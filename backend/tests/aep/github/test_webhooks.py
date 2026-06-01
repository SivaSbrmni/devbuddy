"""Tests for the webhook event router and HMAC verification."""
import hashlib
import hmac

import pytest

from app.aep.github.webhooks import (
    WebhookEventRouter,
    verify_signature,
)


class TestVerifySignature:
    """HMAC-SHA256 signature verification."""

    def test_valid_signature(self) -> None:
        body = b'{"action": "opened"}'
        secret = "test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig = f"sha256={digest}"
        assert verify_signature(body, sig, secret) is True

    def test_invalid_signature(self) -> None:
        body = b'{"action": "opened"}'
        secret = "test-secret"
        assert verify_signature(body, "sha256=invalid", secret) is False

    def test_missing_prefix(self) -> None:
        body = b'{"action": "opened"}'
        secret = "test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_signature(body, digest, secret) is False

    def test_different_secret(self) -> None:
        body = b'{"action": "opened"}'
        digest = hmac.new(b"secret-1", body, hashlib.sha256).hexdigest()
        assert verify_signature(body, f"sha256={digest}", "secret-2") is False

    def test_empty_body(self) -> None:
        body = b""
        secret = "test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_signature(body, f"sha256={digest}", secret) is True


class TestWebhookEventRouter:
    """Event router dispatch and handler registration."""

    @pytest.mark.asyncio
    async def test_dispatch_to_specific_handler(self) -> None:
        router = WebhookEventRouter()
        received: list[tuple[str, dict]] = []

        @router.on("push")
        async def handle_push(event: str, payload: dict) -> None:
            received.append((event, payload))

        count = await router.dispatch("push", {"ref": "refs/heads/main"})
        assert count == 1
        assert len(received) == 1
        assert received[0] == ("push", {"ref": "refs/heads/main"})

    @pytest.mark.asyncio
    async def test_dispatch_to_global_handler(self) -> None:
        router = WebhookEventRouter()
        received: list[str] = []

        @router.on_any
        async def handle_any(event: str, payload: dict) -> None:
            received.append(event)

        await router.dispatch("pull_request", {"action": "opened"})
        await router.dispatch("push", {"ref": "refs/heads/main"})
        assert received == ["pull_request", "push"]

    @pytest.mark.asyncio
    async def test_dispatch_unknown_event(self) -> None:
        router = WebhookEventRouter()
        count = await router.dispatch("unknown_event", {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_handler_error_does_not_break_dispatch(self) -> None:
        router = WebhookEventRouter()
        received: list[str] = []

        @router.on("push")
        async def bad_handler(event: str, payload: dict) -> None:
            raise ValueError("boom")

        @router.on("push")
        async def good_handler(event: str, payload: dict) -> None:
            received.append("ok")

        count = await router.dispatch("push", {})
        assert count == 1
        assert received == ["ok"]

    @pytest.mark.asyncio
    async def test_multiple_handlers_same_event(self) -> None:
        router = WebhookEventRouter()
        order: list[int] = []

        @router.on("push")
        async def h1(event: str, payload: dict) -> None:
            order.append(1)

        @router.on("push")
        async def h2(event: str, payload: dict) -> None:
            order.append(2)

        await router.dispatch("push", {})
        assert order == [1, 2]
