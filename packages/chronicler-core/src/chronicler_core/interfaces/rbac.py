"""RBAC plugin interface and models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class Permission(BaseModel):
    """A single permission grant scoped to a resource and action."""

    model_config = ConfigDict(frozen=True)

    resource: str
    action: str
    conditions: dict[str, Any] = {}


@runtime_checkable
class RBACPlugin(Protocol):
    """Role-based access control backend."""

    def check(self, user_id: str, permission: Permission) -> bool: ...

    def grant(self, user_id: str, permission: Permission) -> None: ...

    def revoke(self, user_id: str, permission: Permission) -> None: ...

    def list_permissions(self, user_id: str) -> list[Permission]: ...
