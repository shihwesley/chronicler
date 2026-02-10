"""Tests for merkle-related CLI commands (check, draft --stale, blast-radius)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from chronicler.cli import app
from chronicler_core.merkle import MerkleTree

runner = CliRunner()


def _make_project(root: Path) -> None:
    """Create a minimal project structure with source files."""
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')")
    (root / "src" / "util.py").write_text("def helper(): pass")
    (root / "README.md").write_text("# My project")


def _build_and_save_merkle(root: Path) -> MerkleTree:
    """Build a merkle tree and save it to .chronicler/.merkle.json."""
    tree = MerkleTree.build(root, doc_dir=".chronicler")
    merkle_dir = root / ".chronicler"
    merkle_dir.mkdir(exist_ok=True)
    tree.save(merkle_dir / ".merkle.json")
    return tree


def _make_tech_md(chronicler_dir: Path, component_id: str, edges: list[dict] | None = None) -> Path:
    """Write a .tech.md file with YAML frontmatter containing optional edges."""
    fm = {
        "component_id": component_id,
        "version": "0.1.0",
        "edges": edges or [],
    }
    content = f"---\n{yaml.dump(fm, default_flow_style=False)}---\n\n# {component_id}\n"
    safe_name = component_id.replace("/", "--")
    path = chronicler_dir / f"{safe_name}.tech.md"
    path.write_text(content)
    return path


# ── chronicler check ─────────────────────────────────────────────────


def test_check_no_merkle_json(tmp_path: Path):
    """First run with no .merkle.json builds the tree and reports first scan."""
    _make_project(tmp_path)
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    assert "First scan" in result.output
    # Should have created the merkle file
    assert (tmp_path / ".chronicler" / ".merkle.json").is_file()


def test_check_all_clean(tmp_path: Path):
    """When no files changed, check reports everything is ok."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower() or "ok" in result.output.lower()


def test_check_with_stale_docs(tmp_path: Path):
    """When a source file changes after build, check reports it as stale."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    # Modify a source file
    (tmp_path / "src" / "main.py").write_text("print('changed!')")

    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    assert "stale" in result.output.lower()


def test_check_ci_mode(tmp_path: Path):
    """CI mode outputs plain text, not Rich formatting."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)
    (tmp_path / "src" / "main.py").write_text("print('changed!')")

    result = runner.invoke(app, ["check", "--ci", str(tmp_path)])
    assert result.exit_code == 0
    assert "STALE" in result.output
    assert "root_hash=" in result.output


def test_check_ci_mode_clean(tmp_path: Path):
    """CI mode with no stale docs outputs OK."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["check", "--ci", str(tmp_path)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_check_fail_on_stale_exit_code(tmp_path: Path):
    """--fail-on-stale causes exit code 1 when stale docs exist."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)
    (tmp_path / "README.md").write_text("# Changed")

    result = runner.invoke(app, ["check", "--fail-on-stale", str(tmp_path)])
    assert result.exit_code == 1


def test_check_fail_on_stale_clean(tmp_path: Path):
    """--fail-on-stale exits 0 when everything is clean."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["check", "--fail-on-stale", str(tmp_path)])
    assert result.exit_code == 0


# ── draft --stale ────────────────────────────────────────────────────


def test_draft_stale_flag_no_stale_docs(tmp_path: Path):
    """draft --stale with no changes reports all docs up to date."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["draft", str(tmp_path), "--stale"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


def test_draft_stale_flag_with_stale_docs(tmp_path: Path):
    """draft --stale with changed files identifies them and updates merkle tree."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    (tmp_path / "src" / "util.py").write_text("def helper(): return 42")

    result = runner.invoke(app, ["draft", str(tmp_path), "--stale"])
    assert result.exit_code == 0
    assert "stale" in result.output.lower()
    assert "src/util.py" in result.output
    assert "Merkle tree updated" in result.output


def test_draft_stale_updates_hashes(tmp_path: Path):
    """After draft --stale, running check should show no stale docs."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    (tmp_path / "src" / "main.py").write_text("print('v2')")
    # Run draft --stale to update hashes
    runner.invoke(app, ["draft", str(tmp_path), "--stale"])

    # Now check should be clean
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0
    # Should not contain "stale" in the output (Rich table marks things as "ok")
    assert "stale" not in result.output.lower().replace("--fail-on-stale", "")


# ── blast-radius ─────────────────────────────────────────────────────


def test_blast_radius_no_merkle_json(tmp_path: Path):
    """blast-radius without a merkle tree exits with error."""
    result = runner.invoke(app, ["blast-radius", "--changed", "foo.py", str(tmp_path)])
    assert result.exit_code == 1
    assert "No .merkle.json" in result.output


def test_blast_radius_file_not_in_tree(tmp_path: Path):
    """blast-radius for a file not in the tree exits with error."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["blast-radius", "--changed", "nonexistent.py", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_blast_radius_no_edges(tmp_path: Path):
    """blast-radius with no edge graph shows no downstream impact."""
    _make_project(tmp_path)
    _build_and_save_merkle(tmp_path)

    result = runner.invoke(app, ["blast-radius", "--changed", "src/main.py", str(tmp_path)])
    assert result.exit_code == 0
    assert "No downstream impact" in result.output or "none" in result.output.lower()


def test_blast_radius_direct_impact(tmp_path: Path):
    """blast-radius shows direct impact component."""
    _make_project(tmp_path)
    tree = _build_and_save_merkle(tmp_path)

    # Create .tech.md with edges
    chronicler_dir = tmp_path / ".chronicler"
    chronicler_dir.mkdir(exist_ok=True)
    _make_tech_md(chronicler_dir, "my-app", edges=[
        {"target": "auth-service", "type": "calls"},
    ])

    result = runner.invoke(app, ["blast-radius", "--changed", "src/main.py", str(tmp_path)])
    assert result.exit_code == 0
    assert "Blast radius" in result.output
    assert "Direct impact" in result.output


def test_blast_radius_one_hop(tmp_path: Path):
    """blast-radius shows 1-hop dependencies through edge graph."""
    _make_project(tmp_path)

    # Create a doc paired with src/main.py
    chronicler_dir = tmp_path / ".chronicler"
    chronicler_dir.mkdir(exist_ok=True)
    _make_tech_md(chronicler_dir, "my-app", edges=[
        {"target": "auth-service", "type": "calls"},
    ])
    _make_tech_md(chronicler_dir, "auth-service", edges=[
        {"target": "db-layer", "type": "depends_on"},
    ])

    # Build merkle with the doc dir present so src/main.py might get paired
    tree = MerkleTree.build(tmp_path, doc_dir=".chronicler")
    tree.save(chronicler_dir / ".merkle.json")

    # Manually set doc_path on the main.py node so blast-radius can find the component
    node = tree.nodes.get("src/main.py")
    if node:
        node.doc_path = ".chronicler/my-app.tech.md"
        tree.save(chronicler_dir / ".merkle.json")

    result = runner.invoke(app, ["blast-radius", "--changed", "src/main.py", str(tmp_path)])
    assert result.exit_code == 0
    assert "auth-service" in result.output
