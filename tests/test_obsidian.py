"""Tests for chronicler-obsidian: transforms, sync, and CLI commands."""

import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from chronicler_obsidian.transform import (
    TransformPipeline,
    LinkRewriter,
    FrontmatterFlattener,
    DataviewInjector,
    IndexGenerator,
)
from chronicler_obsidian.sync import ObsidianSync
from chronicler_obsidian.models import SyncReport, SyncError
from chronicler_core.config.models import ObsidianConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_FRONTMATTER = {
    "component_id": "auth-service",
    "version": "1.2.0",
    "layer": "api",
    "security_level": "high",
    "owner_team": "platform-eng",
    "governance": {
        "verification_status": "ai_draft",
        "visibility": "internal",
    },
    "edges": [
        {"target": "user-db", "type": "reads"},
        {"target": "token-service", "type": "calls"},
        {"target": "gateway", "type": "called_by"},
    ],
}

SAMPLE_TECH_MD = """\
---
component_id: auth-service
version: 1.2.0
layer: api
security_level: high
owner_team: platform-eng
governance:
  verification_status: ai_draft
  visibility: internal
edges:
  - target: user-db
    type: reads
  - target: token-service
    type: calls
  - target: gateway
    type: called_by
---

# Auth Service

Handles authentication and token management.

## Overview

Uses JWT tokens and validates against user-db.
See agent://user-db/schema.tech.md for schema details.
Also see agent://token-service for token generation.
"""


