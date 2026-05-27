"""
Tests for the AEP routers — ``/LLM/*`` gateway and ``/api/v1/aep`` admin.

These tests assume the contract that holds while the
``llm_gateway_enabled`` feature flag is **off**:
  - ``/LLM/health`` returns 503 with ``X-AEP-Phase`` reflecting the
    current phase string while the flag is off.
  - ``/LLM/{generate,chat,embed,route,models}`` reject auth-less requests
    (401) and return the structured 503 envelope when authenticated.

Authentication is harder to fake without a valid Supabase JWT — for
Phase 0 we verify only the unauthenticated paths and the public
``/LLM/health`` route. Authenticated paths are covered indirectly by
the smoke tests of the existing endpoints, which share the same
``get_current_user`` dependency.
"""
from __future__ import annotations


import pytest
from httpx import AsyncClient

from app.aep.feature_flags import reset_feature_flag_service


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    # Ensure flags are off regardless of CI env var leakage.
    for var in (
        "AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED",
        "AEP_FLAG_LLM_GATEWAY_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_feature_flag_service()
    yield
    reset_feature_flag_service()


class TestGatewayHealth:
    async def test_health_returns_503_when_disabled(self, client: AsyncClient):
        resp = await client.get("/LLM/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "disabled"
        assert body["phase"]  # current phase string (e.g. ``phase_1``)
        assert body["flag"] == "llm_gateway_enabled"
        assert resp.headers.get("X-AEP-Phase")


class TestGatewayProtectedEndpoints:
    """Without auth, the protected endpoints should 401, NOT 503.

    This is important: the 503 envelope is the *enabled-but-not-yet-
    wired* signal. Unauthenticated calls must still be rejected by
    the auth layer first.
    """

    async def test_generate_requires_auth(self, client: AsyncClient):
        resp = await client.post("/LLM/generate", json={"prompt": "hi"})
        assert resp.status_code in (401, 403)

    async def test_chat_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/LLM/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code in (401, 403)

    async def test_embed_requires_auth(self, client: AsyncClient):
        resp = await client.post("/LLM/embed", json={"input": "x"})
        assert resp.status_code in (401, 403)

    async def test_route_requires_auth(self, client: AsyncClient):
        resp = await client.post("/LLM/route", json={"task_type": "plan"})
        assert resp.status_code in (401, 403)

    async def test_models_requires_auth(self, client: AsyncClient):
        resp = await client.get("/LLM/models")
        assert resp.status_code in (401, 403)


class TestOpenApiAdvertisesGatewayRoutes:
    """The OpenAPI schema must include every gateway endpoint."""

    async def test_paths_present(self, client: AsyncClient):
        resp = await client.get("/api/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        for expected in (
            "/LLM/health",
            "/LLM/generate",
            "/LLM/chat",
            "/LLM/embed",
            "/LLM/route",
            "/LLM/models",
            "/api/v1/aep/flags",
            "/api/v1/aep/plugins",
            "/api/v1/aep/status",
        ):
            assert expected in paths, f"missing path in OpenAPI: {expected}"


class TestExistingEndpointsStillWork:
    """The AEP layer must not regress any existing endpoint."""

    async def test_health_still_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_api_health_still_ok(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_openapi_still_valid(self, client: AsyncClient):
        resp = await client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema.get("openapi", "").startswith("3.")
