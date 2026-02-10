"""Context builder: transforms CrawlResult into PromptContext for LLM consumption.

Thin orchestrator that delegates to FileTreeFormatter, KeyFileLocator,
and the DependencyParser registry.
"""

from __future__ import annotations

from chronicler_core.drafter.dependency_parser import PARSERS, DependencyParser
from chronicler_core.drafter.file_tree import FileTreeFormatter
from chronicler_core.drafter.key_files import KeyFileLocator
from chronicler_core.drafter.models import PromptContext
from chronicler_core.vcs.models import CrawlResult


class ContextBuilder:
    """Transforms VCS crawl data into structured LLM prompt context."""

    def __init__(
        self,
        parsers: list[DependencyParser] | None = None,
        tree_formatter: FileTreeFormatter | None = None,
        key_locator: KeyFileLocator | None = None,
    ) -> None:
        self._parsers = parsers if parsers is not None else PARSERS
        self._tree_formatter = tree_formatter or FileTreeFormatter()
        self._key_locator = key_locator or KeyFileLocator()

    @staticmethod
    def from_crawl_result(result: CrawlResult) -> PromptContext:
        """Build PromptContext from a CrawlResult (static convenience method)."""
        builder = ContextBuilder()
        return builder.build(result)

    def build(self, result: CrawlResult) -> PromptContext:
        """Build PromptContext using injected components."""
        locator = self._key_locator
        return PromptContext(
            repo_name=result.metadata.name,
            description=result.metadata.description or "",
            default_branch=result.metadata.default_branch,
            languages=_format_languages(result.metadata.languages),
            topics=", ".join(result.metadata.topics),
            file_tree=self._tree_formatter.format(result.tree),
            readme_content=locator.find(result.key_files, "README.md"),
            package_json=locator.extract_package_json_deps(result.key_files),
            dockerfile=locator.find(result.key_files, "Dockerfile"),
            dependencies_list=self._build_dependencies(result.key_files),
            converted_docs_summary=locator.format_converted_docs(result.converted_docs),
        )

    def _build_dependencies(self, key_files: dict[str, str]) -> str:
        """Aggregate dependency names from all registered parsers."""
        all_deps: list[str] = []
        locator = self._key_locator

        for parser in self._parsers:
            content = locator.find(key_files, parser.file_pattern)
            if content:
                all_deps.extend(parser.parse(content))

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


def _format_languages(langs: dict[str, int]) -> str:
    """Sort languages by bytes descending, return comma-separated names."""
    if not langs:
        return ""
    sorted_langs = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
    return ", ".join(name for name, _ in sorted_langs)
