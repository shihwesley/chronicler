"""Mercator-AI scanner integration with built-in fallback."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from chronicler_core.config.models import MerkleConfig
from chronicler_core.merkle.tree import compute_file_hash, _matches_any

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Output of a codebase scan (Mercator or fallback)."""

    files: dict[str, str]  # path -> hash
    total_tokens: int | None = None
    merkle_root_hash: str = ""


@dataclass
class DiffResult:
    """Output of a diff against a previous manifest."""

    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    has_changes: bool = False


# Known locations where Mercator's scan-codebase.py might live
_MERCATOR_SCRIPT = "skills/mercator-ai/scripts/scan-codebase.py"
_MERCATOR_GLOB = ".claude/plugins/cache/**/mercator-ai/*/skills/mercator-ai/scripts/scan-codebase.py"


class MercatorScanner:
    """Discovers and shells out to Mercator-AI, falling back to a built-in walker."""

    def __init__(self, config: MerkleConfig) -> None:
        self.config = config
        self._mercator_path: Path | None = None
        self._searched = False

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_mercator(self) -> Path | None:
        """Try to locate scan-codebase.py from known install locations.

        Checks in order:
        1. config.mercator_path (explicit override)
        2. $CLAUDE_PLUGIN_ROOT/skills/mercator-ai/scripts/scan-codebase.py
        3. ~/.claude/plugins/cache/**/mercator-ai/.../scan-codebase.py
        """
        if self._searched:
            return self._mercator_path
        self._searched = True

        # 1. Explicit config path
        if self.config.mercator_path:
            p = Path(self.config.mercator_path)
            # Validate mercator_path is absolute, exists, and is a file
            if not p.is_absolute():
                logger.warning("mercator_path must be absolute: %s", p)
            elif not p.exists():
                logger.warning("mercator_path does not exist: %s", p)
            elif p.is_dir():
                logger.warning("mercator_path is a directory, not a file: %s", p)
            elif p.is_file():
                self._mercator_path = p
                return p

        # 2. $CLAUDE_PLUGIN_ROOT
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if plugin_root:
            candidate = Path(plugin_root) / _MERCATOR_SCRIPT
            if candidate.is_file():
                self._mercator_path = candidate
                return candidate

        # 3. Glob ~/.claude/plugins/cache
        home = Path.home()
        matches = sorted(home.glob(_MERCATOR_GLOB))
        if matches:
            self._mercator_path = matches[-1]  # newest
            return self._mercator_path

        return None

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan(self, root: Path) -> ScanResult:
        """Scan a directory. Uses Mercator if available, else built-in fallback."""
        script = self.discover_mercator()
        if script is not None:
            return self._mercator_scan(script, root)
        return self._fallback_scan(root)

    def _mercator_scan(self, script: Path, root: Path) -> ScanResult:
        """Run scan-codebase.py and parse its JSON output."""
        try:
            result = subprocess.run(
                ["uv", "run", str(script), str(root), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            logger.warning("uv not found, falling back to built-in scanner")
            return self._fallback_scan(root)
        except subprocess.TimeoutExpired:
            logger.warning("Mercator scan timed out, falling back to built-in scanner")
            return self._fallback_scan(root)

        if result.returncode != 0:
            logger.warning(
                "Mercator exited %d: %s — falling back",
                result.returncode,
                result.stderr[:200],
            )
            return self._fallback_scan(root)

        return self._parse_scan_json(result.stdout)

    def _parse_scan_json(self, raw: str) -> ScanResult:
        """Parse Mercator JSON output into a ScanResult."""
        data = json.loads(raw)
        files: dict[str, str] = {}
        for entry in data.get("files", []):
            files[entry["path"]] = entry["hash"]
        return ScanResult(
            files=files,
            total_tokens=data.get("total_tokens"),
            merkle_root_hash=data.get("merkle_root_hash", ""),
        )

    def _fallback_scan(self, root: Path) -> ScanResult:
        """Walk directory with ignore patterns, hash each file."""
        root = root.resolve()
        ignore = set(self.config.ignore_patterns)
        files: dict[str, str] = {}

        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if _matches_any(rel, ignore):
                continue
            files[str(rel)] = compute_file_hash(p)

        return ScanResult(files=files)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self, root: Path, manifest_path: Path) -> DiffResult:
        """Diff current state against a saved manifest JSON.

        If Mercator is available, shells out with --diff. Otherwise
        compares the manifest against a fresh fallback scan.
        """
        script = self.discover_mercator()
        if script is not None:
            return self._mercator_diff(script, root, manifest_path)
        return self._fallback_diff(root, manifest_path)

    def _mercator_diff(
        self, script: Path, root: Path, manifest_path: Path
    ) -> DiffResult:
        """Run scan-codebase.py --diff and parse its output."""
        try:
            result = subprocess.run(
                [
                    "uv", "run", str(script),
                    str(root), "--diff", str(manifest_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return self._fallback_diff(root, manifest_path)

        if result.returncode != 0:
            return self._fallback_diff(root, manifest_path)

        return self._parse_diff_json(result.stdout)

    def _parse_diff_json(self, raw: str) -> DiffResult:
        """Parse Mercator diff JSON into a DiffResult."""
        data = json.loads(raw)
        changed = data.get("changed", [])
        added = data.get("added", [])
        removed = data.get("removed", [])
        return DiffResult(
            changed=changed,
            added=added,
            removed=removed,
            has_changes=bool(changed or added or removed),
        )

    def _fallback_diff(self, root: Path, manifest_path: Path) -> DiffResult:
        """Compare a fresh scan against the file hashes in a manifest."""
        current = self._fallback_scan(root)

        try:
            old_data = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to parse manifest %s: %s — treating as empty",
                manifest_path,
                e,
            )
            # Treat as empty manifest — all current files are "added"
            return DiffResult(
                changed=[],
                added=sorted(current.files.keys()),
                removed=[],
                has_changes=bool(current.files),
            )

        # Extract old file hashes (support both flat dict and files-list formats)
        old_files: dict[str, str] = {}
        if isinstance(old_data.get("files"), list):
            for entry in old_data["files"]:
                old_files[entry["path"]] = entry["hash"]
        elif isinstance(old_data.get("files"), dict):
            old_files = old_data["files"]
        elif isinstance(old_data.get("nodes"), dict):
            # MerkleTree JSON format
            for path, node in old_data["nodes"].items():
                if node.get("source_hash"):
                    old_files[path] = node["source_hash"]

        old_keys = set(old_files)
        new_keys = set(current.files)

        added = sorted(new_keys - old_keys)
        removed = sorted(old_keys - new_keys)
        changed = [
            p for p in sorted(old_keys & new_keys)
            if old_files[p] != current.files[p]
        ]

        return DiffResult(
            changed=changed,
            added=added,
            removed=removed,
            has_changes=bool(changed or added or removed),
        )
