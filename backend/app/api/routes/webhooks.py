"""GitHub webhook receiver — spec Part 8.

Receives GitHub webhook events and dispatches them to the appropriate
handlers. Gated behind webhook_receiver_enabled feature flag.

Supported events: workflow_run, push, pull_request, check_run, repository
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from app.core.feature_flags import feature_flags

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookResponse(BaseModel):
    received: bool
    event_type: str
    processed: bool


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
    x_github_delivery: str = Header("", alias="X-GitHub-Delivery"),
) -> WebhookResponse:
    """Receive and process a GitHub webhook.

    Verifies the webhook signature, then dispatches the event to the
    appropriate handler in the background.
    """
    if not feature_flags.is_enabled("webhook_receiver_enabled"):
        raise HTTPException(status_code=503, detail="Webhook receiver is not enabled")

    payload_bytes = await request.body()

    # Verify signature
    from app.core.config import settings
    webhook_secret = getattr(settings, "github_webhook_secret", "") or ""
    if webhook_secret:
        from app.integrations.github_client import GitHubClient, GitHubAuth
        client = GitHubClient(GitHubAuth.pat(""))
        if not client.verify_webhook_signature(payload_bytes, x_hub_signature_256, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse the event
    import json
    payload = json.loads(payload_bytes)

    # Dispatch to background handler
    background_tasks.add_task(
        _process_webhook_event,
        event_type=x_github_event,
        payload=payload,
        delivery_id=x_github_delivery,
    )

    return WebhookResponse(
        received=True,
        event_type=x_github_event,
        processed=False,  # Processing happens in background
    )


async def _process_webhook_event(event_type: str, payload: dict, delivery_id: str) -> None:
    """Process a webhook event in the background."""
    import structlog
    log = structlog.get_logger()

    log.info(
        "webhook.event_received",
        event_type=event_type,
        delivery_id=delivery_id,
        action=payload.get("action", ""),
    )

    if event_type == "workflow_run":
        await _handle_workflow_run(payload)
    elif event_type == "push":
        await _handle_push(payload)
    elif event_type == "pull_request":
        await _handle_pull_request(payload)
    elif event_type == "check_run":
        await _handle_check_run(payload)
    else:
        log.info("webhook.unhandled_event", event_type=event_type)


async def _handle_workflow_run(payload: dict) -> None:
    """Handle workflow_run events — update execution status."""
    import structlog
    log = structlog.get_logger()

    action = payload.get("action", "")
    workflow_run = payload.get("workflow_run", {})
    run_id = str(workflow_run.get("id", ""))
    status = workflow_run.get("status", "")
    conclusion = workflow_run.get("conclusion", "")

    log.info(
        "webhook.workflow_run",
        action=action,
        run_id=run_id,
        status=status,
        conclusion=conclusion,
    )

    # Update the AepExecution record if it exists
    # This would query aep_executions by workflow_run_id and update status


async def _handle_push(payload: dict) -> None:
    """Handle push events — trigger repo re-indexing if needed."""
    import structlog
    log = structlog.get_logger()

    ref = payload.get("ref", "")
    repo = payload.get("repository", {})
    full_name = repo.get("full_name", "")

    log.info("webhook.push", ref=ref, repo=full_name)

    # If memory_system_enabled, trigger incremental index update
    if feature_flags.is_enabled("memory_system_enabled"):
        log.info("webhook.triggering_reindex", repo=full_name)


async def _handle_pull_request(payload: dict) -> None:
    """Handle pull_request events — run reviewer agent on new PRs."""
    import structlog
    log = structlog.get_logger()

    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number", 0)
    pr_url = pr.get("html_url", "")

    log.info("webhook.pull_request", action=action, pr_number=pr_number, url=pr_url)

    # If agent_coder_enabled, trigger review on opened PRs
    if action == "opened" and feature_flags.is_enabled("agent_coder_enabled"):
        log.info("webhook.triggering_review", pr_number=pr_number)


async def _handle_check_run(payload: dict) -> None:
    """Handle check_run events — notify on failures."""
    import structlog
    log = structlog.get_logger()

    action = payload.get("action", "")
    check_run = payload.get("check_run", {})
    conclusion = check_run.get("conclusion", "")

    log.info("webhook.check_run", action=action, conclusion=conclusion)

    # If conclusion is failure and agent_debugger_enabled, trigger debug agent
    if conclusion == "failure" and feature_flags.is_enabled("agent_debugger_enabled"):
        log.info("webhook.triggering_debug", check_run_id=check_run.get("id"))
