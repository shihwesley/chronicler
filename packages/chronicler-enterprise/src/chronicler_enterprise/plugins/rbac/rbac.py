"""Role-based access control with visibility scopes."""

from __future__ import annotations

import logging

from chronicler_core.interfaces.rbac import Permission, RBACPlugin

logger = logging.getLogger(__name__)


# Maps actions to minimum required role level.
_ACTION_LEVELS: dict[str, int] = {
    "read": 1,   # viewer+
    "write": 2,  # editor+
    "admin": 3,  # admin+
    "manage": 4, # org-admin only
}


class ChroniclerRBAC:
    """In-memory RBAC backend with role hierarchy and scope filtering."""

    ROLE_HIERARCHY: dict[str, int] = {
        "org-admin": 4,
        "admin": 3,
        "editor": 2,
        "viewer": 1,
    }

    SCOPES = {"internal", "confidential", "secret"}

    # Minimum role level to access each scope tier
    _SCOPE_ACCESS: dict[str, int] = {
        "internal": 1,     # viewer+
        "confidential": 2, # editor+
        "secret": 3,       # admin+
    }

    def __init__(self) -> None:
        self._permissions: dict[str, list[Permission]] = {}
        self._roles: dict[str, str] = {}
        self._scopes: dict[str, str] = {}  # resource -> scope name

    # -- Protocol methods ------------------------------------------------------

    def check(self, user_id: str, permission: Permission) -> bool:
        """Check if user has the given permission.

        Order: direct grants first, then role-based, then scope filtering.
        """
        # Direct grant check
        user_perms = self._permissions.get(user_id, [])
        if permission in user_perms:
            return True

        # Role-based check
        role = self._roles.get(user_id)
        if role is None:
            return False

        user_level = self.ROLE_HIERARCHY.get(role, 0)
        required_level = _ACTION_LEVELS.get(permission.action)
        if required_level is None:
            return False  # unknown actions are denied by default

        if user_level < required_level:
            return False

        # Scope check — does the user's role clear the resource's scope?
        scope = self._scopes.get(permission.resource)
        if scope is not None:
            min_scope_level = self._SCOPE_ACCESS.get(scope, 0)
            if user_level < min_scope_level:
                return False

        return True

    def grant(self, user_id: str, permission: Permission) -> None:
        """Grant a permission directly to a user."""
        self._permissions.setdefault(user_id, [])
        if permission not in self._permissions[user_id]:
            self._permissions[user_id].append(permission)

    def revoke(self, user_id: str, permission: Permission) -> None:
        """Revoke a previously granted permission."""
        if user_id not in self._permissions:
            return
        self._permissions[user_id] = [p for p in self._permissions[user_id] if p != permission]

    def list_permissions(self, user_id: str) -> list[Permission]:
        """Return all directly-granted permissions for a user."""
        return list(self._permissions.get(user_id, []))

    # -- Enterprise extensions -------------------------------------------------

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign a named role to a user."""
        if role not in self.ROLE_HIERARCHY:
            raise ValueError(f"Unknown role: {role!r} (valid: {list(self.ROLE_HIERARCHY)})")
        self._roles[user_id] = role

    def set_scope(self, resource: str, scope: str) -> None:
        """Set the visibility scope for a resource."""
        if scope not in self.SCOPES:
            raise ValueError(f"Unknown scope: {scope!r} (valid: {sorted(self.SCOPES)})")
        self._scopes[resource] = scope

    def can_read(self, user_id: str, doc: str) -> bool:
        """Convenience: check read permission for a document."""
        return self.check(user_id, Permission(resource=doc, action="read"))

    def can_write(self, user_id: str, doc: str) -> bool:
        """Convenience: check write permission for a document."""
        return self.check(user_id, Permission(resource=doc, action="write"))

    def visible_docs(self, user_id: str) -> list[str]:
        """Return list of resources this user can read, based on scopes and role."""
        read_perm = lambda res: Permission(resource=res, action="read")
        return [res for res in self._scopes if self.check(user_id, read_perm(res))]

