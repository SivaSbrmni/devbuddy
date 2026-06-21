"""Compatibility Adapter Layer — Seam 1 between existing app and autonomous extension.

Wraps existing services and exposes hooks for the autonomous engine.
All methods no-op when the autonomous engine is disabled, ensuring
backward compatibility (spec Part 1).
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger()


@dataclass
class AuthContext:
    """Authentication context extracted from the existing app."""
    user_id: str
    email: str
    tenant_id: str = "default"
    github_token: Optional[str] = None
    is_admin: bool = False


@dataclass
class ExistingRepoModel:
    """Repository record from the existing application."""
    id: str
    name: str
    owner: str
    full_name: str
    html_url: str
    default_branch: str = "main"


@dataclass
class AgentEvent:
    """Event emitted by agents to the existing app's notification system."""
    type: str  # task_created, task_completed, execution_started, etc.
    task_id: Optional[str] = None
    execution_id: Optional[str] = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for event handlers
TaskEventHandler = Callable[[AgentEvent], None]


class CompatibilityAdapter:
    """Bridge between the existing DevBuddy application and the AEP extension.

    This adapter:
    1. Exposes hooks for task lifecycle events
    2. Provides auth context from the existing JWT system
    3. Wraps repository records from the existing app
    4. Emits notifications back to the existing app (SSE, WebSocket)

    When autonomous_engine_enabled is False, all methods are safe no-ops.
    """

    def __init__(self) -> None:
        self._task_created_handlers: list[TaskEventHandler] = []
        self._task_completed_handlers: list[TaskEventHandler] = []
        self._notification_handlers: list[TaskEventHandler] = []

    # ─── Event Hooks ─────────────────────────────────────────────────────────

    def on_task_created(self, handler: TaskEventHandler) -> None:
        """Register a handler called when a new AEP task is created."""
        self._task_created_handlers.append(handler)

    def on_task_completed(self, handler: TaskEventHandler) -> None:
        """Register a handler called when an AEP task completes."""
        self._task_completed_handlers.append(handler)

    def on_notification(self, handler: TaskEventHandler) -> None:
        """Register a handler for general agent notifications."""
        self._notification_handlers.append(handler)

    def emit_task_created(self, event: AgentEvent) -> None:
        for handler in self._task_created_handlers:
            try:
                handler(event)
            except Exception as e:
                log.error("adapter.task_created_handler_failed", error=str(e))

    def emit_task_completed(self, event: AgentEvent) -> None:
        for handler in self._task_completed_handlers:
            try:
                handler(event)
            except Exception as e:
                log.error("adapter.task_completed_handler_failed", error=str(e))

    def emit_notification(self, event: AgentEvent) -> None:
        for handler in self._notification_handlers:
            try:
                handler(event)
            except Exception as e:
                log.error("adapter.notification_handler_failed", error=str(e))

    # ─── Auth Context ────────────────────────────────────────────────────────

    def get_auth_context(self, token_payload: dict) -> AuthContext:
        """Extract auth context from a decoded JWT payload.

        Args:
            token_payload: Decoded JWT claims (from core.security.decode_token)

        Returns:
            AuthContext with user info and optional GitHub token
        """
        email = (token_payload.get("email") or token_payload.get("sub") or "").lower()
        return AuthContext(
            user_id=email,
            email=email,
            tenant_id="default",  # single-tenant for now; spec allows multi-tenant
            github_token=token_payload.get("github_token"),
            is_admin=email in _get_admin_emails(),
        )

    # ─── Repository Bridge ───────────────────────────────────────────────────

    def get_repository_record(self, repo_data: dict) -> ExistingRepoModel:
        """Convert existing app's repo format to AEP's ExpectedRepoModel."""
        return ExistingRepoModel(
            id=str(repo_data.get("id", "")),
            name=repo_data.get("name", ""),
            owner=repo_data.get("owner", ""),
            full_name=repo_data.get("full_name", ""),
            html_url=repo_data.get("html_url", ""),
            default_branch=repo_data.get("default_branch", "main"),
        )


def _get_admin_emails() -> set[str]:
    """Get admin emails from settings."""
    from app.core.config import settings
    return settings.allowed_emails_set


# Singleton
compat_adapter = CompatibilityAdapter()
