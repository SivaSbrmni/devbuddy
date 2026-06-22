"""Tests for Priority 1 — Chat Bot Interface (Telegram)."""

from __future__ import annotations

import pytest

from app.integrations.chatbot import TelegramAdapter, ChatCommand, get_adapter


class TestTelegramAdapter:
    """Telegram webhook parsing, signature verification, and formatting."""

    def test_parse_incoming_link_command(self):
        adapter = TelegramAdapter(bot_token="token", secret_token="secret")
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "/link abc123",
            }
        }
        cmd = adapter.parse_incoming(payload)
        assert isinstance(cmd, ChatCommand)
        assert cmd.chat_id == "12345"
        assert cmd.command == "link"
        assert cmd.args == "abc123"

    def test_parse_incoming_strips_bot_username(self):
        adapter = TelegramAdapter()
        payload = {
            "message": {
                "chat": {"id": 99},
                "text": "/link@DevBuddyBot code",
            }
        }
        cmd = adapter.parse_incoming(payload)
        assert cmd.command == "link"
        assert cmd.args == "code"

    def test_parse_incoming_ignores_non_message_updates(self):
        adapter = TelegramAdapter()
        assert adapter.parse_incoming({"edited_message": {}}) is None

    def test_verify_signature_with_secret(self):
        adapter = TelegramAdapter(secret_token="shh")
        assert adapter.verify_webhook_signature(
            {"x-telegram-bot-api-secret-token": "shh"},
            b"body",
        )
        assert not adapter.verify_webhook_signature(
            {"x-telegram-bot-api-secret-token": "wrong"},
            b"body",
        )

    def test_verify_signature_without_secret_passes(self):
        adapter = TelegramAdapter()
        assert adapter.verify_webhook_signature({}, b"body")

    def test_format_task_update(self):
        adapter = TelegramAdapter()
        text = adapter.format_task_update({"task_id": "t1", "agent_name": "coder", "status": "completed"})
        assert "t1" in text
        assert "completed" in text

    def test_get_adapter_factory(self):
        adapter = get_adapter("telegram")
        assert adapter.platform == "telegram"
        with pytest.raises(ValueError):
            get_adapter("unknown")
