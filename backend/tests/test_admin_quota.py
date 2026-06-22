"""Tests for Priority 5 — Quota Dashboard admin endpoint."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.rbac import Role, rbac
from app.api.routes.admin import get_quota_snapshot


class MockUser:
    def __init__(self, email: str, user_id: str = "u1"):
        self.id = user_id
        self.email = email


class TestAdminQuota:
    """Quota snapshot is aep:admin-gated and returns provider/model usage."""

    def test_admin_allowed(self):
        admin_email = next(iter(settings.allowed_emails_set or {"admin@example.com"}))
        rbac.initialize_from_auth("admin-user", is_admin_email=True)
        assert Role.ADMIN in rbac.get_user_roles("admin-user")

    def test_non_admin_rejected(self):
        rbac.initialize_from_auth("operator-user", is_admin_email=False)
        assert Role.ADMIN not in rbac.get_user_roles("operator-user")

    @pytest.mark.asyncio
    async def test_get_quota_snapshot_raises_for_non_admin(self):
        rbac.initialize_from_auth("op-user", is_admin_email=False)
        user = MockUser("operator@example.com", "op-user")
        with pytest.raises(HTTPException) as exc:
            await get_quota_snapshot(user)
        assert exc.value.status_code == 403
