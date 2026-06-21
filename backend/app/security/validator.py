"""Workflow Validator — security enforcement for agent actions.

Validates allowed actions, domains, runtime limits, resource limits, secret access.
Prevents secret leakage, infinite loops, crypto mining, malicious execution, unsafe deploys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class ValidationResult:
    allowed: bool
    reason: str = ""
    warnings: list[str] | None = None


# Blocked shell patterns
BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"rm\s+-rf\s+/(?!\btmp\b)", re.IGNORECASE),       # destructive rm outside /tmp
    re.compile(r"curl.*\|\s*(?:bash|sh)", re.IGNORECASE),         # pipe to shell
    re.compile(r"wget.*\|\s*(?:bash|sh)", re.IGNORECASE),
    re.compile(r"crypto|mining|miner|xmrig", re.IGNORECASE),      # crypto mining
    re.compile(r"chmod\s+777", re.IGNORECASE),                     # overly permissive
    re.compile(r"passwd|shadow", re.IGNORECASE),                   # system files
    re.compile(r"(?:DROP|DELETE)\s+(?:DATABASE|TABLE)", re.IGNORECASE),  # destructive SQL
    # Spec Part 10 additions:
    re.compile(r"\bdd\s+.*of=/dev/", re.IGNORECASE),              # dd to device files
    re.compile(r"mkfs", re.IGNORECASE),                            # filesystem creation
    re.compile(r"chmod\s+777\s+/", re.IGNORECASE),                # chmod 777 on root
    re.compile(r"env\s*\|\s*grep", re.IGNORECASE),                # credential dumping
    re.compile(r"cat\s+/etc/passwd", re.IGNORECASE),              # passwd file access
    re.compile(r"printenv", re.IGNORECASE),                        # env var dumping
    re.compile(r"curl\s+.*\$\(.*\)", re.IGNORECASE),              # command substitution in curl
]

# Allowed domains for network access
ALLOWED_DOMAINS: set[str] = {
    "github.com",
    "api.github.com",
    "registry.npmjs.org",
    "pypi.org",
    "api.anthropic.com",
    "api.llama.com",
    "railway.app",
    "vercel.com",
    "api.vercel.com",
    "hub.docker.com",
}

# Secret patterns to detect in output
SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),                  # API keys
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                   # GitHub PAT
    re.compile(r"(?:password|secret|token|key)\s*=\s*\S+", re.IGNORECASE),
]

# Resource limits
MAX_COMMAND_TIMEOUT_S = 600
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_OUTPUT_LENGTH = 100_000


class WorkflowValidator:
    """Validates agent actions before execution."""

    def validate_command(self, command: str) -> ValidationResult:
        """Validate a shell command before execution."""
        for pattern in BLOCKED_PATTERNS:
            if pattern.search(command):
                log.warning("security.command_blocked", command=command[:100], pattern=pattern.pattern)
                return ValidationResult(
                    allowed=False,
                    reason=f"Blocked pattern detected: {pattern.pattern}",
                )
        return ValidationResult(allowed=True)

    def validate_file_write(self, path: str, content: str) -> ValidationResult:
        """Validate file write operation."""
        # Check size
        if len(content.encode()) > MAX_FILE_SIZE_BYTES:
            return ValidationResult(allowed=False, reason="File too large")

        # Check for secrets in content
        warnings: list[str] = []
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                warnings.append(f"Possible secret in content: {pattern.pattern}")

        # Block writes to sensitive paths
        sensitive = ["/etc/", "/root/", "/home/", "~/.ssh/", "~/.aws/"]
        for s in sensitive:
            if path.startswith(s):
                return ValidationResult(allowed=False, reason=f"Write to sensitive path: {s}")

        return ValidationResult(allowed=True, warnings=warnings or None)

    def validate_network_access(self, url: str) -> ValidationResult:
        """Validate outbound network access."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.hostname or ""

        if domain in ALLOWED_DOMAINS or domain.endswith(tuple(f".{d}" for d in ALLOWED_DOMAINS)):
            return ValidationResult(allowed=True)

        return ValidationResult(
            allowed=False,
            reason=f"Domain not in allowlist: {domain}",
        )

    def sanitize_output(self, output: str) -> str:
        """Remove secrets from output before logging/storing."""
        sanitized = output
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        if len(sanitized) > MAX_OUTPUT_LENGTH:
            sanitized = sanitized[:MAX_OUTPUT_LENGTH] + "\n... [truncated]"
        return sanitized

    def validate_deployment(self, config: dict[str, Any]) -> ValidationResult:
        """Validate deployment configuration."""
        warnings: list[str] = []

        if not config.get("health_check"):
            warnings.append("No health check configured")
        if not config.get("rollback_plan"):
            warnings.append("No rollback plan configured")
        if config.get("environment") == "production" and not config.get("approval"):
            return ValidationResult(
                allowed=False,
                reason="Production deployment requires explicit approval",
            )

        return ValidationResult(allowed=True, warnings=warnings or None)


# Singleton
workflow_validator = WorkflowValidator()
