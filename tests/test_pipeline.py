"""Integration test: full pipeline from VCS crawl through to validated .tech.md on disk."""

import yaml
import pytest
from unittest.mock import AsyncMock, MagicMock

from chronicler.config.models import ChroniclerConfig, OutputConfig, VCSConfig
from chronicler.drafter.drafter import Drafter
from chronicler.llm.base import LLMProvider
from chronicler.llm.models import LLMConfig, LLMResponse, TokenUsage
from chronicler.output.writer import TechMdWriter
from chronicler.output.validator import TechMdValidator
from chronicler.vcs.crawler import VCSCrawler
from chronicler.vcs.base import VCSProvider
from chronicler.vcs.models import CrawlResult, FileNode, RepoMetadata


@pytest.fixture
def pipeline_vcs_provider():
    """A mock VCS provider that returns realistic repo data."""
    metadata = RepoMetadata(
        component_id="myorg/payments-api",
        name="payments-api",
        full_name="myorg/payments-api",
        description="Handles payment processing for the platform",
        languages={"Python": 35000, "SQL": 4000},
        default_branch="main",
        size=2400,
        topics=["payments", "api", "python"],
        url="https://github.com/myorg/payments-api",
    )

    tree = [
        FileNode(path="src", name="src", type="dir"),
        FileNode(path="src/app.py", name="app.py", type="file", size=1200, sha="a1"),
        FileNode(path="api", name="api", type="dir"),
        FileNode(
            path="api/routes.py", name="routes.py", type="file", size=900, sha="a2"
        ),
        FileNode(
            path="requirements.txt",
            name="requirements.txt",
            type="file",
            size=120,
            sha="a3",
        ),
        FileNode(
            path="README.md", name="README.md", type="file", size=1500, sha="a4"
        ),
        FileNode(
            path="Dockerfile", name="Dockerfile", type="file", size=250, sha="a5"
        ),
    ]

    provider = MagicMock(spec=VCSProvider)
    provider.get_repo_metadata = AsyncMock(return_value=metadata)
    provider.get_file_tree = AsyncMock(return_value=tree)
    provider.get_file_content = AsyncMock(
        side_effect=lambda repo_id, path: {
            "requirements.txt": "flask>=2.0\nstripe>=5.0\nsqlalchemy",
            "README.md": "# Payments API\nProcesses credit card and ACH payments.",
            "Dockerfile": "FROM python:3.12-slim\nRUN pip install -r requirements.txt",
        }.get(path, "")
    )
    return provider


@pytest.fixture
def pipeline_llm_provider():
    """Mock LLM that returns a plausible architectural intent."""
    provider = MagicMock(spec=LLMProvider)
    provider.config = LLMConfig(provider="anthropic", model="test-model")
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=(
                "Processes credit card and ACH payments through Stripe.\n\n"
                "Exists to centralize payment processing across the platform.\n\n"
                "**Key responsibilities:**\n"
                "- Accept and validate payment requests\n"
                "- Integrate with Stripe for card processing\n"
                "- Store transaction records in PostgreSQL\n"
            ),
            usage=TokenUsage(input_tokens=500, output_tokens=150),
            model="test-model",
        )
    )
    return provider


class TestFullPipeline:
    """End-to-end: mock VCS -> crawl -> draft -> write -> validate."""

    async def test_pipeline_produces_valid_tech_md(
        self, pipeline_vcs_provider, pipeline_llm_provider, tmp_path
    ):
        # 1. Crawl
        vcs_config = VCSConfig(provider="github")
        crawler = VCSCrawler(provider=pipeline_vcs_provider, config=vcs_config)
        crawl_result = await crawler.crawl_repo("myorg/payments-api")

        assert isinstance(crawl_result, CrawlResult)
        assert crawl_result.metadata.name == "payments-api"

        # 2. Draft
        config = ChroniclerConfig()
        drafter = Drafter(llm=pipeline_llm_provider, config=config)
        tech_doc = await drafter.draft_tech_doc(crawl_result)

        assert tech_doc.component_id == "myorg/payments-api"
        assert tech_doc.raw_content.startswith("---\n")

        # 3. Write
        output_config = OutputConfig(
            base_dir=str(tmp_path), create_index=True
        )
        writer = TechMdWriter(output_config)
        written_path = writer.write(tech_doc)

        assert written_path.exists()
        content = written_path.read_text(encoding="utf-8")
        assert len(content) > 0

        # 4. Validate (strict mode)
        validator = TechMdValidator(mode="strict")
        result = validator.validate_file(written_path)

        assert result.valid is True, f"Validation failed: {result.errors}"
        assert result.errors == []

    async def test_frontmatter_has_required_fields(
        self, pipeline_vcs_provider, pipeline_llm_provider, tmp_path
    ):
        vcs_config = VCSConfig(provider="github")
        crawler = VCSCrawler(provider=pipeline_vcs_provider, config=vcs_config)
        crawl_result = await crawler.crawl_repo("myorg/payments-api")

        config = ChroniclerConfig()
        drafter = Drafter(llm=pipeline_llm_provider, config=config)
        tech_doc = await drafter.draft_tech_doc(crawl_result)

        output_config = OutputConfig(base_dir=str(tmp_path), create_index=False)
        writer = TechMdWriter(output_config)
        written_path = writer.write(tech_doc)

        content = written_path.read_text(encoding="utf-8")

        # Parse frontmatter from written file
        assert content.startswith("---\n")
        end = content.find("---", 3)
        assert end != -1
        fm = yaml.safe_load(content[3:end])

        assert isinstance(fm, dict)
        assert fm["component_id"] == "myorg/payments-api"
        assert isinstance(fm["version"], str)
        assert fm["layer"] in ("api", "logic", "infrastructure")
        assert fm["governance"]["verification_status"] == "ai_draft"

    async def test_written_file_exists_on_disk(
        self, pipeline_vcs_provider, pipeline_llm_provider, tmp_path
    ):
        vcs_config = VCSConfig(provider="github")
        crawler = VCSCrawler(provider=pipeline_vcs_provider, config=vcs_config)
        crawl_result = await crawler.crawl_repo("myorg/payments-api")

        config = ChroniclerConfig()
        drafter = Drafter(llm=pipeline_llm_provider, config=config)
        tech_doc = await drafter.draft_tech_doc(crawl_result)

        output_config = OutputConfig(base_dir=str(tmp_path), create_index=True)
        writer = TechMdWriter(output_config)
        written_path = writer.write(tech_doc)

        # File on disk
        assert written_path.exists()
        assert written_path.stat().st_size > 0
        assert written_path.name.endswith(".tech.md")

        # Index file on disk
        index_path = tmp_path / "_index.yaml"
        assert index_path.exists()
        entries = yaml.safe_load(index_path.read_text())
        assert any(
            e["component_id"] == "myorg/payments-api" for e in entries
        )

    async def test_connectivity_graph_in_output(
        self, pipeline_vcs_provider, pipeline_llm_provider, tmp_path
    ):
        vcs_config = VCSConfig(provider="github")
        crawler = VCSCrawler(provider=pipeline_vcs_provider, config=vcs_config)
        crawl_result = await crawler.crawl_repo("myorg/payments-api")

        config = ChroniclerConfig()
        drafter = Drafter(llm=pipeline_llm_provider, config=config)
        tech_doc = await drafter.draft_tech_doc(crawl_result)

        assert "graph LR" in tech_doc.connectivity_graph
        assert "```mermaid" in tech_doc.raw_content
