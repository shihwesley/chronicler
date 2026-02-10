"""Tests for the output subsystem: writer and validator."""

import pytest
import yaml
from pathlib import Path

from chronicler_core.config.models import OutputConfig
from chronicler_core.drafter.models import FrontmatterModel, GovernanceModel, TechDoc
from chronicler_core.output.writer import TechMdWriter, _sanitize_component_id
from chronicler_core.output.validator import (
    TechMdValidator,
    ValidationResult,
    _split_frontmatter,
)


# ---------------------------------------------------------------------------
# _sanitize_component_id
# ---------------------------------------------------------------------------


class TestSanitizeComponentId:
    def test_replaces_slash_with_double_dash(self):
        assert _sanitize_component_id("acme/widget") == "acme--widget"

    def test_strips_dot_dot(self):
        result = _sanitize_component_id("../../etc/passwd")
        assert ".." not in result

    def test_removes_unsafe_chars(self):
        result = _sanitize_component_id("my<repo>name")
        assert "<" not in result
        assert ">" not in result

    def test_collapses_dashes(self):
        result = _sanitize_component_id("a////b")
        # / -> -- each, so a----b, then collapse 3+ dashes to --
        assert "---" not in result

    def test_empty_becomes_unnamed(self):
        assert _sanitize_component_id("") == "_unnamed"

    def test_dots_only_becomes_unnamed(self):
        assert _sanitize_component_id("...") == "_unnamed"

    def test_normal_id_unchanged(self):
        assert _sanitize_component_id("my-service") == "my-service"

    def test_at_sign_preserved(self):
        result = _sanitize_component_id("@scope/package")
        assert "@" in result


# ---------------------------------------------------------------------------
# TechMdWriter
# ---------------------------------------------------------------------------


