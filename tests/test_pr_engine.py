"""Tests for the PR Engine plugin."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from chronicler_core.drafter.models import FrontmatterModel, TechDoc
from chronicler_enterprise.plugins.pr_engine.engine import PREngine, PREngineConfig


# -- Fixtures ----------------------------------------------------------------


def _make_tech_doc(
    component_id: str = "my-service",
    layer: str = "backend",
    version: str = "1.0.0",
    raw_content: str = "# My Service\nSome docs.",
) -> TechDoc:
    return TechDoc(
        component_id=component_id,
        frontmatter=FrontmatterModel(
            component_id=component_id, layer=layer, version=version,
        ),
        raw_content=raw_content,
    )


def _make_mock_github(*, file_exists: bool = False):
    """Build a mock Github client with a repo that behaves predictably."""
    gh = MagicMock()
    repo = MagicMock()
    gh.get_repo.return_value = repo

    branch = MagicMock()
    branch.commit.sha = "abc123"
    repo.get_branch.return_value = branch

    pr = MagicMock()
    pr.html_url = "https://github.com/org/repo/pull/1"
    pr.head.ref = "chronicler/my-service"
    repo.create_pull.return_value = pr
    repo.get_pull.return_value = pr

    if file_exists:
        contents = MagicMock()
        contents.sha = "file_sha_456"
        repo.get_contents.return_value = contents
    else:
        from github import UnknownObjectException
        repo.get_contents.side_effect = UnknownObjectException(404, {}, {})

    return gh, repo


# -- Tests -------------------------------------------------------------------


class TestPREngineConfig:
    def test_pr_config_defaults(self):
        cfg = PREngineConfig()
        assert cfg.branch_prefix == "chronicler/"
        assert cfg.draft is True
        assert cfg.auto_merge is False
        assert cfg.base_branch == "main"
        assert "{component_id}" in cfg.commit_message_template
        assert "{component_id}" in cfg.pr_title_template


class TestCreateDocPR:
    def test_creates_branch(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.create_doc_pr("org/repo", doc)

        repo.create_git_ref.assert_called_once_with(
            "refs/heads/chronicler/my-service", "abc123",
        )

    def test_creates_file(self):
        gh, repo = _make_mock_github(file_exists=False)
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.create_doc_pr("org/repo", doc)

        repo.create_file.assert_called_once_with(
            ".chronicler/my-service.tech.md",
            "docs: update my-service technical ledger",
            "# My Service\nSome docs.",
            branch="chronicler/my-service",
        )

    def test_opens_pr(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.create_doc_pr("org/repo", doc)

        repo.create_pull.assert_called_once()
        call_kwargs = repo.create_pull.call_args.kwargs
        assert call_kwargs["title"] == "docs: update my-service .tech.md"
        assert call_kwargs["head"] == "chronicler/my-service"
        assert call_kwargs["base"] == "main"
        assert call_kwargs["draft"] is True

    def test_returns_url(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        doc = _make_tech_doc()

        url = engine.create_doc_pr("org/repo", doc)

        assert url == "https://github.com/org/repo/pull/1"

    def test_updates_existing_file(self):
        gh, repo = _make_mock_github(file_exists=True)
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.create_doc_pr("org/repo", doc)

        repo.update_file.assert_called_once()
        repo.create_file.assert_not_called()
        args = repo.update_file.call_args
        assert args[0][0] == ".chronicler/my-service.tech.md"
        # sha from the existing content
        assert args[0][3] == "file_sha_456"

    def test_custom_branch_prefix(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.create_doc_pr("org/repo", doc, branch_prefix="docs/auto/")

        repo.create_git_ref.assert_called_once_with(
            "refs/heads/docs/auto/my-service", "abc123",
        )

    def test_pr_body_contains_component_info(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        doc = _make_tech_doc(component_id="api-gateway", layer="edge", version="2.0.0")

        engine.create_doc_pr("org/repo", doc)

        call_kwargs = repo.create_pull.call_args.kwargs
        body = call_kwargs["body"]
        assert "api-gateway" in body
        assert "edge" in body
        assert "2.0.0" in body


class TestUpdateDocPR:
    def test_pushes_to_branch(self):
        gh, repo = _make_mock_github(file_exists=True)
        engine = PREngine(gh)
        doc = _make_tech_doc()

        engine.update_doc_pr("org/repo", 1, doc)

        repo.get_pull.assert_called_once_with(1)
        repo.update_file.assert_called_once()
        args = repo.update_file.call_args
        assert args[0][0] == ".chronicler/my-service.tech.md"
        assert args.kwargs["branch"] == "chronicler/my-service"


class TestBatchPRs:
    def test_one_per_doc(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        docs = [_make_tech_doc(component_id=f"svc-{i}") for i in range(3)]

        urls = engine.batch_prs("org/repo", docs, strategy="one-per-doc")

        assert len(urls) == 3
        assert repo.create_pull.call_count == 3

    def test_one_per_repo(self):
        gh, repo = _make_mock_github()
        engine = PREngine(gh)
        docs = [_make_tech_doc(component_id=f"svc-{i}") for i in range(3)]

        urls = engine.batch_prs("org/repo", docs, strategy="one-per-repo")

        assert len(urls) == 1
        # One branch created for batch
        branch_ref_calls = [
            c for c in repo.create_git_ref.call_args_list
            if "batch-update" in str(c)
        ]
        assert len(branch_ref_calls) == 1
        # Three files committed
        assert repo.create_file.call_count == 3
        assert repo.create_pull.call_count == 1
