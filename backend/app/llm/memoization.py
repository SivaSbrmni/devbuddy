"""Response memoization (cache-first routing) for deterministic LLM calls.

Spec Priority 0: exact canonical-signature matching only. Enabled by default for
`debugger`, `test`, and `devops` task types. Explicit opt-in required for `coder`
and `planner` via `response_memoization_scope` override.

The cache is checked before compression and provider routing. On a hit, the
stored NormalizedResponse is returned directly and no provider is called.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import feature_flags
from app.models.aep import AepResponseCache

log = structlog.get_logger()

DEFAULT_MEMOIZATION_SCOPE = {"debugger", "test", "devops"}


def _sort_keys_deep(value: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON serialization."""
    if isinstance(value, dict):
        return {k: _sort_keys_deep(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_sort_keys_deep(v) for v in value]
    return value


def _compute_signature_hash(components: dict[str, Any]) -> str:
    """SHA-256 of sorted, JSON-canonicalized signature components."""
    canonical = _sort_keys_deep(components)
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_error_type(error_message: str) -> str:
    """Strip line numbers, timestamps, memory addresses from error text."""
    import re
    if not error_message:
        return ""
    # Remove line numbers like (line 42) and digits that look like timestamps
    cleaned = re.sub(r"\(?line\s+\d+\)?", "", error_message, flags=re.IGNORECASE)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?", "", cleaned)
    cleaned = re.sub(r"0x[0-9a-fA-F]+", "", cleaned)
    cleaned = re.sub(r"\d+\.\d+\.\d+\.\d+:\d+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _hash_stack_trace_top_frames(stack_trace: str, top_n: int = 3) -> str:
    """Hash top N stack frames with paths relativized."""
    if not stack_trace:
        return ""
    lines = [line.strip() for line in stack_trace.splitlines() if line.strip()]
    frames: list[str] = []
    for line in lines:
        if line.startswith("File ") or "/" in line or "\\" in line:
            # Drop absolute prefixes and line numbers to keep the signature stable
            simplified = line.split(":", 1)[0]
            simplified = simplified.replace("\\", "/")
            simplified = simplified.split("/")[-1]
            frames.append(simplified)
        if len(frames) >= top_n:
            break
    return hashlib.sha256("\n".join(frames).encode("utf-8")).hexdigest()


class SignatureCanonicalizer:
    """Base class for task-type-specific canonicalizers."""

    def __init__(self, task_type: str) -> None:
        self.task_type = task_type

    def canonicalize(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class DebuggerCanonicalizer(SignatureCanonicalizer):
    """Canonicalizer for debugger task type."""

    def canonicalize(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "error_type": _normalize_error_type(context.get("error_message", "")),
            "error_fingerprint": _hash_stack_trace_top_frames(context.get("stack_trace", ""), 3),
            "file_content_hash": _sha256_text(context.get("target_file_content", "")),
            "language": context.get("language", ""),
            "dependency_lock_hash": context.get("lockfile_hash"),
        }


class TestCanonicalizer(SignatureCanonicalizer):
    """Canonicalizer for test-generation task type."""

    def canonicalize(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "code_under_test_hash": _sha256_text(context.get("code", "")),
            "specification_hash": _sha256_text(context.get("specification", "")),
            "language": context.get("language", ""),
            "dependency_lock_hash": context.get("lockfile_hash"),
            "test_type": context.get("test_type", "unit"),
        }


class DevOpsCanonicalizer(SignatureCanonicalizer):
    """Canonicalizer for devops/lint/format task type."""

    def canonicalize(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "workflow_name": context.get("workflow_name", ""),
            "file_content_hash": _sha256_text(context.get("file_content", "")),
            "dependency_lock_hash": context.get("lockfile_hash"),
            "command": context.get("command", ""),
        }


CANONICALIZERS: dict[str, type[SignatureCanonicalizer]] = {
    "debugger": DebuggerCanonicalizer,
    "test": TestCanonicalizer,
    "devops": DevOpsCanonicalizer,
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ttl_for(task_type: str) -> datetime | None:
    """Return expiration time for a cached entry. None means indefinite."""
    now = datetime.utcnow()
    if task_type == "devops":
        return None
    if task_type == "debugger":
        return now + timedelta(days=90)
    if task_type == "test":
        return now + timedelta(days=30)
    return now + timedelta(days=7)


class ResponseMemoizer:
    """Exact-signature response memoizer.

    Usage:
        memoizer = ResponseMemoizer(db)
        result = await memoizer.execute(
            task_type="debugger",
            context={"error_message": ..., "target_file_content": ...},
            tenant_id="default",
            execute_fn=actual_llm_call,
        )
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self.db = db

    def _is_memoization_scoped(self, task_type: str, context: dict[str, Any]) -> bool:
        """Return True if memoization should be applied to this task type."""
        if not feature_flags.is_enabled("response_memoization_enabled"):
            return False

        if context.get("skip_cache") is True:
            return False

        # Default scope excludes coder/planner; explicit override can include them.
        # The feature flag service treats env vars as booleans, so read the scope
        # override directly as a JSON array.
        scope: list[str] = list(DEFAULT_MEMOIZATION_SCOPE)
        scope_env = os.environ.get("AEP_FLAG_RESPONSE_MEMOIZATION_SCOPE")
        if scope_env:
            try:
                scope = json.loads(scope_env)
            except Exception:
                scope = list(DEFAULT_MEMOIZATION_SCOPE)

        return task_type in set(scope)

    def _canonicalizer(self, task_type: str) -> SignatureCanonicalizer | None:
        cls = CANONICALIZERS.get(task_type)
        return cls(task_type) if cls else None

    async def lookup(
        self,
        task_type: str,
        context: dict[str, Any],
        tenant_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Look up a cached response by exact canonical signature."""
        if not self.db:
            return None

        canonicalizer = self._canonicalizer(task_type)
        if not canonicalizer:
            return None

        components = canonicalizer.canonicalize(context)
        signature_hash = _compute_signature_hash(components)

        stmt = select(AepResponseCache).where(
            AepResponseCache.tenant_id == tenant_id,
            AepResponseCache.task_type == task_type,
            AepResponseCache.signature_hash == signature_hash,
        )
        result = await self.db.execute(stmt)
        cached = result.scalar_one_or_none()
        if not cached:
            return None

        if cached.expires_at is not None and cached.expires_at < datetime.utcnow():
            return None

        cached.hit_count = (cached.hit_count or 0) + 1
        cached.last_hit_at = datetime.utcnow()
        await self.db.flush()

        log.info(
            "aep.cache.hit",
            tenant_id=tenant_id,
            task_type=task_type,
            signature_hash=signature_hash,
            hit_count=cached.hit_count,
        )
        return dict(cached.response_payload)

    async def store(
        self,
        task_type: str,
        context: dict[str, Any],
        response: dict[str, Any],
        tenant_id: str = "default",
        validated: bool = False,
    ) -> None:
        """Store a validated successful response in the cache."""
        if not self.db:
            return

        if not validated:
            return

        if response.get("finish_reason") == "error" or not response.get("text"):
            return

        canonicalizer = self._canonicalizer(task_type)
        if not canonicalizer:
            return

        components = canonicalizer.canonicalize(context)
        signature_hash = _compute_signature_hash(components)
        payload = {
            "text": response.get("text", ""),
            "finish_reason": response.get("finish_reason", "stop"),
            "usage": response.get("usage", {"input_tokens": 0, "output_tokens": 0}),
            "provider": response.get("provider", ""),
            "model": response.get("model", ""),
            "latency_ms": response.get("latency_ms", 0),
        }

        stmt = select(AepResponseCache).where(
            AepResponseCache.tenant_id == tenant_id,
            AepResponseCache.task_type == task_type,
            AepResponseCache.signature_hash == signature_hash,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.response_payload = payload
            existing.signature_components = components
            existing.expires_at = _ttl_for(task_type)
            existing.last_hit_at = datetime.utcnow()
        else:
            self.db.add(
                AepResponseCache(
                    tenant_id=tenant_id,
                    task_type=task_type,
                    signature_hash=signature_hash,
                    signature_components=components,
                    response_payload=payload,
                    expires_at=_ttl_for(task_type),
                    last_hit_at=datetime.utcnow(),
                )
            )
        await self.db.flush()
        log.info(
            "aep.cache.store",
            tenant_id=tenant_id,
            task_type=task_type,
            signature_hash=signature_hash,
        )

    async def execute(
        self,
        task_type: str,
        context: dict[str, Any],
        tenant_id: str,
        execute_fn: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
    ) -> dict[str, Any]:
        """Execute with memoization: lookup, then call, then store if valid."""
        if not self._is_memoization_scoped(task_type, context):
            return await execute_fn()

        cached = await self.lookup(task_type, context, tenant_id)
        if cached is not None:
            tokens = cached.usage.get("input_tokens", 0) + cached.usage.get("output_tokens", 0)
            log.info(
                "aep.cache.tokens_saved",
                tenant_id=tenant_id,
                task_type=task_type,
                tokens_saved=tokens,
            )
            return cached

        log.info("aep.cache.miss", tenant_id=tenant_id, task_type=task_type)
        response = await execute_fn()
        await self.store(task_type, context, response, tenant_id=tenant_id, validated=True)
        return response


# Singleton for health-check / global routes without a user db session.
response_memoizer = ResponseMemoizer()