class TestTechMdWriter:
    def _make_tech_doc(self, component_id="test/repo"):
        fm = FrontmatterModel(
            component_id=component_id,
            version="0.1.0",
            layer="logic",
            governance=GovernanceModel(verification_status="ai_draft"),
        )
        yaml_str = yaml.dump(fm.model_dump(), default_flow_style=False, sort_keys=False)
        raw = f"---\n{yaml_str}---\n\n# {component_id}\n\nSome content.\n"
        return TechDoc(
            component_id=component_id,
            frontmatter=fm,
            raw_content=raw,
        )

    def test_write_creates_file(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        path = writer.write(doc)
        assert path.exists()
        assert path.suffix == ".md"
        assert path.stem.endswith(".tech")

    def test_write_content_matches(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        path = writer.write(doc)
        content = path.read_text(encoding="utf-8")
        assert content == doc.raw_content

    def test_dry_run_no_file(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        path = writer.write(doc, dry_run=True)
        assert not path.exists()

    def test_dry_run_returns_path(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        path = writer.write(doc, dry_run=True)
        assert isinstance(path, Path)
        assert str(path).endswith(".tech.md")

    def test_creates_index(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=True)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        writer.write(doc)
        index_path = tmp_path / "_index.yaml"
        assert index_path.exists()

        entries = yaml.safe_load(index_path.read_text())
        assert isinstance(entries, list)
        assert len(entries) == 1
        assert entries[0]["component_id"] == "test/repo"

    def test_index_upsert(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=True)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        writer.write(doc)
        writer.write(doc)  # second write for same component

        index_path = tmp_path / "_index.yaml"
        entries = yaml.safe_load(index_path.read_text())
        assert len(entries) == 1  # upserted, not duplicated

    def test_write_batch(self, tmp_path):
        config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(config)
        docs = [self._make_tech_doc("a/b"), self._make_tech_doc("c/d")]

        paths = writer.write_batch(docs)
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        config = OutputConfig(base_dir=str(nested), create_index=False)
        writer = TechMdWriter(config)
        doc = self._make_tech_doc()

        path = writer.write(doc)
        assert path.exists()


# ---------------------------------------------------------------------------
# _split_frontmatter
# ---------------------------------------------------------------------------


class TestSplitFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\nfoo: bar\n---\n\nbody here"
        yaml_str, body = _split_frontmatter(content)
        assert yaml_str == "foo: bar"
        assert "body here" in body

    def test_no_frontmatter(self):
        content = "just plain content"
        yaml_str, body = _split_frontmatter(content)
        assert yaml_str is None
        assert body == content

    def test_no_closing_marker(self):
        content = "---\nfoo: bar\nno closing"
        yaml_str, body = _split_frontmatter(content)
        assert yaml_str is None


# ---------------------------------------------------------------------------
# TechMdValidator
# ---------------------------------------------------------------------------


class TestTechMdValidator:
    def _valid_content(self):
        fm = {
            "component_id": "test/repo",
            "version": "0.1.0",
            "layer": "logic",
            "governance": {
                "verification_status": "ai_draft",
                "visibility": "internal",
            },
        }
        yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n\n# test/repo\n"

    def test_valid_content_strict(self):
        v = TechMdValidator(mode="strict")
        result = v.validate_content(self._valid_content())
        assert result.valid is True
        assert result.errors == []

    def test_missing_component_id(self):
        content = "---\nversion: '0.1.0'\nlayer: logic\ngovernance:\n  verification_status: ai_draft\n---\nbody"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("component_id" in e for e in result.errors)

    def test_missing_version(self):
        content = "---\ncomponent_id: test\nlayer: logic\ngovernance:\n  verification_status: ai_draft\n---\n"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("version" in e for e in result.errors)

    def test_missing_layer(self):
        content = "---\ncomponent_id: test\nversion: '0.1.0'\ngovernance:\n  verification_status: ai_draft\n---\n"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("layer" in e for e in result.errors)

    def test_wrong_verification_status(self):
        content = "---\ncomponent_id: test\nversion: '0.1.0'\nlayer: logic\ngovernance:\n  verification_status: human_verified\n---\n"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("verification_status" in e for e in result.errors)

    def test_missing_governance(self):
        content = "---\ncomponent_id: test\nversion: '0.1.0'\nlayer: logic\n---\n"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("verification_status" in e for e in result.errors)

    def test_no_frontmatter(self):
        v = TechMdValidator(mode="strict")
        result = v.validate_content("just text, no yaml")
        assert result.valid is False
        assert any("frontmatter" in e.lower() for e in result.errors)

    def test_invalid_yaml(self):
        v = TechMdValidator(mode="strict")
        result = v.validate_content("---\n: :\n  invalid yaml [[\n---\n")
        assert result.valid is False

    def test_warn_mode_stays_valid(self):
        content = "---\nversion: '0.1.0'\nlayer: logic\n---\n"  # missing component_id
        v = TechMdValidator(mode="warn")
        result = v.validate_content(content)
        assert result.valid is True
        assert len(result.warnings) > 0

    def test_off_mode_skips_validation(self):
        v = TechMdValidator(mode="off")
        result = v.validate_content("garbage content")
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown validation mode"):
            TechMdValidator(mode="invalid")

    def test_validate_file(self, tmp_path):
        v = TechMdValidator(mode="strict")
        content = self._valid_content()
        f = tmp_path / "test.tech.md"
        f.write_text(content, encoding="utf-8")

        result = v.validate_file(f)
        assert result.valid is True

    def test_validate_file_not_found(self, tmp_path):
        v = TechMdValidator(mode="strict")
        result = v.validate_file(tmp_path / "nope.tech.md")
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_validate_directory(self, tmp_path):
        v = TechMdValidator(mode="strict")
        content = self._valid_content()

        (tmp_path / "a.tech.md").write_text(content)
        (tmp_path / "b.tech.md").write_text(content)

        results = v.validate_directory(tmp_path)
        assert len(results) == 2
        assert all(r.valid for r in results)

    def test_validate_directory_not_a_dir(self, tmp_path):
        v = TechMdValidator(mode="strict")
        results = v.validate_directory(tmp_path / "nonexistent")
        assert len(results) == 1
        assert results[0].valid is False

    def test_validate_directory_empty(self, tmp_path):
        v = TechMdValidator(mode="strict")
        results = v.validate_directory(tmp_path)
        assert results == []

    def test_type_mismatch_component_id(self):
        content = "---\ncomponent_id: 123\nversion: '0.1.0'\nlayer: logic\ngovernance:\n  verification_status: ai_draft\n---\n"
        v = TechMdValidator(mode="strict")
        result = v.validate_content(content)
        assert result.valid is False
        assert any("component_id" in e for e in result.errors)
