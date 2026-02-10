"""Key file identification and summarization."""

from __future__ import annotations

import json


class KeyFileLocator:
    """Locates and summarizes key files from crawl data."""

    @staticmethod
    def find(key_files: dict[str, str], name: str) -> str:
        """Case-insensitive lookup in key_files dict by basename."""
        lower = name.lower()
        for path, content in key_files.items():
            basename = path.rsplit("/", 1)[-1]
            if basename.lower() == lower:
                return content
        return ""

    @staticmethod
    def extract_package_json_deps(key_files: dict[str, str]) -> str:
        """Extract dependencies (not devDeps) from package.json as JSON string."""
        raw = KeyFileLocator.find(key_files, "package.json")
        if not raw:
            return ""
        try:
            data = json.loads(raw)
            deps = data.get("dependencies", {})
            if deps:
                return json.dumps(deps, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    @staticmethod
    def format_converted_docs(converted: dict[str, str]) -> str:
        """Summarize converted documents with char counts."""
        if not converted:
            return ""
        parts = [f"{path} ({len(content)} chars)" for path, content in converted.items()]
        return "Converted documents: " + ", ".join(parts)
