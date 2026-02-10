"""Tests for ChroniclerRBAC — direct grants, role hierarchy, scopes, protocol."""

from __future__ import annotations

import pytest

from chronicler_core.interfaces.rbac import Permission, RBACPlugin
from chronicler_enterprise.plugins.rbac.rbac import ChroniclerRBAC


@pytest.fixture()
def rbac() -> ChroniclerRBAC:
    return ChroniclerRBAC()


# -- Direct permission grants -------------------------------------------------


def test_grant_and_check(rbac: ChroniclerRBAC):
    perm = Permission(resource="doc:design", action="read")
    rbac.grant("alice", perm)
    assert rbac.check("alice", perm) is True


def test_check_ungranted_returns_false(rbac: ChroniclerRBAC):
    perm = Permission(resource="doc:secret", action="write")
    assert rbac.check("bob", perm) is False


def test_revoke_removes_permission(rbac: ChroniclerRBAC):
    perm = Permission(resource="doc:notes", action="read")
    rbac.grant("carol", perm)
    rbac.revoke("carol", perm)
    assert rbac.check("carol", perm) is False


def test_list_permissions(rbac: ChroniclerRBAC):
    p1 = Permission(resource="doc:a", action="read")
    p2 = Permission(resource="doc:b", action="write")
    rbac.grant("dave", p1)
    rbac.grant("dave", p2)
    result = rbac.list_permissions("dave")
    assert len(result) == 2
    assert p1 in result
    assert p2 in result


def test_list_permissions_empty(rbac: ChroniclerRBAC):
    assert rbac.list_permissions("nobody") == []


# -- Role assignment and hierarchy --------------------------------------------


def test_assign_role(rbac: ChroniclerRBAC):
    rbac.assign_role("eve", "editor")
    # Editor (level 2) should pass a read check (requires level 1)
    assert rbac.check("eve", Permission(resource="doc:x", action="read")) is True


def test_role_hierarchy_admin_has_editor_access(rbac: ChroniclerRBAC):
    rbac.assign_role("frank", "admin")
    # Admin (level 3) inherits editor (level 2) — write requires level 2
    assert rbac.check("frank", Permission(resource="doc:y", action="write")) is True


def test_viewer_cannot_write(rbac: ChroniclerRBAC):
    rbac.assign_role("gina", "viewer")
    assert rbac.check("gina", Permission(resource="doc:z", action="write")) is False


# -- Scopes and visibility ----------------------------------------------------


def test_set_scope_and_visibility(rbac: ChroniclerRBAC):
    rbac.assign_role("hank", "viewer")
    rbac.set_scope("doc:internal-report", "internal")
    rbac.set_scope("doc:team-only", "confidential")

    # Viewer (level 1) can read internal (requires level 1)
    assert rbac.can_read("hank", "doc:internal-report") is True
    # Viewer cannot read confidential (requires level 2)
    assert rbac.can_read("hank", "doc:team-only") is False


# -- Convenience methods -------------------------------------------------------


def test_can_read_convenience(rbac: ChroniclerRBAC):
    rbac.assign_role("iris", "viewer")
    assert rbac.can_read("iris", "doc:public") is True


def test_can_write_convenience(rbac: ChroniclerRBAC):
    rbac.assign_role("jay", "editor")
    assert rbac.can_write("jay", "doc:draft") is True


def test_visible_docs(rbac: ChroniclerRBAC):
    rbac.assign_role("kate", "editor")
    rbac.set_scope("doc:open", "internal")
    rbac.set_scope("doc:team", "confidential")
    rbac.set_scope("doc:classified", "secret")

    visible = rbac.visible_docs("kate")
    # Editor (level 2) sees internal + confidential but not secret
    assert "doc:open" in visible
    assert "doc:team" in visible
    assert "doc:classified" not in visible


# -- Protocol conformance -----------------------------------------------------


def test_protocol_conformance():
    assert isinstance(ChroniclerRBAC(), RBACPlugin)
