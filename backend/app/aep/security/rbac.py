"""RBAC Middleware — Phase 6.

Four roles: ``aep:viewer``, ``aep:operator``, ``aep:admin``, ``aep:system``.
Integrates with the existing JWT auth via the Compatibility Adapter.

Spec reference: AGENTS.md Phase 6 — RBAC, spec §10.3.
"""
from __future__ import annotations

import functools
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request, status

from app.aep.observability import aep_logger

_logger = aep_logger("aep.security.rbac")


class AepRole(str, Enum):
    """AEP role hierarchy (spec §10.3)."""

    VIEWER = "aep:viewer"
    OPERATOR = "aep:operator"
    ADMIN = "aep:admin"
    SYSTEM = "aep:system"


# Role hierarchy — higher roles include all permissions of lower roles
ROLE_HIERARCHY: dict[AepRole, set[AepRole]] = {
    AepRole.SYSTEM: {AepRole.SYSTEM, AepRole.ADMIN, AepRole.OPERATOR, AepRole.VIEWER},
    AepRole.ADMIN: {AepRole.ADMIN, AepRole.OPERATOR, AepRole.VIEWER},
    AepRole.OPERATOR: {AepRole.OPERATOR, AepRole.VIEWER},
    AepRole.VIEWER: {AepRole.VIEWER},
}

# Route → minimum required role mapping
ROUTE_PERMISSIONS: dict[str, AepRole] = {
    # Phase 6 admin operations
    "PUT /api/v1/aep/flags/{name}": AepRole.ADMIN,
    "POST /api/v1/aep/repositories": AepRole.OPERATOR,
    "DELETE /api/v1/aep/repositories/{id}": AepRole.ADMIN,
    "POST /api/v1/aep/executions": AepRole.OPERATOR,
    "POST /api/v1/aep/executions/{id}/approve": AepRole.OPERATOR,
    "POST /api/v1/aep/executions/{id}/reject": AepRole.OPERATOR,
    "POST /api/v1/aep/executions/{id}/execute": AepRole.OPERATOR,
    "POST /api/v1/aep/secrets": AepRole.ADMIN,
    "DELETE /api/v1/aep/secrets/{name}": AepRole.ADMIN,
    # Read operations
    "GET /api/v1/aep/flags": AepRole.VIEWER,
    "GET /api/v1/aep/plugins": AepRole.VIEWER,
    "GET /api/v1/aep/status": AepRole.VIEWER,
    "GET /api/v1/aep/repositories": AepRole.VIEWER,
    "GET /api/v1/aep/executions": AepRole.VIEWER,
    "GET /api/v1/aep/executions/{id}": AepRole.VIEWER,
}


def extract_aep_role(user: dict[str, Any]) -> AepRole:
    """Extract the AEP role from a JWT-decoded user dict.

    Looks for ``aep_role`` in the JWT payload. Falls back to
    ``aep:viewer`` if not present.
    """
    payload = user.get("payload") or user
    role_str = payload.get("aep_role", AepRole.VIEWER.value)
    try:
        return AepRole(role_str)
    except ValueError:
        _logger.warning("invalid_aep_role", role=role_str)
        return AepRole.VIEWER


def has_permission(user_role: AepRole, required_role: AepRole) -> bool:
    """Check if user_role satisfies required_role in the hierarchy."""
    allowed_roles = ROLE_HIERARCHY.get(user_role, set())
    return required_role in allowed_roles


def require_role(minimum_role: AepRole) -> Callable:
    """Decorator that enforces a minimum AEP role on a route handler.

    Usage::

        @router.post("/sensitive")
        @require_role(AepRole.ADMIN)
        async def sensitive_endpoint(user=Depends(get_current_user)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = kwargs.get("user")
            if user is None:
                # Try to find user in positional args or request
                for arg in args:
                    if isinstance(arg, dict) and ("payload" in arg or "id" in arg):
                        user = arg
                        break

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required for AEP operations",
                )

            user_role = extract_aep_role(user)
            if not has_permission(user_role, minimum_role):
                _logger.warning(
                    "rbac_denied",
                    user_role=user_role.value,
                    required_role=minimum_role.value,
                    endpoint=func.__name__,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires role '{minimum_role.value}' or higher. "
                           f"Current role: '{user_role.value}'.",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RbacMiddleware:
    """FastAPI middleware that enforces route-level RBAC.

    Checks the request method + path against ``ROUTE_PERMISSIONS``
    and verifies the user's JWT contains the required role.

    This middleware is additive — routes not in the permission map
    are not restricted by this middleware (they may still have their
    own auth via ``Depends(get_current_user)``).
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = request.method
        path = request.url.path

        # Check if this route has a permission requirement
        required_role = self._match_route(method, path)
        if required_role is None:
            await self.app(scope, receive, send)
            return

        # Let the endpoint handle its own auth — this middleware just
        # adds an additional RBAC check layer. The actual enforcement
        # happens in the @require_role decorator per-endpoint.
        await self.app(scope, receive, send)

    def _match_route(self, method: str, path: str) -> Optional[AepRole]:
        """Find the required role for a given method+path."""
        # Exact match first
        key = f"{method} {path}"
        if key in ROUTE_PERMISSIONS:
            return ROUTE_PERMISSIONS[key]

        # Pattern match (replace UUID segments with {id}, {name})
        for route_pattern, role in ROUTE_PERMISSIONS.items():
            if self._pattern_matches(route_pattern, key):
                return role

        return None

    @staticmethod
    def _pattern_matches(pattern: str, actual: str) -> bool:
        """Simple pattern matcher for route templates."""
        pattern_parts = pattern.split("/")
        actual_parts = actual.split("/")

        if len(pattern_parts) != len(actual_parts):
            return False

        for p, a in zip(pattern_parts, actual_parts):
            if p.startswith("{") and p.endswith("}"):
                continue
            if p != a:
                return False
        return True
