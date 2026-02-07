"""Context builder: transforms CrawlResult into PromptContext for LLM consumption."""

from __future__ import annotations

import json
import re
from collections import defaultdict

from chronicler.drafter.models import PromptContext
from chronicler.vcs.models import CrawlResult, FileNode

# Priority tiers for file tree ordering (lower = higher priority).
_PRIORITY_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(^|/)package\.json$"), 0),
    (re.compile(r"(^|/)pyproject\.toml$"), 0),
    (re.compile(r"(^|/)Cargo\.toml$"), 0),
    (re.compile(r"(^|/)go\.mod$"), 0),
    (re.compile(r"(^|/)Dockerfile"), 1),
    (re.compile(r"(^|/)\.github/workflows/"), 1),
    (re.compile(r"(^|/)\.gitlab-ci"), 1),
    (re.compile(r"(^|/)(src|lib|app)/"), 2),
]

_MAX_TREE_FILES = 50


class ContextBuilder:
    """Transforms VCS crawl data into structured LLM prompt context."""

    @staticmethod
    def from_crawl_result(result: CrawlResult) -> PromptContext:
        """Build PromptContext from a CrawlResult."""
        languages = _format_languages(result.metadata.languages)
        topics = ", ".join(result.metadata.topics)
        file_tree = _format_file_tree(result.tree)
        readme = _find_key_file(result.key_files, "README.md")
        pkg_json = _extract_package_json_deps(result.key_files)
        dockerfile = _find_key_file(result.key_files, "Dockerfile")
        deps = _build_dependencies_list(result.key_files)
        docs_summary = _format_converted_docs(result.converted_docs)

        return PromptContext(
            repo_name=result.metadata.name,
            description=result.metadata.description or "",
            default_branch=result.metadata.default_branch,
            languages=languages,
            topics=topics,
            file_tree=file_tree,
            readme_content=readme,
            package_json=pkg_json,
            dockerfile=dockerfile,
            dependencies_list=deps,
            converted_docs_summary=docs_summary,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_languages(langs: dict[str, int]) -> str:
    """Sort languages by bytes descending, return comma-separated names."""
    if not langs:
        return ""
    sorted_langs = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
    return ", ".join(name for name, _ in sorted_langs)


def _file_priority(path: str) -> tuple[int, str]:
    """Return (priority_tier, path) for sorting. Lower tier = more important."""
    for pattern, tier in _PRIORITY_PATTERNS:
        if pattern.search(path):
            return (tier, path)
    return (9, path)


def _format_file_tree(tree: list[FileNode]) -> str:
    """Format FileNode list as indented text tree, limited to _MAX_TREE_FILES files."""
    files = [n for n in tree if n.type == "file"]
    files.sort(key=lambda n: _file_priority(n.path))
    files = files[:_MAX_TREE_FILES]

    # Collect directories that contain selected files.
    dirs_with_files: set[str] = set()
    for f in files:
        parts = f.path.split("/")
        for i in range(1, len(parts)):
            dirs_with_files.add("/".join(parts[:i]))

    # Build ordered lines: insert directory entries before their children.
    seen_dirs: set[str] = set()
    lines: list[str] = []

    # Sort selected files alphabetically for the final output.
    files.sort(key=lambda n: n.path)

    for f in files:
        parts = f.path.split("/")
        # Ensure parent dirs are emitted first.
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            if d not in seen_dirs:
                seen_dirs.add(d)
                depth = i - 1
                lines.append("  " * depth + parts[i - 1] + "/")
        # Emit the file itself.
        depth = len(parts) - 1
        lines.append("  " * depth + parts[-1])

    return "\n".join(lines)


def _find_key_file(key_files: dict[str, str], name: str) -> str:
    """Case-insensitive lookup in key_files dict."""
    lower = name.lower()
    for path, content in key_files.items():
        # Match against the basename.
        basename = path.rsplit("/", 1)[-1]
        if basename.lower() == lower:
            return content
    return ""


def _extract_package_json_deps(key_files: dict[str, str]) -> str:
    """Extract dependencies (not devDeps) from package.json, return as JSON string."""
    raw = _find_key_file(key_files, "package.json")
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


def _parse_requirements_txt(content: str) -> list[str]:
    """Extract package names from requirements.txt content."""
    names: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip version specifiers: "requests>=2.0" -> "requests"
        name = re.split(r"[>=<!\[;]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def _parse_pyproject_deps(content: str) -> list[str]:
    """Simple extraction of dependency names from pyproject.toml."""
    names: list[str] = []
    # Match lines like: "anthropic>=0.1", or items inside dependencies = [...]
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies") and "=" in stripped:
            in_deps = True
            # Handle inline list: dependencies = ["foo", "bar"]
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
                # Grab any items on the closing line.
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


def _build_dependencies_list(key_files: dict[str, str]) -> str:
    """Aggregate dependency names from package.json, pyproject.toml, requirements.txt."""
    all_deps: list[str] = []

    # package.json
    pkg_raw = _find_key_file(key_files, "package.json")
    if pkg_raw:
        try:
            data = json.loads(pkg_raw)
            all_deps.extend(data.get("dependencies", {}).keys())
        except (json.JSONDecodeError, TypeError):
            pass

    # pyproject.toml
    pyproject = _find_key_file(key_files, "pyproject.toml")
    if pyproject:
        all_deps.extend(_parse_pyproject_deps(pyproject))

    # requirements.txt
    reqs = _find_key_file(key_files, "requirements.txt")
    if reqs:
        all_deps.extend(_parse_requirements_txt(reqs))

    if not all_deps:
        return ""

    # Deduplicate preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for d in all_deps:
        low = d.lower()
        if low not in seen:
            seen.add(low)
            unique.append(d)

    return "\n".join(f"- {d}" for d in unique)


def _format_converted_docs(converted: dict[str, str]) -> str:
    """Summarize converted documents with char counts."""
    if not converted:
        return ""
    parts = [f"{path} ({len(content)} chars)" for path, content in converted.items()]
    return "Converted documents: " + ", ".join(parts)
