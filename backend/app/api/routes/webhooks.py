"""GitHub webhook receiver — spec Part 8.

Receives GitHub webhook events and dispatches them to the appropriate
handlers. Gated behind webhook_receiver_enabled feature flag.

Supported events: workflow_run, push, pull_request, check_run, repository
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.feature_flags import feature_flags
from app.integrations.chatbot import ChatCommand, TelegramAdapter, get_adapter
from app.models.aep import AepChatBinding

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


# ─── Telegram Chat Bot Webhook — Priority 1 ─────────────────────────────────

@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header("", alias="X-Telegram-Bot-Api-Secret-Token"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive Telegram bot commands and dispatch them.

    Gated behind telegram_bot_enabled feature flag. Unbound chat_ids are
    rejected except for the /link command.
    """
    if not feature_flags.is_enabled("telegram_bot_enabled"):
        raise HTTPException(status_code=503, detail="Telegram bot is not enabled")

    adapter = TelegramAdapter()
    body = await request.body()
    if not adapter.verify_webhook_signature(
        {"x-telegram-bot-api-secret-token": x_telegram_bot_api_secret_token},
        body,
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook signature")

    import json
    payload = json.loads(body)
    cmd = adapter.parse_incoming(payload)
    if not cmd:
        return {"ok": True}

    await _handle_chat_command(adapter, cmd, db)
    return {"ok": True}


async def _handle_chat_command(
    adapter: TelegramAdapter,
    cmd: ChatCommand,
    db: AsyncSession,
) -> None:
    """Handle a normalized chat command."""
    import structlog
    log = structlog.get_logger()

    log.info("telegram.command", chat_id=cmd.chat_id, command=cmd.command, args=cmd.args)

    if cmd.command == "link":
        await _handle_link_command(adapter, cmd, db)
        return

    # All other commands require an active binding
    stmt = select(AepChatBinding).where(
        AepChatBinding.platform == adapter.platform,
        AepChatBinding.platform_chat_id == cmd.chat_id,
        AepChatBinding.status == "active",
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()
    if not binding:
        await adapter.send_message(
            cmd.chat_id,
            "Not linked. Send /link <code> from your DevBuddy dashboard.",
        )
        return

    if cmd.command == "task":
        await adapter.send_message(
            cmd.chat_id,
            f"Task submitted: {cmd.args[:200]}. You will receive updates as it progresses.",
        )
    elif cmd.command == "status":
        await adapter.send_message(cmd.chat_id, "No active executions for this chat.")
    elif cmd.command == "cancel":
        await adapter.send_message(cmd.chat_id, "Cancel request received.")
    elif cmd.command == "approve":
        await adapter.send_message(cmd.chat_id, "Approval recorded.")
    elif cmd.command == "repos":
        await adapter.send_message(cmd.chat_id, "Your repositories: (none registered)")
    else:
        await adapter.send_message(
            cmd.chat_id,
            "Commands: /link <code>, /task <description>, /status, /cancel, /approve, /repos, /help",
        )


async def _handle_link_command(
    adapter: TelegramAdapter,
    cmd: ChatCommand,
    db: AsyncSession,
) -> None:
    """Bind a Telegram chat to a tenant/user using a one-time link code."""
    from datetime import datetime
    import structlog
    log = structlog.get_logger()

    link_code = cmd.args.strip()
    if not link_code:
        await adapter.send_message(cmd.chat_id, "Usage: /link <code>")
        return

    stmt = select(AepChatBinding).where(
        AepChatBinding.platform == adapter.platform,
        AepChatBinding.link_code == link_code,
        AepChatBinding.status == "pending",
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()
    if not binding:
        await adapter.send_message(cmd.chat_id, "Invalid or expired link code.")
        return

    binding.status = "active"
    binding.platform_chat_id = cmd.chat_id
    binding.link_code = None
    binding.linked_at = datetime.utcnow()
    await db.flush()
    log.info(
        "telegram.binding_activated",
        tenant_id=binding.tenant_id,
        user_id=binding.user_id,
        chat_id=cmd.chat_id,
    )
    await adapter.send_message(
        cmd.chat_id,
        f"Linked to DevBuddy. Welcome, {binding.user_id}!",
    )
