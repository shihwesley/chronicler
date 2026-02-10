"""Tests for the Merkle tree subsystem."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronicler_core.merkle import (
    MerkleDiff,
    MerkleNode,
    MerkleTree,
    build_tree,
    check_drift,
    compute_file_hash,
    compute_hash,
    compute_merkle_hash,
)


# ── Hash primitives ──────────────────────────────────────────────────


def test_compute_hash_deterministic():
    """Same input always produces the same output."""
    assert compute_hash(b"hello") == compute_hash(b"hello")


def test_compute_hash_12_chars():
    """Output is exactly 12 hex characters."""
    h = compute_hash(b"anything")
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_hash_different_inputs():
    """Different inputs produce different hashes."""
    assert compute_hash(b"a") != compute_hash(b"b")


def test_compute_file_hash(tmp_path: Path):
    """compute_file_hash reads a file and returns a 12-char hash."""
    f = tmp_path / "sample.txt"
    f.write_text("hello world")
    h = compute_file_hash(f)
    assert len(h) == 12
    # Should match hashing the same bytes directly
    assert h == compute_hash(b"hello world")


def test_compute_merkle_hash_sorted():
    """Child hashes are sorted before hashing, so order doesn't matter."""
    h1 = compute_merkle_hash(["aaa", "bbb", "ccc"])
    h2 = compute_merkle_hash(["ccc", "aaa", "bbb"])
    assert h1 == h2
    assert len(h1) == 12


# ── Tree build ───────────────────────────────────────────────────────


def _make_project(tmp_path: Path) -> Path:
    """Create a small project layout for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')")
    (tmp_path / "src" / "util.py").write_text("def helper(): pass")
    (tmp_path / "README.md").write_text("# Readme")
    return tmp_path


def test_build_tree_simple(tmp_path: Path):
    """Build a tree from a small project with a few files."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)

    # Should have leaf nodes for each file plus directory nodes
    assert "src/main.py" in tree.nodes
    assert "src/util.py" in tree.nodes
    assert "README.md" in tree.nodes
    # Directory nodes
    assert "src" in tree.nodes
    assert "" in tree.nodes  # root
    assert tree.root_hash == tree.nodes[""].hash


def test_build_tree_with_docs(tmp_path: Path):
    """Source files paired with .tech.md get doc_hash and doc_path set."""
    root = _make_project(tmp_path)
    doc_dir = root / ".chronicler"
    doc_dir.mkdir()
    (doc_dir / "src-main.tech.md").write_text("# Main docs")

    tree = MerkleTree.build(root, doc_dir=".chronicler")
    node = tree.nodes["src/main.py"]
    assert node.doc_hash is not None
    assert node.doc_path is not None
    assert node.doc_path.endswith(".tech.md")


def test_build_tree_ignores_patterns(tmp_path: Path):
    """Custom ignore patterns are respected."""
    root = _make_project(tmp_path)
    (root / "build").mkdir()
    (root / "build" / "output.js").write_text("compiled")
    # Also add a custom-ignored dir
    (root / "vendor").mkdir()
    (root / "vendor" / "lib.py").write_text("third party")

    tree = MerkleTree.build(root, ignore_patterns=["vendor"])
    assert "build/output.js" not in tree.nodes  # default ignore
    assert "vendor/lib.py" not in tree.nodes  # custom ignore


def test_build_tree_empty_dir(tmp_path: Path):
    """An empty directory produces a tree with just the root node."""
    tree = MerkleTree.build(tmp_path)
    # No file nodes, but the root hash should still be set
    assert tree.root_hash
    assert len(tree.root_hash) == 12


def test_build_tree_nested_dirs(tmp_path: Path):
    """Nested directory structure produces correct parent-child relationships."""
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "deep.py").write_text("deep")
    (tmp_path / "a" / "top.py").write_text("top")

    tree = MerkleTree.build(tmp_path)

    assert "a/b/c/deep.py" in tree.nodes
    assert "a/top.py" in tree.nodes
    # Directory nodes
    assert "a/b/c" in tree.nodes
    assert "a/b" in tree.nodes
    assert "a" in tree.nodes
    # Verify children lists
    assert "a/b/c/deep.py" in tree.nodes["a/b/c"].children


def test_build_tree_convenience_wrapper(tmp_path: Path):
    """The build_tree() shorthand works the same as MerkleTree.build()."""
    root = _make_project(tmp_path)
    tree = build_tree(root)
    assert tree.root_hash
    assert "README.md" in tree.nodes


# ── Drift detection ──────────────────────────────────────────────────


