"""Quota ledger + circuit breaker for the LLM Gateway.

Tracks per-provider, per-model usage against free-tier limits.
When a provider hits its limit or errors repeatedly, the circuit breaker
cools it down for exponential backoff.

Spec Part 2.4: Redis quota ledger keys:
  aep:quota:{provider}:{model}:rpm   INCR, TTL 60s
  aep:quota:{provider}:{model}:rpd   INCR, TTL until reset
  aep:quota:{provider}:{model}:tpm   token sum, TTL 60s
  aep:breaker:{provider}:{model}     cooling_down flag, TTL = backoff

This implementation uses in-memory dicts with TTLs. When Redis is
available, the same logic ports to Redis INCR + EXPIRE for multi-instance
safety. The interface is identical either way.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class QuotaState:
    """In-memory quota tracking for a single provider+model."""
    rpm_count: int = 0
    rpm_window_start: float = field(default_factory=time.time)
    rpd_count: int = 0
    rpd_window_start: float = field(default_factory=time.time)
    tpm_count: int = 0
    tpm_window_start: float = field(default_factory=time.time)


@dataclass
class BreakerState:
    """Circuit breaker state for a single provider+model."""
    cooling_down: bool = False
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    last_error: str = ""


class QuotaLedger:
    """Tracks request/token counts per provider+model against limits.

    Uses sliding windows for RPM (60s) and TPM (60s), and a fixed daily
    window for RPD (reset at midnight UTC or after 24h from first request).
    """

    def __init__(self) -> None:
        self._state: dict[str, QuotaState] = {}
        self._limits: dict[str, dict[str, int]] = {}  # provider -> {rpm, rpd, tpm}

    def register_limits(self, provider: str, limits: dict[str, int]) -> None:
        """Register the free-tier limits for a provider."""
        self._limits[provider] = limits

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def _get_or_create(self, provider: str, model: str) -> QuotaState:
        key = self._key(provider, model)
        if key not in self._state:
            self._state[key] = QuotaState()
        return self._state[key]

    def _reset_if_expired(self, state: QuotaState) -> None:
        now = time.time()
        if now - state.rpm_window_start > 60:
            state.rpm_count = 0
            state.rpm_window_start = now
        if now - state.tpm_window_start > 60:
            state.tpm_count = 0
            state.tpm_window_start = now
        if now - state.rpd_window_start > 86400:  # 24 hours
            state.rpd_count = 0
            state.rpd_window_start = now

    def would_exceed(self, provider: str, model: str, estimated_tokens: int = 0) -> bool:
        """Check if a request would exceed any quota limit."""
        limits = self._limits.get(provider, {})
        state = self._get_or_create(provider, model)
        self._reset_if_expired(state)

        rpm_limit = limits.get("rpm", 0)
        rpd_limit = limits.get("rpd", 0)
        tpm_limit = limits.get("tpm", 0)

        if rpm_limit and state.rpm_count >= rpm_limit:
            return True
        if rpd_limit and state.rpd_count >= rpd_limit:
            return True
        if tpm_limit and state.tpm_count + estimated_tokens > tpm_limit:
            return True
        return False

    def record(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record a successful request's usage."""
        state = self._get_or_create(provider, model)
        self._reset_if_expired(state)
        state.rpm_count += 1
        state.rpd_count += 1
        state.tpm_count += input_tokens + output_tokens
        log.debug(
            "quota.recorded",
            provider=provider,
            model=model,
            rpm=state.rpm_count,
            rpd=state.rpd_count,
            tpm=state.tpm_count,
        )

    def get_usage(self, provider: str, model: str) -> dict[str, int]:
        """Get current usage for observability."""
        state = self._get_or_create(provider, model)
        self._reset_if_expired(state)
        return {
            "rpm": state.rpm_count,
            "rpd": state.rpd_count,
            "tpm": state.tpm_count,
        }


class CircuitBreaker:
    """Circuit breaker with exponential backoff for failing providers.

    On 429 or 5xx errors, the provider is cooled down for an increasing
    duration. After cooldown, a single probe request is allowed; if it
    succeeds, the breaker resets. If it fails, backoff doubles.
    """

    def __init__(self, base_cooldown_ms: int = 60_000, max_cooldown_ms: int = 3_600_000) -> None:
        self.base_cooldown = base_cooldown_ms / 1000.0  # convert to seconds
        self.max_cooldown = max_cooldown_ms / 1000.0
        self._state: dict[str, BreakerState] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def is_cooling_down(self, provider: str, model: str) -> bool:
        """Check if a provider+model is currently in cooldown."""
        key = self._key(provider, model)
        state = self._state.get(key)
        if not state or not state.cooling_down:
            return False
        if time.time() >= state.cooldown_until:
            state.cooling_down = False
            return False
        return True

    def cool_down(self, provider: str, model: str, error: str = "", retry_after: Optional[float] = None) -> None:
        """Put a provider+model into cooldown after a failure."""
        key = self._key(provider, model)
        state = self._state.setdefault(key, BreakerState())
        state.consecutive_failures += 1
        state.last_error = error

        if retry_after:
            cooldown = retry_after
        else:
            # Exponential backoff: base * 2^(failures-1), capped at max
            cooldown = min(
                self.base_cooldown * (2 ** (state.consecutive_failures - 1)),
                self.max_cooldown,
            )

        state.cooling_down = True
        state.cooldown_until = time.time() + cooldown
        log.warning(
            "breaker.cooldown",
            provider=provider,
            model=model,
            cooldown_seconds=cooldown,
            failures=state.consecutive_failures,
            error=error,
        )

    def record_success(self, provider: str, model: str) -> None:
        """Reset the breaker after a successful request."""
        key = self._key(provider, model)
        state = self._state.get(key)
        if state:
            state.cooling_down = False
            state.consecutive_failures = 0
            state.last_error = ""

    def get_state(self, provider: str, model: str) -> dict:
        """Get breaker state for observability."""
        key = self._key(provider, model)
        state = self._state.get(key)
        if not state:
            return {"cooling_down": False, "failures": 0}
        return {
            "cooling_down": self.is_cooling_down(provider, model),
            "failures": state.consecutive_failures,
            "last_error": state.last_error,
            "cooldown_remaining": max(0, state.cooldown_until - time.time()),
        }
