"""Shared test fixtures for Chronicler."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from chronicler_core.config.models import ChroniclerConfig
from chronicler_core.vcs.base import VCSProvider
from chronicler_core.vcs.models import CrawlResult, FileNode, RepoMetadata
from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig as LLMRuntimeConfig, LLMResponse, TokenUsage


@pytest.fixture
def sample_repo_metadata():
    return RepoMetadata(
        component_id="acme/widget-api",
        name="widget-api",
        full_name="acme/widget-api",
        description="REST API for widget management",
        languages={"Python": 42000, "Shell": 1200},
        default_branch="main",
        size=1500,
        topics=["api", "python", "rest"],
        url="https://github.com/acme/widget-api",
    )


@pytest.fixture
def sample_file_tree():
    """Mix of files and dirs, including several key files."""
    return [
        FileNode(path="src", name="src", type="dir"),
        FileNode(path="src/main.py", name="main.py", type="file", size=800, sha="abc1"),
        FileNode(path="package.json", name="package.json", type="file", size=450, sha="abc2"),
        FileNode(path="README.md", name="README.md", type="file", size=2000, sha="abc3"),
        FileNode(path="Dockerfile", name="Dockerfile", type="file", size=300, sha="abc4"),
        FileNode(
            path=".github/workflows/ci.yml",
            name="ci.yml",
            type="file",
            size=600,
            sha="abc5",
        ),
        FileNode(path="docs", name="docs", type="dir"),
        FileNode(path="docs/guide.md", name="guide.md", type="file", size=5000, sha="abc6"),
        FileNode(path="pyproject.toml", name="pyproject.toml", type="file", size=350, sha="abc7"),
    ]


@pytest.fixture
def sample_crawl_result(sample_repo_metadata, sample_file_tree):
    return CrawlResult(
        metadata=sample_repo_metadata,
        tree=sample_file_tree,
        key_files={
            "package.json": '{"name": "widget-api"}',
            "README.md": "# Widget API\nSome docs.",
            "Dockerfile": "FROM python:3.12",
        },
    )


@pytest.fixture
def mock_vcs_provider(sample_repo_metadata, sample_file_tree):
    provider = MagicMock(spec=VCSProvider)
    provider.list_repos = AsyncMock(return_value=[sample_repo_metadata])
    provider.get_repo_metadata = AsyncMock(return_value=sample_repo_metadata)
    provider.get_file_tree = AsyncMock(return_value=sample_file_tree)
    provider.get_file_content = AsyncMock(return_value="file content placeholder")
    return provider


@pytest.fixture
def mock_llm_provider():
    provider = MagicMock(spec=LLMProvider)
    provider.config = LLMRuntimeConfig(provider="anthropic", model="test-model")
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="Generated documentation content.",
            usage=TokenUsage(input_tokens=100, output_tokens=250),
            model="test-model",
        )
    )

    async def _fake_stream(*args, **kwargs):
        for chunk in ["Generated ", "documentation ", "content."]:
            yield chunk

    provider.generate_stream = MagicMock(side_effect=_fake_stream)
    return provider


@pytest.fixture
def sample_config():
    return ChroniclerConfig()


@pytest.fixture
def tmp_chronicler_dir(tmp_path):
    """A temp .chronicler directory structure for output tests."""
    chronicler_dir = tmp_path / ".chronicler"
    chronicler_dir.mkdir()
    (chronicler_dir / "docs").mkdir()
    return chronicler_dir