def test_check_drift_clean(tmp_path: Path):
    """No stale nodes when files haven't changed."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)
    stale = tree.check_drift()
    assert stale == []


def test_check_drift_stale(tmp_path: Path):
    """Modifying a source file after build marks it stale."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)

    # Mutate the file on disk
    (root / "src" / "main.py").write_text("print('changed')")

    stale = tree.check_drift()
    stale_paths = [n.path for n in stale]
    assert "src/main.py" in stale_paths
    # The node itself should be flagged
    assert tree.nodes["src/main.py"].stale is True


def test_check_drift_convenience_wrapper(tmp_path: Path):
    """The check_drift() shorthand returns the same result."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)
    (root / "README.md").write_text("changed")
    stale = check_drift(tree)
    assert len(stale) == 1
    assert stale[0].path == "README.md"


# ── Diff ─────────────────────────────────────────────────────────────


def test_diff_no_changes(tmp_path: Path):
    """Diffing identical trees reports nothing changed."""
    root = _make_project(tmp_path)
    t1 = MerkleTree.build(root)
    t2 = MerkleTree.build(root)
    d = t1.diff(t2)
    assert d.changed == []
    assert d.added == []
    assert d.removed == []
    assert d.root_changed is False


def test_diff_added_file(tmp_path: Path):
    """A new file shows up in diff.added."""
    root = _make_project(tmp_path)
    t1 = MerkleTree.build(root)

    (root / "new_file.py").write_text("new")
    t2 = MerkleTree.build(root)

    d = t1.diff(t2)
    assert "new_file.py" in d.added
    assert d.root_changed is True


def test_diff_removed_file(tmp_path: Path):
    """A deleted file shows up in diff.removed."""
    root = _make_project(tmp_path)
    t1 = MerkleTree.build(root)

    (root / "README.md").unlink()
    t2 = MerkleTree.build(root)

    d = t1.diff(t2)
    assert "README.md" in d.removed
    assert d.root_changed is True


def test_diff_changed_file(tmp_path: Path):
    """A modified file shows up in diff.changed and diff.stale."""
    root = _make_project(tmp_path)
    t1 = MerkleTree.build(root)

    (root / "src" / "util.py").write_text("def helper(): return 42")
    t2 = MerkleTree.build(root)

    d = t1.diff(t2)
    assert "src/util.py" in d.changed
    # No doc was updated, so it's stale too
    assert "src/util.py" in d.stale


# ── Serialization ────────────────────────────────────────────────────


def test_serialize_roundtrip(tmp_path: Path):
    """to_json -> from_json preserves all fields."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)

    restored = MerkleTree.from_json(tree.to_json())

    assert restored.root_hash == tree.root_hash
    assert restored.version == tree.version
    assert restored.algorithm == tree.algorithm
    assert set(restored.nodes.keys()) == set(tree.nodes.keys())

    for path, node in tree.nodes.items():
        rn = restored.nodes[path]
        assert rn.hash == node.hash
        assert rn.source_hash == node.source_hash
        assert rn.doc_hash == node.doc_hash
        assert rn.doc_path == node.doc_path
        assert rn.children == node.children
        assert rn.stale == node.stale


def test_save_load_roundtrip(tmp_path: Path):
    """save() + load() preserves all data through disk."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("import os")

    tree = MerkleTree.build(project)
    out = tmp_path / "tree.json"
    tree.save(out)

    loaded = MerkleTree.load(out)
    assert loaded.root_hash == tree.root_hash
    assert set(loaded.nodes.keys()) == set(tree.nodes.keys())


def test_serialized_json_is_valid(tmp_path: Path):
    """to_json() produces valid, parseable JSON."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)
    data = json.loads(tree.to_json())
    assert data["version"] == 1
    assert data["algorithm"] == "sha256"
    assert isinstance(data["nodes"], dict)


# ── update_node ──────────────────────────────────────────────────────


def test_update_node(tmp_path: Path):
    """update_node changes hashes and clears stale flag."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)

    node = tree.nodes["src/main.py"]
    node.stale = True
    tree.update_node("src/main.py", source_hash="aabbccddeeff", doc_hash="112233445566")
    assert node.source_hash == "aabbccddeeff"
    assert node.doc_hash == "112233445566"
    assert node.stale is False


def test_update_node_missing_raises(tmp_path: Path):
    """update_node raises KeyError for nonexistent paths."""
    root = _make_project(tmp_path)
    tree = MerkleTree.build(root)
    with pytest.raises(KeyError):
        tree.update_node("nonexistent.py", source_hash="abc")
