"""Drafter orchestrator: coordinates all components to produce a .tech.md document."""

from __future__ import annotations

import logging

import yaml

from chronicler_core.config import ChroniclerConfig
from chronicler_core.drafter.context import ContextBuilder
from chronicler_core.drafter.frontmatter import generate_frontmatter
from chronicler_core.drafter.graph import generate_connectivity_graph
from chronicler_core.drafter.models import FrontmatterModel, PromptContext, TechDoc
from chronicler_core.drafter.sections import draft_architectural_intent
from chronicler_core.llm.base import LLMProvider
from chronicler_core.vcs.models import CrawlResult

logger = logging.getLogger(__name__)


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
        frontmatter = generate_frontmatter(crawl_result)

        # 3. Draft architectural intent (async LLM call)
        intent = await draft_architectural_intent(context, self.llm)

        word_count = len(intent.split())
        if word_count > 1500:
            logger.warning(
                "Architectural intent is %d words (target: ~1000, max: 1500)",
                word_count,
            )

        # 4. Generate connectivity graph
        graph = generate_connectivity_graph(crawl_result)

        # 5. Assemble
        component_id = frontmatter.component_id
        raw_content = _assemble_tech_md(frontmatter, component_id, intent, graph)

        return TechDoc(
            component_id=component_id,
            frontmatter=frontmatter,
            architectural_intent=intent,
            connectivity_graph=graph,
            raw_content=raw_content,
        )


def _assemble_tech_md(
    frontmatter: FrontmatterModel,
    component_id: str,
    intent: str,
    graph: str,
) -> str:
    """Assemble a complete .tech.md string from its parts."""
    yaml_block = yaml.dump(frontmatter.model_dump(), default_flow_style=False, sort_keys=False)

    return (
        f"---\n{yaml_block}---\n\n"
        f"# {component_id}\n\n"
        f"## Architectural Intent\n\n{intent}\n\n"
        f"## Connectivity Graph\n\n```mermaid\n{graph}```\n"
    )
