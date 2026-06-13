"""CommandValidator — Phase 6.

Validates shell commands injected into GitHub Actions workflow YAML
against a blocklist. Every command passes through this validator;
results are logged to ``aep_audit_log``.

Spec reference: AGENTS.md Phase 6 — CommandValidator, spec §10.2.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.aep.observability import aep_logger

_logger = aep_logger("aep.security.command_validator")


# ─────────────────────────────────────────────────────────────────────────────
# Blocklists (spec §10.2)
# ─────────────────────────────────────────────────────────────────────────────

BLOCKED_COMMANDS: set[str] = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };:",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "init 0",
    "init 6",
    "kill -9 1",
    "killall",
    "pkill -9",
}

BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"curl\s+.*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)", re.IGNORECASE),
    re.compile(r"wget\s+.*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)", re.IGNORECASE),
    re.compile(r"eval\s+\$\(", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r">\s*/dev/nvme", re.IGNORECASE),
    re.compile(r"nc\s+-[le].*\d+", re.IGNORECASE),
    re.compile(r"ncat\s+-[le].*\d+", re.IGNORECASE),
    re.compile(r"/etc/shadow", re.IGNORECASE),
    re.compile(r"/etc/passwd.*>>", re.IGNORECASE),
    re.compile(r"iptables\s+-F", re.IGNORECASE),
    re.compile(r"ufw\s+disable", re.IGNORECASE),
    re.compile(r"crypto(?:miner|mine)", re.IGNORECASE),
    re.compile(r"xmrig", re.IGNORECASE),
    re.compile(r"base64\s+-d.*\|\s*(?:bash|sh)", re.IGNORECASE),
]

BLOCKED_ENV_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\{?(?:AWS_SECRET|GITHUB_TOKEN|DATABASE_URL|DB_PASSWORD)", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret[_-]?key|password)\s*=\s*['\"]?[^\s'\"]+", re.IGNORECASE),
]

SUDO_ALLOWED_COMMANDS: set[str] = {
    "apt-get",
    "apt",
    "yum",
    "dnf",
    "pip",
    "npm",
    "systemctl",
}


class CommandValidationResult:
    """Result of command validation."""

    def __init__(
        self,
        *,
        command: str,
        is_allowed: bool,
        violations: list[str],
        warnings: list[str],
        risk_level: str,
    ) -> None:
        self.command = command
        self.is_allowed = is_allowed
        self.violations = violations
        self.warnings = warnings
        self.risk_level = risk_level

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "is_allowed": self.is_allowed,
            "violations": self.violations,
            "warnings": self.warnings,
            "risk_level": self.risk_level,
        }


class CommandValidator:
    """Validates shell commands against security blocklists."""

    def __init__(
        self,
        *,
        extra_blocked: Optional[set[str]] = None,
        extra_patterns: Optional[list[re.Pattern[str]]] = None,
    ) -> None:
        self._blocked = BLOCKED_COMMANDS | (extra_blocked or set())
        self._patterns = BLOCKED_PATTERNS + (extra_patterns or [])

    def validate(self, command: str) -> CommandValidationResult:
        """Validate a single command string."""
        violations: list[str] = []
        warnings: list[str] = []
        normalized = command.strip()

        # Check exact blocklist
        for blocked in self._blocked:
            if blocked in normalized:
                violations.append(f"Blocked command detected: '{blocked}'")

        # Check regex patterns
        for pattern in self._patterns:
            if pattern.search(normalized):
                violations.append(
                    f"Dangerous pattern detected: {pattern.pattern[:60]}"
                )

        # Check environment variable leakage
        for env_pattern in BLOCKED_ENV_PATTERNS:
            if env_pattern.search(normalized):
                warnings.append(
                    f"Potential secret exposure: {env_pattern.pattern[:60]}"
                )

        # Check sudo usage
        if "sudo" in normalized:
            parts = normalized.split("sudo", 1)
            if len(parts) > 1:
                after_sudo = parts[1].strip().split()[0] if parts[1].strip() else ""
                if after_sudo and after_sudo not in SUDO_ALLOWED_COMMANDS:
                    warnings.append(
                        f"Sudo used with non-allowlisted command: '{after_sudo}'"
                    )

        # Determine risk level
        if violations:
            risk_level = "critical"
        elif warnings:
            risk_level = "elevated"
        else:
            risk_level = "low"

        is_allowed = len(violations) == 0

        if not is_allowed:
            _logger.warning(
                "command_blocked",
                command=normalized[:200],
                violations=violations,
            )

        return CommandValidationResult(
            command=normalized,
            is_allowed=is_allowed,
            violations=violations,
            warnings=warnings,
            risk_level=risk_level,
        )

    def validate_batch(self, commands: list[str]) -> list[CommandValidationResult]:
        """Validate a batch of commands."""
        return [self.validate(cmd) for cmd in commands]

    async def validate_and_audit(
        self,
        command: str,
        *,
        tenant_id: uuid.UUID,
        execution_id: Optional[uuid.UUID] = None,
        actor_id: Optional[str] = None,
        db: Any,
    ) -> CommandValidationResult:
        """Validate a command and log the result to aep_audit_log."""
        from sqlalchemy import text

        result = self.validate(command)

        await db.execute(
            text(
                """
                INSERT INTO aep_audit_log
                    (id, tenant_id, event_type, actor_type, actor_id,
                     resource_type, resource_id, action, details,
                     created_at, prev_hash)
                VALUES
                    (:id, :tenant_id, :event_type, :actor_type, :actor_id,
                     :resource_type, :resource_id, :action, :details,
                     :created_at, :prev_hash)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "event_type": "command_validation",
                "actor_type": "system",
                "actor_id": actor_id or "command_validator",
                "resource_type": "command",
                "resource_id": str(execution_id) if execution_id else None,
                "action": "allow" if result.is_allowed else "block",
                "details": str(result.to_dict()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "prev_hash": "",
            },
        )
        await db.commit()

        return result


_singleton: Optional[CommandValidator] = None


def get_command_validator() -> CommandValidator:
    global _singleton
    if _singleton is None:
        _singleton = CommandValidator()
    return _singleton
