"""Platform-agnostic chat bot adapter (Priority 1).

Primary implementation: Telegram. The adapter interface is designed so
WhatsApp/Slack can plug in later without rewriting the command handler.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger()


@dataclass
class ChatCommand:
    """Normalized incoming chat command."""

    chat_id: str
    command: str
    args: str
    raw: dict[str, Any]


class ChatBotAdapter:
    """Abstract base for chat platform adapters."""

    platform: str = ""

    def verify_webhook_signature(self, request_headers: dict[str, str], body: bytes) -> bool:
        raise NotImplementedError

    def parse_incoming(self, payload: dict[str, Any]) -> Optional[ChatCommand]:
        raise NotImplementedError

    async def send_message(self, chat_id: str, text: str) -> None:
        raise NotImplementedError

    def format_task_update(self, execution: dict[str, Any]) -> str:
        raise NotImplementedError


class TelegramAdapter(ChatBotAdapter):
    """Telegram Bot API adapter.

    Webhook signature is verified via the X-Telegram-Bot-Api-Secret-Token header.
    """

    platform = "telegram"

    def __init__(self, bot_token: str | None = None, secret_token: str | None = None) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.secret_token = secret_token or os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def verify_webhook_signature(self, request_headers: dict[str, str], body: bytes) -> bool:
        """Verify the X-Telegram-Bot-Api-Secret-Token header."""
        if not self.secret_token:
            log.warning("telegram.no_secret_token_configured")
            return True
        received = request_headers.get("x-telegram-bot-api-secret-token", "")
        return hmac.compare_digest(received, self.secret_token)

    def parse_incoming(self, payload: dict[str, Any]) -> Optional[ChatCommand]:
        """Parse a Telegram update into a ChatCommand."""
        message = payload.get("message", {})
        if not message:
            return None
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = (message.get("text") or "").strip()
        if not text:
            return None

        parts = text.split(None, 1)
        command = parts[0].lstrip("/").lower()
        args = parts[1] if len(parts) > 1 else ""

        # Strip bot username suffix from command (e.g. /link@mybot)
        if "@" in command:
            command = command.split("@", 1)[0]

        return ChatCommand(
            chat_id=chat_id,
            command=command,
            args=args,
            raw=payload,
        )

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send a text message via the Telegram Bot API."""
        if not self.bot_token:
            log.warning("telegram.no_bot_token", chat_id=chat_id)
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            client = self._get_client()
            resp = await client.post(url, json={"chat_id": chat_id, "text": text[:4096]})
            resp.raise_for_status()
            log.info("telegram.message_sent", chat_id=chat_id)
        except Exception as exc:
            log.warning("telegram.send_failed", chat_id=chat_id, error=str(exc))

    def format_task_update(self, execution: dict[str, Any]) -> str:
        """Format a human-readable status line for an execution."""
        status = execution.get("status", "unknown")
        task_id = execution.get("task_id", "")
        agent = execution.get("agent_name", "")
        return f"Task {task_id} ({agent}): {status}"


def get_adapter(platform: str) -> ChatBotAdapter:
    """Factory for chat platform adapters."""
    if platform == "telegram":
        return TelegramAdapter()
    raise ValueError(f"Unsupported chat platform: {platform}")
