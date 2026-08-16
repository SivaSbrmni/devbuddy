"""Session architecture tests."""

import uuid

import pytest

from app.agent.session_hub import SessionEventHub
from app.agent.session_runner import _translate_cloud_event
from app.core.security import create_session_scoped_token, decode_token, extract_github_token


def test_format_event_structure():
    sid = uuid.uuid4()
    event = SessionEventHub.format_event(sid, 1, "thinking", {"content": "hello"})
    assert event["type"] == "thinking"
    assert event["session_id"] == str(sid)
    assert event["seq"] == 1
    assert event["payload"]["content"] == "hello"
    assert isinstance(event["timestamp"], int)


def test_translate_cloud_pr_event():
    result = _translate_cloud_event("pr", {"url": "https://github.com/o/r/pull/1", "number": 1})
    assert result is not None
    etype, payload = result
    assert etype == "pr_created"
    assert payload["url"] == "https://github.com/o/r/pull/1"


def test_translate_cloud_done_event():
    result = _translate_cloud_event("done", {"summary": "All done"})
    assert result is not None
    etype, payload = result
    assert etype == "session_status"
    assert payload["status"] == "completed"


def test_translate_unknown_event_returns_none():
    assert _translate_cloud_event("unknown_type", {}) is None


def test_extract_github_token():
    assert extract_github_token({"github_token": "ghp_test"}) == "ghp_test"
    assert extract_github_token({"github_token": ""}) is None
    assert extract_github_token(None) is None


def test_session_scoped_token_has_no_github_credentials():
    token = create_session_scoped_token("user@example.com", str(uuid.uuid4()))
    payload = decode_token(token)
    assert payload is not None
    assert payload["scope"] == "session"
    assert payload["email"] == "user@example.com"
    assert "github_token" not in payload


@pytest.mark.asyncio
async def test_create_session_requires_github_for_repo(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.security import get_current_user
    from app.models.user import User

    user_id = uuid.uuid4()
    fake_user = User(id=user_id, email="test@example.com", name="Test", is_active=True)

    async def override_user():
        return fake_user

    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/sessions",
                json={
                    "prompt": "Fix the login bug",
                    "repository_owner": "acme",
                    "repository_name": "app",
                },
            )
            assert resp.status_code == 400
            assert "GitHub" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_follow_up_rejects_running_session(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.security import get_current_user
    from app.models.user import User
    from app.models.agent_session import AgentSession

    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    fake_user = User(id=user_id, email="test@example.com", name="Test", is_active=True)

    class FakeScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        async def scalar(self, *_args, **_kwargs):
            return AgentSession(
                id=session_id,
                user_id=user_id,
                title="Test",
                prompt="hello",
                status="running",
            )

        async def execute(self, *_args, **_kwargs):
            return FakeExecuteResult(None)

        async def commit(self):
            return None

    class FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *_args):
            return None

    async def override_user():
        return fake_user

    monkeypatch.setattr(
        "app.api.routes.sessions.async_session_factory",
        FakeSessionFactory(),
    )
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/sessions/{session_id}/messages",
                json={"content": "Also add tests"},
            )
            assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()
