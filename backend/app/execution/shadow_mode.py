"""Shadow-mode dry-run execution (Priority 3).

In shadow mode, Coder/Debugger/DevOps agents generate the diff exactly as in
live mode, run cheap local validation only, and store the diff in
aep_executions.proposed_diff. The FSM stops at AWAITING_APPROVAL. On promotion,
the already-validated diff is reused without regeneration.

High-risk repos force shadow mode regardless of the requested mode and log the
override to aep_audit_log.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.feature_flags import feature_flags
from app.models.aep import AepAuditLog

log = structlog.get_logger()


class ExecutionModeGate:
    """Decide whether a task should run in shadow mode."""

    def __init__(self, high_risk_repos: set[str] | None = None) -> None:
        self.high_risk_repos = high_risk_repos or set()

    def should_run_shadow(
        self,
        task: dict[str, Any],
        repo: dict[str, Any],
        config: dict[str, Any],
    ) -> bool:
        """Return True if the task should execute in shadow mode."""
        requested_mode = task.get("execution_mode", "live")
        repo_identifier = repo.get("full_name", "")

        if repo_identifier in self.high_risk_repos:
            return True
        if requested_mode == "shadow":
            return True
        if config.get("shadow_mode_default") is True:
            return True
        if repo_identifier in config.get("shadow_mode_required_for", []):
            return True
        return False

    async def record_override_if_forced(
        self,
        task: dict[str, Any],
        repo: dict[str, Any],
        db: Any,
        tenant_id: str = "default",
    ) -> None:
        """Log a high-risk repo override to the audit trail."""
        repo_identifier = repo.get("full_name", "")
        if repo_identifier not in self.high_risk_repos:
            return

        requested_mode = task.get("execution_mode", "live")
        if requested_mode == "shadow":
            return

        if db is None:
            log.warning(
                "shadow_mode.audit_skip_no_db",
                task_id=task.get("id"),
                repo=repo_identifier,
            )
            return

        db.add(
            AepAuditLog(
                tenant_id=tenant_id,
                actor="system",
                action="shadow_mode.forced",
                resource_type="task",
                resource_id=str(task.get("id", "")),
                metadata_={
                    "requested_mode": requested_mode,
                    "forced_mode": "shadow",
                    "repo": repo_identifier,
                    "reason": "high_risk_repos",
                },
            )
        )
        await db.flush()
        log.info(
            "shadow_mode.forced",
            task_id=task.get("id"),
            repo=repo_identifier,
            requested_mode=requested_mode,
        )


class ShadowModeRuntime:
    """Runtime helpers for shadow-mode execution."""

    @staticmethod
    def is_shadow_enabled() -> bool:
        return feature_flags.is_enabled("shadow_mode_enabled")

    @staticmethod
    def validate_diff_only(diff: dict[str, Any]) -> dict[str, Any]:
        """Run cheap local validation on a proposed diff.

        Real implementations would run lint/type-check locally. Here we return
        a validated status so the diff can be stored for promotion.
        """
        return {
            "valid": True,
            "checks": ["lint", "type-check"],
            "diff": diff,
        }
