"""Drafter orchestrator: coordinates all components to produce a .tech.md document."""

from __future__ import annotations

import yaml

from chronicler.config import ChroniclerConfig
from chronicler.drafter.context import ContextBuilder
from chronicler.drafter.frontmatter import generate_frontmatter
from chronicler.drafter.graph import generate_connectivity_graph
from chronicler.drafter.models import PromptContext, TechDoc
from chronicler.drafter.sections import draft_architectural_intent
from chronicler.llm.base import LLMProvider
from chronicler.vcs.models import CrawlResult


class Drafter:
    """Orchestrates .tech.md generation from crawled repo data.

    Pipeline:
        CrawlResult → ContextBuilder → frontmatter + intent + graph → TechDoc
    """

    def __init__(self, llm: LLMProvider, config: ChroniclerConfig) -> None:
        self.llm = llm
        self.config = config

    async def draft_tech_doc(self, crawl_result: CrawlResult) -> TechDoc:
        """Generate a complete .tech.md document from crawl data.

        Steps:
            1. Build PromptContext from CrawlResult
            2. Generate YAML frontmatter (deterministic)
            3. Draft Architectural Intent (LLM)
            4. Generate connectivity graph (deterministic)
            5. Assemble into TechDoc with raw_content
        """
        # 1. Build prompt context
        context = ContextBuilder.from_crawl_result(crawl_result)

        # 2. Generate frontmatter
        frontmatter = generate_frontmatter(
            crawl_result.metadata,
            crawl_result.key_files,
            crawl_result.tree,
        )

        # 3. Draft architectural intent (async LLM call)
        intent = await draft_architectural_intent(context, self.llm)

        # 4. Generate connectivity graph
        graph = generate_connectivity_graph(
            crawl_result.metadata,
            crawl_result.key_files,
            crawl_result.tree,
        )

        # 5. Assemble
        component_id = frontmatter["component_id"]
        raw_content = _assemble_tech_md(frontmatter, component_id, intent, graph)

        return TechDoc(
            component_id=component_id,
            frontmatter=frontmatter,
            architectural_intent=intent,
            connectivity_graph=graph,
            raw_content=raw_content,
        )


def _assemble_tech_md(
    frontmatter: dict,
    component_id: str,
    intent: str,
    graph: str,
) -> str:
    """Assemble a complete .tech.md string from its parts."""
    yaml_block = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    return (
        f"---\n{yaml_block}---\n\n"
        f"# {component_id}\n\n"
        f"## Architectural Intent\n\n{intent}\n\n"
        f"## Connectivity Graph\n\n```mermaid\n{graph}```\n"
    )
