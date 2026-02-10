"""Tests for the drafter subsystem: context, frontmatter, graph, sections, drafter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chronicler_core.drafter.context import ContextBuilder
from chronicler_core.drafter.drafter import Drafter, _assemble_tech_md
from chronicler_core.drafter.frontmatter import generate_frontmatter, _infer_layer, _parse_owner
from chronicler_core.drafter.graph import (
    generate_connectivity_graph,
    _sanitize_node_id,
    _detect_infrastructure,
)
from chronicler_core.drafter.models import PromptContext, TechDoc
from chronicler_core.drafter.prompts import PromptTemplate
from chronicler_core.drafter.sections import draft_architectural_intent
from chronicler_core.vcs.models import CrawlResult, FileNode, RepoMetadata


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------


class TestContextBuilder:
    def test_from_crawl_result_basic(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)

        assert isinstance(ctx, PromptContext)
        assert ctx.repo_name == "widget-api"
        assert ctx.description == "REST API for widget management"
        assert ctx.default_branch == "main"

    def test_languages_sorted_by_bytes(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        # Python (42000) should come before Shell (1200)
        assert ctx.languages.startswith("Python")
        assert "Shell" in ctx.languages

    def test_topics_joined(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        assert "api" in ctx.topics
        assert "python" in ctx.topics

    def test_readme_extracted(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        assert "Widget API" in ctx.readme_content

    def test_dockerfile_extracted(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        assert "python:3.12" in ctx.dockerfile

    def test_file_tree_formatted(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        assert ctx.file_tree  # non-empty string
        assert "main.py" in ctx.file_tree

    def test_empty_languages(self, sample_crawl_result):
        sample_crawl_result.metadata.languages = {}
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        assert ctx.languages == ""

    def test_no_key_files(self, sample_repo_metadata, sample_file_tree):
        result = CrawlResult(
            metadata=sample_repo_metadata,
            tree=sample_file_tree,
            key_files={},
        )
        ctx = ContextBuilder.from_crawl_result(result)
        assert ctx.readme_content == ""
        assert ctx.dockerfile == ""
        assert ctx.package_json == ""

    def test_converted_docs_summary(self, sample_repo_metadata, sample_file_tree):
        result = CrawlResult(
            metadata=sample_repo_metadata,
            tree=sample_file_tree,
            key_files={},
            converted_docs={"design.pdf": "Some design content here"},
        )
        ctx = ContextBuilder.from_crawl_result(result)
        assert "design.pdf" in ctx.converted_docs_summary
        assert "chars" in ctx.converted_docs_summary


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestGenerateFrontmatter:
    def test_required_fields_present(self, sample_crawl_result):
        fm = generate_frontmatter(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert "component_id" in fm
        assert "version" in fm
        assert "layer" in fm
        assert fm["component_id"] == "acme/widget-api"
        assert fm["version"] == "0.1.0"

    def test_governance_verification_status(self, sample_crawl_result):
        fm = generate_frontmatter(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert fm["governance"]["verification_status"] == "ai_draft"

    def test_infer_layer_api(self):
        tree = [
            FileNode(path="api", name="api", type="dir"),
            FileNode(path="routes", name="routes", type="dir"),
        ]
        assert _infer_layer(tree) == "api"

    def test_infer_layer_logic(self):
        tree = [
            FileNode(path="services", name="services", type="dir"),
            FileNode(path="core", name="core", type="dir"),
        ]
        assert _infer_layer(tree) == "logic"

    def test_infer_layer_infrastructure(self):
        tree = [
            FileNode(path="terraform", name="terraform", type="dir"),
            FileNode(path="deploy", name="deploy", type="dir"),
        ]
        assert _infer_layer(tree) == "infrastructure"

    def test_infer_layer_default(self):
        tree = [
            FileNode(path="random", name="random", type="dir"),
        ]
        assert _infer_layer(tree) == "logic"

    def test_parse_owner_from_codeowners(self):
        key_files = {"CODEOWNERS": "* @acme/platform-team\n"}
        assert _parse_owner(key_files) == "platform-team"

    def test_parse_owner_github_path(self):
        key_files = {".github/CODEOWNERS": "* @org/infra-squad"}
        assert _parse_owner(key_files) == "infra-squad"

    def test_parse_owner_missing(self):
        assert _parse_owner({}) == "unknown"

    def test_parse_owner_no_global_line(self):
        key_files = {"CODEOWNERS": "# just a comment\n"}
        assert _parse_owner(key_files) == "unknown"

    def test_edges_is_list(self, sample_crawl_result):
        fm = generate_frontmatter(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert isinstance(fm["edges"], list)


# ---------------------------------------------------------------------------
# Connectivity Graph
# ---------------------------------------------------------------------------


class TestGenerateConnectivityGraph:
    def test_starts_with_graph_lr(self, sample_crawl_result):
        graph = generate_connectivity_graph(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert graph.startswith("graph LR")

    def test_contains_component_node(self, sample_crawl_result):
        graph = generate_connectivity_graph(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert "widget-api" in graph

    def test_sanitize_node_id(self):
        assert _sanitize_node_id("my/package") == "my-package"
        assert _sanitize_node_id("@scope/name") == "scope-name"
        assert _sanitize_node_id("") == "component"

    def test_infra_detection_postgres(self):
        key_files = {"Dockerfile": "FROM postgres:15 as db"}
        tree = []
        infra = _detect_infrastructure(key_files, tree)
        assert any(n[0] == "postgres" for n in infra)

    def test_infra_detection_redis(self):
        key_files = {"Dockerfile": "RUN pip install redis"}
        infra = _detect_infrastructure(key_files, [])
        assert any(n[0] == "redis" for n in infra)

    def test_graph_with_python_deps(self):
        metadata = RepoMetadata(
            component_id="test/repo",
            name="repo",
            full_name="test/repo",
            languages={"Python": 10000},
        )
        key_files = {"requirements.txt": "flask>=2.0\nrequests\nsqlalchemy"}
        graph = generate_connectivity_graph(metadata, key_files, [])
        assert "flask" in graph.lower() or "Flask" in graph
        assert "requests" in graph.lower() or "Requests" in graph

    def test_graph_with_node_deps(self):
        metadata = RepoMetadata(
            component_id="test/app",
            name="app",
            full_name="test/app",
            languages={"JavaScript": 5000},
        )
        key_files = {
            "package.json": '{"dependencies": {"express": "^4.0", "lodash": "^4.17"}}'
        }
        graph = generate_connectivity_graph(metadata, key_files, [])
        assert "express" in graph.lower() or "Express" in graph

    def test_graph_ends_with_newline(self, sample_crawl_result):
        graph = generate_connectivity_graph(
            sample_crawl_result.metadata,
            sample_crawl_result.key_files,
            sample_crawl_result.tree,
        )
        assert graph.endswith("\n")


# ---------------------------------------------------------------------------
# draft_architectural_intent (async, mocked LLM)
# ---------------------------------------------------------------------------


class TestDraftArchitecturalIntent:
    async def test_returns_llm_content(self, sample_crawl_result, mock_llm_provider):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        result = await draft_architectural_intent(ctx, mock_llm_provider)
        assert result == "Generated documentation content."
        mock_llm_provider.generate.assert_awaited_once()

    async def test_passes_system_and_user_prompts(
        self, sample_crawl_result, mock_llm_provider
    ):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        await draft_architectural_intent(ctx, mock_llm_provider)

        call_kwargs = mock_llm_provider.generate.call_args
        assert "system" in call_kwargs.kwargs or len(call_kwargs.args) >= 1
        assert "user" in call_kwargs.kwargs or len(call_kwargs.args) >= 2


# ---------------------------------------------------------------------------
# PromptTemplate
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    def test_render_returns_tuple(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        template = PromptTemplate()
        system, user = template.render(ctx)
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_user_prompt_contains_repo_name(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        _, user = PromptTemplate().render(ctx)
        assert "widget-api" in user

    def test_truncation_long_readme(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        # Override readme with very long content
        ctx = ctx.model_copy(update={"readme_content": "x" * 5000})
        template = PromptTemplate()
        truncated = template._apply_truncation(ctx)
        assert len(truncated.readme_content) < 5000
        assert "truncated" in truncated.readme_content

    def test_truncation_no_mutation(self, sample_crawl_result):
        ctx = ContextBuilder.from_crawl_result(sample_crawl_result)
        original_readme = ctx.readme_content
        PromptTemplate()._apply_truncation(ctx)
        assert ctx.readme_content == original_readme


# ---------------------------------------------------------------------------
# _assemble_tech_md
# ---------------------------------------------------------------------------


class TestAssembleTechMd:
    def test_has_yaml_frontmatter(self):
        fm = {"component_id": "test", "version": "0.1.0", "layer": "logic"}
        raw = _assemble_tech_md(fm, "test", "Some intent", "graph LR\n")
        assert raw.startswith("---\n")
        assert "\n---\n" in raw

    def test_contains_heading(self):
        fm = {"component_id": "test"}
        raw = _assemble_tech_md(fm, "test", "Intent text", "graph LR\n")
        assert "# test" in raw

    def test_contains_sections(self):
        fm = {"component_id": "myapp"}
        raw = _assemble_tech_md(fm, "myapp", "Intent here", "graph LR\n")
        assert "## Architectural Intent" in raw
        assert "Intent here" in raw
        assert "## Connectivity Graph" in raw
        assert "```mermaid" in raw


# ---------------------------------------------------------------------------
# Drafter (full orchestration, mocked LLM)
# ---------------------------------------------------------------------------


class TestDrafter:
    async def test_draft_tech_doc_returns_tech_doc(
        self, sample_crawl_result, mock_llm_provider, sample_config
    ):
        drafter = Drafter(llm=mock_llm_provider, config=sample_config)
        doc = await drafter.draft_tech_doc(sample_crawl_result)

        assert isinstance(doc, TechDoc)
        assert doc.component_id == "acme/widget-api"
        assert doc.architectural_intent == "Generated documentation content."
        assert doc.connectivity_graph.startswith("graph LR")
        assert doc.raw_content.startswith("---\n")

    async def test_draft_tech_doc_frontmatter_dict(
        self, sample_crawl_result, mock_llm_provider, sample_config
    ):
        drafter = Drafter(llm=mock_llm_provider, config=sample_config)
        doc = await drafter.draft_tech_doc(sample_crawl_result)

        assert doc.frontmatter["component_id"] == "acme/widget-api"
        assert doc.frontmatter["governance"]["verification_status"] == "ai_draft"
        assert "layer" in doc.frontmatter
        assert "version" in doc.frontmatter

    async def test_draft_tech_doc_calls_llm(
        self, sample_crawl_result, mock_llm_provider, sample_config
    ):
        drafter = Drafter(llm=mock_llm_provider, config=sample_config)
        await drafter.draft_tech_doc(sample_crawl_result)
        mock_llm_provider.generate.assert_awaited_once()
