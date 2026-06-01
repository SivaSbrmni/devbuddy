"""GitHub webhook receiver and event router — Phase 2.

Mounted at ``/api/v1/aep/webhooks/github``. Accepts GitHub webhook
payloads, verifies the HMAC-SHA256 signature, and dispatches events
to registered handlers.

Events handled (spec AGENTS.md Phase 2):
    push, pull_request, workflow_run, check_run, issue_comment,
    pull_request_review, installation, installation_repositories.

The receiver is gated behind the ``webhook_receiver_enabled`` feature
flag. When the flag is off every request returns a structured 503.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from app.aep.observability import aep_logger

_logger = aep_logger("aep.github.webhooks")

WebhookHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class WebhookEventRouter:
    """Routes incoming GitHub webhook events to registered handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[WebhookHandler]] = {}
        self._global_handlers: list[WebhookHandler] = []

    def on(self, event: str) -> Callable[[WebhookHandler], WebhookHandler]:
        """Decorator to register a handler for a specific event type."""
        def decorator(fn: WebhookHandler) -> WebhookHandler:
            self._handlers.setdefault(event, []).append(fn)
            return fn
        return decorator

    def on_any(self, fn: WebhookHandler) -> WebhookHandler:
        """Register a handler that receives every event."""
        self._global_handlers.append(fn)
        return fn

    async def dispatch(self, event: str, payload: dict[str, Any]) -> int:
        """Dispatch an event to all matching handlers. Returns handler count."""
        count = 0
        for handler in self._global_handlers:
            try:
                await handler(event, payload)
                count += 1
            except Exception as exc:
                _logger.warning(
                    "webhook_handler_error",
                    handler=getattr(handler, "__qualname__", repr(handler)),
                    gh_event=event,
                    error=str(exc),
                )
        for handler in self._handlers.get(event, []):
            try:
                await handler(event, payload)
                count += 1
            except Exception as exc:
                _logger.warning(
                    "webhook_handler_error",
                    handler=getattr(handler, "__qualname__", repr(handler)),
                    gh_event=event,
                    error=str(exc),
                )
        return count


def verify_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify a GitHub HMAC-SHA256 webhook signature.

    ``signature`` is the value of the ``X-Hub-Signature-256`` header
    (e.g. ``sha256=abc123...``).
    """
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode(), payload_body, hashlib.sha256,
    ).hexdigest()
    received = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


# ── Singleton event router ──────────────────────────────────────────────────

_event_router: Optional[WebhookEventRouter] = None


def get_event_router() -> WebhookEventRouter:
    global _event_router
    if _event_router is None:
        _event_router = WebhookEventRouter()
        _register_default_handlers(_event_router)
    return _event_router


def _register_default_handlers(router: WebhookEventRouter) -> None:
    """Register default logging handlers for all supported event types."""

    @router.on_any
    async def _log_event(event: str, payload: dict[str, Any]) -> None:
        action = payload.get("action", "")
        repo_name = ""
        if "repository" in payload:
            repo_name = payload["repository"].get("full_name", "")
        _logger.info(
            "webhook_received",
            event=event,
            action=action,
            repository=repo_name,
        )

    @router.on("push")
    async def _handle_push(event: str, payload: dict[str, Any]) -> None:
        ref = payload.get("ref", "")
        repo = payload.get("repository", {}).get("full_name", "")
        commits = payload.get("commits", [])
        _logger.info(
            "push_event",
            repository=repo,
            ref=ref,
            commit_count=len(commits),
        )

    @router.on("pull_request")
    async def _handle_pull_request(event: str, payload: dict[str, Any]) -> None:
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name", "")
        _logger.info(
            "pull_request_event",
            repository=repo,
            action=action,
            pr_number=pr.get("number"),
            pr_title=pr.get("title", ""),
        )

    @router.on("workflow_run")
    async def _handle_workflow_run(event: str, payload: dict[str, Any]) -> None:
        action = payload.get("action", "")
        run = payload.get("workflow_run", {})
        repo = payload.get("repository", {}).get("full_name", "")
        _logger.info(
            "workflow_run_event",
            repository=repo,
            action=action,
            run_id=run.get("id"),
            status=run.get("status"),
            conclusion=run.get("conclusion"),
        )

    @router.on("check_run")
    async def _handle_check_run(event: str, payload: dict[str, Any]) -> None:
        action = payload.get("action", "")
        check = payload.get("check_run", {})
        repo = payload.get("repository", {}).get("full_name", "")
        _logger.info(
            "check_run_event",
            repository=repo,
            action=action,
            check_name=check.get("name", ""),
            status=check.get("status"),
            conclusion=check.get("conclusion"),
        )


def reset_event_router() -> None:
    """Reset the singleton — used by tests."""
    global _event_router
    _event_router = None
