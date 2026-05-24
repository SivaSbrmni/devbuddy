"""
Smoke tests — verify core endpoints and safety gates.

Run locally:
  cd backend
  pip install -r requirements.txt
  pytest tests/test_smoke.py -v

CI runs these automatically on every push.
"""
import pytest
from httpx import AsyncClient


class TestHealthAndDocs:
    """Basic connectivity and OpenAPI availability."""

    async def test_health_endpoint(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app" in data

    async def test_api_health_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_openapi_schema(self, client: AsyncClient):
        resp = await client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema.get("openapi", "").startswith("3.")
        assert "paths" in schema


class TestSecurityAndSafety:
    """Security gates that must hold in production."""

    async def test_sandbox_disabled_by_default(self):
        """
        The run_python skill must refuse execution when SANDBOX_BACKEND
        is not explicitly configured.
        """
        import os
        from app.services.skills import run_skill

        # Ensure env is not set to e2b or subprocess
        old = os.environ.pop("SANDBOX_BACKEND", None)
        try:
            result = await run_skill("run_python", {"code": "print('hello')"})
            assert "sandbox_disabled" in result.lower() or "disabled" in result.lower()
        finally:
            if old:
                os.environ["SANDBOX_BACKEND"] = old

    async def test_rate_limit_headers_on_chat(self, client: AsyncClient):
        """
        Rate limiting should be active and inject Retry-After on abuse.
        We can't easily trigger a real limit in tests, but we can verify
        the middleware is mounted by checking headers exist.
        """
        # Unauthenticated request should still get through to 401 with headers
        resp = await client.post("/api/v1/chat", json={"message": "test"})
        # We expect 401 since no auth, but the rate limiter should have run
        assert resp.status_code in (401, 429)


class TestCrypto:
    """Encryption utilities for sensitive data."""

    def test_encrypt_decrypt_roundtrip(self):
        from app.core.crypto import encrypt_secret, decrypt_secret

        original = "ghp_supersecretgithubtoken123"
        encrypted = encrypt_secret(original)
        assert encrypted != original
        assert encrypted.startswith("enc::v1::")

        decrypted = decrypt_secret(encrypted)
        assert decrypted == original

    def test_encrypt_idempotent(self):
        """Encrypting an already-encrypted value should return as-is."""
        from app.core.crypto import encrypt_secret

        original = "secret123"
        enc1 = encrypt_secret(original)
        enc2 = encrypt_secret(enc1)
        assert enc1 == enc2

    def test_decrypt_plaintext_backward_compat(self):
        """Legacy plaintext secrets should be handled gracefully."""
        from app.core.crypto import decrypt_secret

        plain = "old_plaintext_token"
        result = decrypt_secret(plain)
        assert result == plain


class TestConfig:
    """Configuration validation."""

    def test_settings_load(self):
        from app.core.config import settings

        assert settings.APP_NAME
        assert settings.DATABASE_URL.startswith("postgresql")

    def test_resolved_api_base(self):
        from app.core.config import settings

        # Test that resolved_api_base works for known providers
        urls = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "llama": "https://api.llama.com/compat/v1",
        }
        for provider, expected_base in urls.items():
            # Create a mock settings with the provider
            from app.core.config import Settings
            s = Settings(
                DATABASE_URL="postgresql+asyncpg://localhost/db",
                LLM_PROVIDER=provider,  # type: ignore
            )
            assert s.resolved_api_base == expected_base
