"""StoragePlugin implementation backed by MemVid .mv2 files."""

from __future__ import annotations

from pathlib import Path

import yaml
from memvid_sdk import Memvid

from chronicler_core.interfaces.storage import SearchResult


class MemVidStorage:
    """StoragePlugin implementation backed by MemVid .mv2 files.

    Opens an existing .mv2 file or creates one from scratch.
    All writes are committed immediately so callers don't need to
    think about flush semantics.
    """

    def __init__(
        self,
        path: str = ".chronicler/chronicler.mv2",
        embedding: str = "bge-small",
    ) -> None:
        self._path = path
        self._embedding = embedding

        if Path(path).exists():
            self._mem = Memvid.use(kind="basic", path=path)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._mem = Memvid.create(path=path, kind="basic")

    # -- StoragePlugin protocol ------------------------------------------------

    def store(self, doc_id: str, content: str, metadata: dict) -> None:
        """Write a document into the .mv2 file."""
        self._mem.put(
            text=content,
            title=doc_id,
            label="tech.md",
            metadata=metadata,
        )
        self._mem.commit()

    def search(
        self, query: str, k: int = 10, mode: str = "auto"
    ) -> list[SearchResult]:
        """Run a hybrid/lex/vec search and return SearchResult objects."""
        raw_results = self._mem.find(query, k=k, mode=mode)
        return [
            SearchResult(
                doc_id=r.get("title", ""),
                content=r.get("text", ""),
                score=r.get("score", 0.0),
                metadata=r.get("metadata", {}),
            )
            for r in raw_results
        ]

    def get(self, doc_id: str) -> str | None:
        """Exact-match lookup by doc_id using lexical search."""
        results = self._mem.find(doc_id, k=1, mode="lex")
        if not results:
            return None
        hit = results[0]
        if hit.get("title") == doc_id:
            return hit.get("text")
        return None

    def state(self, entity: str) -> dict:
        """O(1) SPO lookup for a named entity."""
        return self._mem.state(entity)

    # -- Extended operations ---------------------------------------------------

    def enrich_from_frontmatter(
        self, doc_id: str, edges: list[dict]
    ) -> None:
        """Convert YAML frontmatter edges to memory cards and commit them.

        Each edge dict should have at least 'entity', 'slot', and 'value' keys.
        """
        cards = [
            {
                "entity": edge.get("entity", doc_id),
                "slot": edge["slot"],
                "value": edge["value"],
            }
            for edge in edges
        ]
        if cards:
            self._mem.add_memory_cards(cards)
            self._mem.commit()

    def rebuild(self, tech_md_dir: str) -> None:
        """Rebuild the .mv2 file from all .tech.md files in a directory.

        Parses YAML frontmatter from each file, stores the body text,
        and enriches with any edges found in the frontmatter.
        """
        md_dir = Path(tech_md_dir)
        for md_path in sorted(md_dir.glob("*.tech.md")):
            raw = md_path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(raw)
            doc_id = md_path.stem  # "foo.tech" from "foo.tech.md"
            metadata = frontmatter if frontmatter else {}

            self.store(doc_id, body, metadata)

            edges = metadata.get("edges", [])
            if edges:
                self.enrich_from_frontmatter(doc_id, edges)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter dict, body text).

    Expects optional YAML frontmatter between '---' fences at the top.
    Returns ({}, full_text) when no frontmatter is found.
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, text

    if not isinstance(fm, dict):
        return {}, text

    return fm, parts[2].lstrip("\n")