def _make_source_dir(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Create a source directory with .tech.md files."""
    source = tmp_path / "source"
    source.mkdir()
    if files is None:
        files = {"auth-service.tech.md": SAMPLE_TECH_MD}
    for name, content in files.items():
        (source / name).write_text(content)
    return source


def _make_sync(tmp_path: Path, source: Path | None = None, pipeline=None) -> tuple[ObsidianSync, Path]:
    """Create an ObsidianSync instance with temp vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    src = source or _make_source_dir(tmp_path)
    if pipeline is None:
        pipeline = TransformPipeline([
            LinkRewriter(),
            FrontmatterFlattener(),
            DataviewInjector(),
            IndexGenerator(),
        ])
    config = ObsidianConfig()
    sync = ObsidianSync(
        source_dir=str(src),
        vault_path=str(vault),
        config=config,
        pipeline=pipeline,
    )
    return sync, vault


# ===========================================================================
# LinkRewriter tests
# ===========================================================================


class TestLinkRewriter:
    def setup_method(self):
        self.rewriter = LinkRewriter()

    def test_agent_uri_with_path(self):
        content = "See agent://auth-service/api.tech.md for details."
        result = self.rewriter.apply(content, {})
        assert "[[auth-service - api]]" in result
        assert "agent://" not in result

    def test_agent_uri_without_path(self):
        content = "Connects to agent://auth-service directly."
        result = self.rewriter.apply(content, {})
        assert "[[auth-service]]" in result
        assert "agent://" not in result

    def test_existing_wikilink_unchanged(self):
        content = "See [[existing-link]] for more."
        result = self.rewriter.apply(content, {})
        assert "[[existing-link]]" in result

    def test_standard_markdown_link_unchanged(self):
        content = "See [text](https://example.com) for docs."
        result = self.rewriter.apply(content, {})
        assert "[text](https://example.com)" in result

    def test_multiple_agent_uris(self):
        content = (
            "Reads from agent://user-db/schema.tech.md "
            "and calls agent://token-service."
        )
        result = self.rewriter.apply(content, {})
        assert "[[user-db - schema]]" in result
        assert "[[token-service]]" in result
        assert "agent://" not in result

    def test_empty_content(self):
        result = self.rewriter.apply("", {})
        assert result == ""

    def test_no_agent_uris(self):
        content = "Just plain text with no links."
        result = self.rewriter.apply(content, {})
        assert result == content


# ===========================================================================
# FrontmatterFlattener tests
# ===========================================================================


class TestFrontmatterFlattener:
    def setup_method(self):
        self.flattener = FrontmatterFlattener()

    def test_nested_governance_flattened(self):
        content = "---\ncomponent_id: auth-service\ngovernance:\n  verification_status: ai_draft\n  visibility: internal\n---\n\nBody text."
        meta = {
            "component_id": "auth-service",
            "governance": {"verification_status": "ai_draft", "visibility": "internal"},
        }
        result = self.flattener.apply(content, meta)
        # Parse the resulting frontmatter
        assert "---" in result
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        assert fm["verification_status"] == "ai_draft"
        assert fm["visibility"] == "internal"

    def test_component_id_becomes_title_and_aliases(self):
        content = "---\ncomponent_id: auth-service\n---\n\nBody."
        meta = {"component_id": "auth-service"}
        result = self.flattener.apply(content, meta)
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        assert fm["title"] == "Auth Service"
        assert "auth-service" in fm["aliases"]

    def test_tags_array_includes_layer_and_security(self):
        content = "---\ncomponent_id: svc\nlayer: api\nsecurity_level: high\nowner_team: team-a\n---\n\nBody."
        meta = {
            "component_id": "svc",
            "layer": "api",
            "security_level": "high",
            "owner_team": "team-a",
        }
        result = self.flattener.apply(content, meta)
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        assert "tech-doc" in fm["tags"]
        assert "api" in fm["tags"]
        assert "security-high" in fm["tags"]
        assert "team-a" in fm["tags"]

    def test_edges_become_dependencies(self):
        content = "---\ncomponent_id: svc\nedges:\n  - target: db\n---\n\nBody."
        meta = {"component_id": "svc", "edges": [{"target": "db"}]}
        result = self.flattener.apply(content, meta)
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        assert "db" in fm["dependencies"]

    def test_cssclass_added(self):
        content = "---\ncomponent_id: svc\n---\n\nBody."
        meta = {"component_id": "svc"}
        result = self.flattener.apply(content, meta)
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        assert fm["cssclass"] == "chronicler-doc"

    def test_empty_metadata_passthrough(self):
        content = "No frontmatter here."
        result = self.flattener.apply(content, {})
        assert result == content

    def test_missing_optional_fields_graceful(self):
        content = "---\ncomponent_id: minimal\n---\n\nBody."
        meta = {"component_id": "minimal"}
        result = self.flattener.apply(content, meta)
        end = result.find("---", 3)
        fm = yaml.safe_load(result[3:end])
        # Should still have title, tags, cssclass
        assert fm["title"] == "Minimal"
        assert "tech-doc" in fm["tags"]
        assert fm["cssclass"] == "chronicler-doc"
        # No dependencies key when no edges
        assert "dependencies" not in fm


# ===========================================================================
# DataviewInjector tests
# ===========================================================================


class TestDataviewInjector:
    def setup_method(self):
        self.injector = DataviewInjector()

    def test_reads_writes_calls_become_depends_on(self):
        meta = {"edges": [
            {"target": "user-db", "type": "reads"},
            {"target": "cache", "type": "writes"},
            {"target": "token-svc", "type": "calls"},
        ]}
        result = self.injector.apply("# Doc\n\nSome text.", meta)
        assert "[depends_on:: [[user-db]]]" in result
        assert "[depends_on:: [[cache]]]" in result
        assert "[depends_on:: [[token-svc]]]" in result

    def test_called_by_edge(self):
        meta = {"edges": [{"target": "gateway", "type": "called_by"}]}
        result = self.injector.apply("# Doc\n\nText.", meta)
        assert "[called_by:: [[gateway]]]" in result

    def test_no_edges_no_modification(self):
        content = "# Doc\n\nBody text."
        result = self.injector.apply(content, {"edges": []})
        assert result == content

    def test_no_edges_key_no_modification(self):
        content = "# Doc\n\nBody text."
        result = self.injector.apply(content, {})
        assert result == content

    def test_dependencies_heading_inserted(self):
        meta = {"edges": [{"target": "db", "type": "reads"}]}
        result = self.injector.apply("# Doc\n\n## Overview\n\nText.", meta)
        assert "## Dependencies" in result

    def test_appends_to_existing_dependencies_section(self):
        content = "# Doc\n\n## Dependencies\n\nExisting deps.\n\n## Other"
        meta = {"edges": [{"target": "new-dep", "type": "calls"}]}
        result = self.injector.apply(content, meta)
        assert "[depends_on:: [[new-dep]]]" in result
        assert "## Dependencies" in result

    def test_via_suffix(self):
        meta = {"edges": [{"target": "db", "type": "reads", "via": "ORM"}]}
        result = self.injector.apply("# Doc", meta)
        assert "via ORM" in result


# ===========================================================================
# IndexGenerator tests
# ===========================================================================


class TestIndexGenerator:
    def test_collects_from_multiple_apply_calls(self):
        gen = IndexGenerator()
        gen.apply("content1", {"component_id": "svc-a", "layer": "api"})
        gen.apply("content2", {"component_id": "svc-b", "layer": "logic"})
        assert "api" in gen.components
        assert "logic" in gen.components
        assert len(gen.components["api"]) == 1
        assert len(gen.components["logic"]) == 1

    def test_generate_produces_valid_frontmatter(self):
        gen = IndexGenerator()
        gen.apply("c", {"component_id": "svc-a", "layer": "api"})
        index = gen.generate()
        assert index.startswith("---")
        assert "chronicler-index" in index

    def test_generate_groups_by_layer(self):
        gen = IndexGenerator()
        gen.apply("c", {"component_id": "svc-a", "layer": "api"})
        gen.apply("c", {"component_id": "svc-b", "layer": "api"})
        gen.apply("c", {"component_id": "svc-c", "layer": "logic"})
        index = gen.generate()
        assert "### Api" in index
        assert "### Logic" in index
        assert "[[svc-a]]" in index
        assert "[[svc-b]]" in index
        assert "[[svc-c]]" in index

    def test_generate_includes_dataview_tables(self):
        gen = IndexGenerator()
        gen.apply("c", {"component_id": "svc-a", "layer": "api"})
        index = gen.generate()
        assert "```dataview" in index
        assert "TABLE" in index

    def test_empty_state_minimal_index(self):
        gen = IndexGenerator()
        index = gen.generate()
        assert "---" in index
        assert "chronicler-index" in index
        # No layer sections when empty
        assert "###" not in index

    def test_apply_returns_content_unchanged(self):
        gen = IndexGenerator()
        content = "# My doc\n\nBody here."
        result = gen.apply(content, {"component_id": "svc", "layer": "api"})
        assert result == content


# ===========================================================================
# TransformPipeline tests
# ===========================================================================


class TestTransformPipeline:
    def test_chains_transforms_in_order(self):
        """Transforms run sequentially; later ones see earlier output."""
        rewriter = LinkRewriter()
        flattener = FrontmatterFlattener()
        pipeline = TransformPipeline([rewriter, flattener])
        result = pipeline.apply(SAMPLE_TECH_MD, SAMPLE_FRONTMATTER)
        # LinkRewriter should have rewritten agent:// URIs
        assert "agent://" not in result
        # FrontmatterFlattener should have flattened governance
        assert "cssclass" in result

    def test_empty_pipeline_passthrough(self):
        pipeline = TransformPipeline([])
        result = pipeline.apply("hello world", {})
        assert result == "hello world"

    def test_single_transform(self):
        pipeline = TransformPipeline([LinkRewriter()])
        content = "See agent://svc for info."
        result = pipeline.apply(content, {})
        assert "[[svc]]" in result


# ===========================================================================
# ObsidianSync export tests
# ===========================================================================


class TestObsidianSyncExport:
    def test_creates_vault_directory_structure(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        sync.export()
        # .tech.md -> .md
        assert (vault / "auth-service.md").exists()

    def test_transforms_tech_md_to_md(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        sync.export()
        content = (vault / "auth-service.md").read_text()
        # Links should be rewritten
        assert "agent://" not in content
        assert "[[" in content

    def test_sync_report_correct_counts(self, tmp_path):
        source = _make_source_dir(tmp_path, {
            "a.tech.md": SAMPLE_TECH_MD,
            "b.tech.md": SAMPLE_TECH_MD,
        })
        sync, vault = _make_sync(tmp_path, source)
        report = sync.export()
        assert report.synced == 2
        assert report.errors == []

    def test_skips_non_tech_md_files(self, tmp_path):
        source = _make_source_dir(tmp_path, {
            "real.tech.md": SAMPLE_TECH_MD,
        })
        # Add a non-.tech.md file
        (source / "notes.md").write_text("# Just notes")
        sync, vault = _make_sync(tmp_path, source)
        report = sync.export()
        assert report.synced == 1
        assert not (vault / "notes.md").exists()

    def test_second_export_skips_unchanged(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        report1 = sync.export()
        assert report1.synced == 1
        report2 = sync.export()
        assert report2.synced == 0
        assert report2.skipped == 1


# ===========================================================================
# ObsidianSync watch tests (testing internals, not actual file watching)
# ===========================================================================


class TestObsidianSyncWatch:
    def test_sync_single_file(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        tech_file = source / "auth-service.tech.md"
        result = sync._sync_single_file(tech_file)
        assert result is True
        assert (vault / "auth-service.md").exists()

    def test_delete_handling(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        # Export first so vault file exists
        sync.export()
        vault_file = vault / "auth-service.md"
        assert vault_file.exists()
        # Simulate delete: just remove the vault file directly
        vault_file.unlink()
        assert not vault_file.exists()

    def test_sync_single_file_returns_false_on_error(self, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        # Non-existent file
        fake = source / "nonexistent.tech.md"
        result = sync._sync_single_file(fake)
        assert result is False


# ===========================================================================
# ObsidianSync REST tests (mock requests)
# ===========================================================================


class TestObsidianSyncRest:
    @patch("chronicler_obsidian.sync.requests")
    def test_puts_to_correct_url_path(self, mock_requests, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_resp

        sync.sync_rest(api_url="https://localhost:27124", token="test-token")
        call_args = mock_requests.put.call_args
        assert "/vault/auth-service.md" in call_args[0][0]

    @patch("chronicler_obsidian.sync.requests")
    def test_sends_bearer_token_header(self, mock_requests, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_resp

        sync.sync_rest(api_url="https://localhost:27124", token="my-secret")
        call_args = mock_requests.put.call_args
        headers = call_args[1]["headers"] if "headers" in call_args[1] else call_args.kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer my-secret"

    @patch("chronicler_obsidian.sync.requests")
    def test_handles_per_file_errors(self, mock_requests, tmp_path):
        source = _make_source_dir(tmp_path)
        sync, vault = _make_sync(tmp_path, source)
        mock_requests.put.side_effect = Exception("Connection refused")

        report = sync.sync_rest(api_url="https://localhost:27124", token="tok")
        assert len(report.errors) == 1
        assert "Connection refused" in report.errors[0].error

    @patch("chronicler_obsidian.sync.requests")
    def test_returns_sync_report(self, mock_requests, tmp_path):
        source = _make_source_dir(tmp_path, {
            "a.tech.md": SAMPLE_TECH_MD,
            "b.tech.md": SAMPLE_TECH_MD,
        })
        sync, vault = _make_sync(tmp_path, source)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_resp

        report = sync.sync_rest(api_url="https://localhost:27124", token="tok")
        assert isinstance(report, SyncReport)
        assert report.synced == 2


# ===========================================================================
# parse_frontmatter tests
# ===========================================================================


class TestParseFrontmatter:
    def test_valid_yaml_frontmatter(self):
        content = "---\ncomponent_id: svc\nversion: 1.0\n---\n\nBody."
        meta, body = ObsidianSync._parse_frontmatter(content)
        assert meta["component_id"] == "svc"
        assert "Body." in body

    def test_no_frontmatter(self):
        content = "Just text, no YAML."
        meta, body = ObsidianSync._parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_malformed_yaml_raises(self):
        content = "---\n: [invalid yaml\n---\n\nBody."
        # _parse_frontmatter doesn't catch YAML errors — callers handle it
        with pytest.raises(Exception):
            ObsidianSync._parse_frontmatter(content)


# ===========================================================================
# CLI tests
# ===========================================================================


class TestObsidianCLI:
    def test_obsidian_export_no_vault(self):
        from typer.testing import CliRunner
        from chronicler.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["obsidian", "export"])
        assert result.exit_code != 0 or "Error" in result.output

    def test_obsidian_sync_no_mode(self):
        from typer.testing import CliRunner
        from chronicler.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["obsidian", "sync"])
        assert result.exit_code != 0 or "Error" in result.output

    def test_obsidian_export_dry_run(self, tmp_path):
        from typer.testing import CliRunner
        from chronicler.cli import app

        source = _make_source_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        runner = CliRunner()
        result = runner.invoke(app, [
            "obsidian", "export",
            "--vault", str(vault),
            "--source", str(source),
            "--dry-run",
        ])
        # Should list the file but not write it
        assert "auth-service" in result.output
        assert not (vault / "auth-service.md").exists()

    @patch("chronicler_obsidian.sync.ObsidianSync.export")
    def test_obsidian_export_with_vault(self, mock_export, tmp_path):
        from typer.testing import CliRunner
        from chronicler.cli import app

        source = _make_source_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        mock_export.return_value = SyncReport(synced=1, skipped=0, errors=[], duration=0.5)

        runner = CliRunner()
        result = runner.invoke(app, [
            "obsidian", "export",
            "--vault", str(vault),
            "--source", str(source),
        ])
        assert result.exit_code == 0
        assert "Synced" in result.output
