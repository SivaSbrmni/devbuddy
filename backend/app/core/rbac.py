"""RBAC — Role-Based Access Control (spec Part 10).

Roles: aep:viewer, aep:operator, aep:admin, aep:system
Integrated with the existing app's auth via the Compatibility Adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import structlog

log = structlog.get_logger()


class Role(str, Enum):
    """AEP roles (spec Part 10)."""
    VIEWER = "aep:viewer"       # Read-only access to tasks, executions, metrics
    OPERATOR = "aep:operator"   # Can create tasks, trigger executions, manage repos
    ADMIN = "aep:admin"         # Can manage feature flags, secrets, all tenants
    SYSTEM = "aep:system"       # Internal system access (agents, webhooks)


class Permission(str, Enum):
    """AEP permissions."""
    # Viewer permissions
    VIEW_TASKS = "view:tasks"
    VIEW_EXECUTIONS = "view:executions"
    VIEW_METRICS = "view:metrics"
    VIEW_REPOS = "view:repos"

    # Operator permissions
    CREATE_TASK = "create:task"
    TRIGGER_EXECUTION = "trigger:execution"
    CANCEL_EXECUTION = "cancel:execution"
    REGISTER_REPO = "register:repo"
    VIEW_LOGS = "view:logs"

    # Admin permissions
    MANAGE_FLAGS = "manage:flags"
    MANAGE_SECRETS = "manage:secrets"
    MANAGE_TENANTS = "manage:tenants"
    VIEW_AUDIT_LOG = "view:audit_log"

    # System permissions
    EXECUTE_AGENT = "execute:agent"
    RECEIVE_WEBHOOK = "receive:webhook"
    ACCESS_ALL_TENANTS = "access:all_tenants"


# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.VIEW_TASKS,
        Permission.VIEW_EXECUTIONS,
        Permission.VIEW_METRICS,
        Permission.VIEW_REPOS,
    },
    Role.OPERATOR: {
        # Inherits all viewer permissions
        Permission.VIEW_TASKS,
        Permission.VIEW_EXECUTIONS,
        Permission.VIEW_METRICS,
        Permission.VIEW_REPOS,
        Permission.CREATE_TASK,
        Permission.TRIGGER_EXECUTION,
        Permission.CANCEL_EXECUTION,
        Permission.REGISTER_REPO,
        Permission.VIEW_LOGS,
    },
    Role.ADMIN: {
        # Inherits all operator permissions
        Permission.VIEW_TASKS,
        Permission.VIEW_EXECUTIONS,
        Permission.VIEW_METRICS,
        Permission.VIEW_REPOS,
        Permission.CREATE_TASK,
        Permission.TRIGGER_EXECUTION,
        Permission.CANCEL_EXECUTION,
        Permission.REGISTER_REPO,
        Permission.VIEW_LOGS,
        Permission.MANAGE_FLAGS,
        Permission.MANAGE_SECRETS,
        Permission.MANAGE_TENANTS,
        Permission.VIEW_AUDIT_LOG,
    },
    Role.SYSTEM: {
        # System has all permissions
        *list(Permission),
    },
}


@dataclass
class RBACContext:
    """RBAC context for a request."""
    user_id: str
    tenant_id: str = "default"
    roles: set[Role] = field(default_factory=set)
    is_admin: bool = False


class RBACManager:
    """Role-Based Access Control manager.

    Checks permissions for authenticated users. Integrates with the
    existing app's auth via the Compatibility Adapter.
    """

    def __init__(self) -> None:
        self._user_roles: dict[str, set[Role]] = {}  # user_id -> roles

    def assign_role(self, user_id: str, role: Role) -> None:
        """Assign a role to a user."""
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        self._user_roles[user_id].add(role)
        log.info("rbac.role_assigned", user=user_id, role=role.value)

    def revoke_role(self, user_id: str, role: Role) -> None:
        """Revoke a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role)

    def get_user_roles(self, user_id: str) -> set[Role]:
        """Get all roles for a user."""
        return self._user_roles.get(user_id, set())

    def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all permissions for a user (union of all role permissions)."""
        roles = self.get_user_roles(user_id)
        permissions: set[Permission] = set()
        for role in roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        return permissions

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        return permission in self.get_user_permissions(user_id)

    def require_permission(self, user_id: str, permission: Permission) -> None:
        """Raise if user lacks a permission. Use as a guard in endpoints."""
        if not self.has_permission(user_id, permission):
            raise PermissionError(
                f"User '{user_id}' lacks permission '{permission.value}'"
            )

    def get_context(self, user_id: str, tenant_id: str = "default") -> RBACContext:
        """Build RBAC context for a request."""
        roles = self.get_user_roles(user_id)
        is_admin = Role.ADMIN in roles or Role.SYSTEM in roles
        return RBACContext(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
            is_admin=is_admin,
        )

    def initialize_from_auth(self, user_id: str, is_admin_email: bool = False) -> None:
        """Initialize roles based on the existing app's auth system.

        Users in the admin email list get ADMIN role.
        All other authenticated users get OPERATOR role.
        """
        if is_admin_email:
            self.assign_role(user_id, Role.ADMIN)
        else:
            self.assign_role(user_id, Role.OPERATOR)


# Singleton
rbac = RBACManager()
