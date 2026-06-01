"""GitHub webhook receiver endpoint — Phase 2.

Mounted at ``/api/v1/aep/webhooks/github``. Verifies the HMAC-SHA256
signature from ``X-Hub-Signature-256`` and dispatches the event to
the :class:`WebhookEventRouter`.

Gated behind ``webhook_receiver_enabled``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.aep.feature_flags import get_feature_flag_service
from app.aep.github.webhooks import get_event_router, verify_signature
from app.aep.observability import aep_logger

router = APIRouter(prefix="/aep/webhooks", tags=["aep-webhooks"])
_logger = aep_logger("aep.api.github_webhooks")

PHASE = "phase_2"


def _disabled_envelope() -> dict[str, Any]:
    return {
        "error": "service_unavailable",
        "phase": PHASE,
        "message": "Webhook receiver is not enabled. Set `webhook_receiver_enabled` to true.",
        "flag": "webhook_receiver_enabled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/github")
async def receive_github_webhook(request: Request, response: Response) -> dict[str, Any]:
    """Accept a GitHub webhook event."""
    ff = get_feature_flag_service()
    if not await ff.is_enabled("webhook_receiver_enabled"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return _disabled_envelope()

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "ping")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if webhook_secret and not verify_signature(body, signature, webhook_secret):
        _logger.warning("webhook_signature_invalid", delivery=delivery_id)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"error": "invalid_signature", "message": "HMAC verification failed"}

    if event_type == "ping":
        _logger.info("webhook_ping", delivery=delivery_id)
        return {"status": "pong", "delivery": delivery_id}

    try:
        import json
        payload = json.loads(body)
    except Exception:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "invalid_payload", "message": "Could not parse JSON body"}

    event_router = get_event_router()
    handler_count = await event_router.dispatch(event_type, payload)

    _logger.info(
        "webhook_dispatched",
        event=event_type,
        delivery=delivery_id,
        handlers=handler_count,
    )

    return {
        "status": "accepted",
        "event": event_type,
        "delivery": delivery_id,
        "handlers_invoked": handler_count,
    }
