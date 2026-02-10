"""Extensible dependency parsing via registry pattern.

Adding a new manifest type (e.g., Cargo.toml) requires only defining a new
parser class and appending an instance to PARSERS.
"""

from __future__ import annotations

import json
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class DependencyParser(Protocol):
    """Protocol for manifest file parsers."""

    file_pattern: str

    def parse(self, content: str) -> list[str]:
        """Extract dependency names from file content."""
        ...


class RequirementsTxtParser:
    """Parses requirements.txt files."""

    file_pattern = "requirements.txt"

    def parse(self, content: str) -> list[str]:
        names: list[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[>=<!\[;]", line, maxsplit=1)[0].strip()
            if name:
                names.append(name)
        return names


class PyprojectTomlParser:
    """Parses pyproject.toml dependency lists."""

    file_pattern = "pyproject.toml"

    def parse(self, content: str) -> list[str]:
        names: list[str] = []
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies") and "=" in stripped:
                in_deps = True
                bracket_content = stripped.split("=", 1)[1].strip()
                if bracket_content.startswith("["):
                    for item in re.findall(r'"([^"]+)"', bracket_content):
                        name = re.split(r"[>=<!\[;]", item, maxsplit=1)[0].strip()
                        if name:
                            names.append(name)
                    if "]" in bracket_content:
                        in_deps = False
                continue
            if in_deps:
                if "]" in stripped:
                    for item in re.findall(r'"([^"]+)"', stripped):
                        name = re.split(r"[>=<!\[;]", item, maxsplit=1)[0].strip()
                        if name:
                            names.append(name)
                    in_deps = False
                    continue
                for item in re.findall(r'"([^"]+)"', stripped):
                    name = re.split(r"[>=<!\[;]", item, maxsplit=1)[0].strip()
                    if name:
                        names.append(name)
        return names


class PackageJsonParser:
    """Parses package.json dependency objects."""

    file_pattern = "package.json"

    def parse(self, content: str) -> list[str]:
        try:
            data = json.loads(content)
            return list(data.get("dependencies", {}).keys())
        except (json.JSONDecodeError, TypeError):
            return []


# Registry: add new parsers here. Order determines precedence when
# the same dependency appears in multiple manifests.
PARSERS: list[DependencyParser] = [
    PackageJsonParser(),
    PyprojectTomlParser(),
    RequirementsTxtParser(),
]
