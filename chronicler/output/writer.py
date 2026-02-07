"""TechMdWriter — writes TechDoc models to .tech.md files on disk."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from chronicler.config.models import OutputConfig
from chronicler.drafter.models import TechDoc

logger = logging.getLogger(__name__)


def _sanitize_component_id(component_id: str) -> str:
    """Make a component_id safe for use as a filename.

    Replaces `/` with `--`, strips `..` segments, and removes characters
    that are problematic on common filesystems.
    """
    name = component_id.replace("/", "--")
    # Remove path traversal attempts
    name = name.replace("..", "")
    # Strip anything that isn't alphanumeric, dash, underscore, dot, or @
    name = re.sub(r"[^\w\-\.@]", "", name)
    # Collapse repeated dashes left over from substitutions
    name = re.sub(r"-{3,}", "--", name)
    # Don't allow empty or dot-only names
    if not name or name.strip(".") == "":
        name = "_unnamed"
    return name


class TechMdWriter:
    """Writes TechDoc instances to disk as .tech.md files.

    Handles filename sanitization, directory creation, optional index
    maintenance, and dry-run mode.
    """

    def __init__(self, config: OutputConfig) -> None:
        self.config = config
        self.base_dir = Path(config.base_dir)

    def write(self, tech_doc: TechDoc, *, dry_run: bool = False) -> Path:
        """Write a single TechDoc to disk.

        Returns the Path of the written (or would-be) file.
        """
        safe_name = _sanitize_component_id(tech_doc.component_id)
        dest = self.base_dir / f"{safe_name}.tech.md"

        if dry_run:
            logger.debug("dry-run: would write %s", dest)
            return dest

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tech_doc.raw_content, encoding="utf-8")
        logger.info("wrote %s (%d bytes)", dest, len(tech_doc.raw_content))

        if self.config.create_index:
            self._update_index(tech_doc.component_id, dest)

        return dest

    def write_batch(self, docs: list[TechDoc], *, dry_run: bool = False) -> list[Path]:
        """Write multiple TechDocs. Returns list of paths in input order."""
        return [self.write(doc, dry_run=dry_run) for doc in docs]

    # -- index management --------------------------------------------------

    def _update_index(self, component_id: str, path: Path) -> None:
        """Upsert an entry in _index.yaml for the written file."""
        index_path = self.base_dir / "_index.yaml"

        entries: list[dict] = []
        if index_path.exists():
            raw = index_path.read_text(encoding="utf-8")
            loaded = yaml.safe_load(raw)
            if isinstance(loaded, list):
                entries = loaded

        # Upsert: replace existing entry for same component_id
        entries = [e for e in entries if e.get("component_id") != component_id]
        entries.append({
            "component_id": component_id,
            "path": str(path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        index_path.write_text(
            yaml.safe_dump(entries, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        logger.debug("updated index %s (%d entries)", index_path, len(entries))
