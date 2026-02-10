"""Tests for chronicler.vcs — crawler, key file matching, and error handling."""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from github import GithubException

from chronicler_core.config.models import VCSConfig
from chronicler_core.vcs.crawler import (
    KEY_FILES,
    MAX_KEY_FILE_SIZE,
    VCSCrawler,
    _matches_key_file,
)
from chronicler_core.vcs.models import FileNode, RepoMetadata


# ── _matches_key_file ───────────────────────────────────────────────


class TestMatchesKeyFile:
    """Tests for the module-level pattern matcher."""

    def test_matches_exact_filename(self):
        assert _matches_key_file("package.json") is True
        assert _matches_key_file("README.md") is True
        assert _matches_key_file("Dockerfile") is True

    def test_matches_nested_path_by_filename(self):
        assert _matches_key_file("some/deep/path/package.json") is True
        assert _matches_key_file("root/Makefile") is True

    def test_matches_github_workflow_glob(self):
        assert _matches_key_file(".github/workflows/ci.yml") is True
        assert _matches_key_file(".github/workflows/deploy.yaml") is True

    def test_rejects_non_key_file(self):
        assert _matches_key_file("src/main.py") is False
        assert _matches_key_file("random.txt") is False

    def test_rejects_partial_match(self):
        # "package.json.bak" shouldn't match "package.json"
        assert _matches_key_file("package.json.bak") is False

    def test_gitlab_ci_matches(self):
        assert _matches_key_file(".gitlab-ci.yml") is True

    def test_all_key_files_patterns_are_strings(self):
        """Sanity check that KEY_FILES is a list of strings."""
        assert all(isinstance(p, str) for p in KEY_FILES)
        assert len(KEY_FILES) >= 20  # we expect 23 patterns

    def test_workflow_outside_github_dir_no_match(self):
        # ci.yml alone shouldn't match the .github/workflows/*.yml pattern
        # but it also isn't in KEY_FILES as a bare name, so it shouldn't match
        assert _matches_key_file("ci.yml") is False

    def test_docker_compose_variants(self):
        assert _matches_key_file("docker-compose.yml") is True
        assert _matches_key_file("docker-compose.yaml") is True

    def test_monorepo_config_files(self):
        assert _matches_key_file("lerna.json") is True
        assert _matches_key_file("pnpm-workspace.yaml") is True
        assert _matches_key_file("nx.json") is True
        assert _matches_key_file("turbo.json") is True


# ── VCSCrawler.list_repos ───────────────────────────────────────────


class TestCrawlerListRepos:
    @pytest.fixture
    def default_config(self):
        return VCSConfig()

    async def test_returns_all_repos_without_filter(self, mock_vcs_provider, default_config):
        crawler = VCSCrawler(provider=mock_vcs_provider, config=default_config)
        repos = await crawler.list_repos("acme")
        assert len(repos) == 1
        assert repos[0].full_name == "acme/widget-api"
        mock_vcs_provider.list_repos.assert_awaited_once_with("acme")

    async def test_filters_by_allowed_orgs(self, mock_vcs_provider):
        # Provider returns repos from two orgs
        mock_vcs_provider.list_repos = AsyncMock(
            return_value=[
                RepoMetadata(component_id="acme/a", name="a", full_name="acme/a"),
                RepoMetadata(component_id="other/b", name="b", full_name="other/b"),
                RepoMetadata(component_id="ACME/c", name="c", full_name="ACME/c"),
            ]
        )
        config = VCSConfig(allowed_orgs=["acme"])
        crawler = VCSCrawler(provider=mock_vcs_provider, config=config)

        repos = await crawler.list_repos("someuser")
        names = [r.full_name for r in repos]
        assert "acme/a" in names
        assert "ACME/c" in names  # case-insensitive
        assert "other/b" not in names

    async def test_allowed_orgs_case_insensitive(self, mock_vcs_provider):
        mock_vcs_provider.list_repos = AsyncMock(
            return_value=[
                RepoMetadata(component_id="MyOrg/r", name="r", full_name="MyOrg/r"),
            ]
        )
        config = VCSConfig(allowed_orgs=["myorg"])
        crawler = VCSCrawler(provider=mock_vcs_provider, config=config)

        repos = await crawler.list_repos("x")
        assert len(repos) == 1

    async def test_empty_allowed_orgs_means_no_filter(self, mock_vcs_provider, default_config):
        crawler = VCSCrawler(provider=mock_vcs_provider, config=default_config)
        repos = await crawler.list_repos("acme")
        # Should return everything the provider gives back
        assert len(repos) == 1


# ── VCSCrawler.crawl_repo ──────────────────────────────────────────


class TestCrawlerCrawlRepo:
    async def test_returns_crawl_result(self, mock_vcs_provider, sample_repo_metadata):
        config = VCSConfig()
        # Make get_file_tree return only files (no dirs) to prevent recursion
        leaf_tree = [
            FileNode(path="README.md", name="README.md", type="file", size=100, sha="a1"),
        ]
        mock_vcs_provider.get_file_tree = AsyncMock(return_value=leaf_tree)
        crawler = VCSCrawler(provider=mock_vcs_provider, config=config)

        result = await crawler.crawl_repo("acme/widget-api")
        assert result.metadata.full_name == "acme/widget-api"
        assert len(result.tree) >= 1
        assert isinstance(result.key_files, dict)

    async def test_crawl_fetches_metadata_tree_and_keys(self, mock_vcs_provider):
        config = VCSConfig()
        leaf_tree = [
            FileNode(path="package.json", name="package.json", type="file", size=100, sha="a1"),
        ]
        mock_vcs_provider.get_file_tree = AsyncMock(return_value=leaf_tree)
        mock_vcs_provider.get_file_content = AsyncMock(return_value='{"name":"test"}')
        crawler = VCSCrawler(provider=mock_vcs_provider, config=config)

        result = await crawler.crawl_repo("acme/widget-api")
        mock_vcs_provider.get_repo_metadata.assert_awaited_once()
        mock_vcs_provider.get_file_tree.assert_awaited()
        assert "package.json" in result.key_files


# ── VCSCrawler._get_full_tree ──────────────────────────────────────


class TestGetFullTree:
    async def test_flat_tree_no_recursion(self, mock_vcs_provider):
        flat_nodes = [
            FileNode(path="file1.py", name="file1.py", type="file", size=100),
            FileNode(path="file2.py", name="file2.py", type="file", size=200),
        ]
        mock_vcs_provider.get_file_tree = AsyncMock(return_value=flat_nodes)
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        tree = await crawler._get_full_tree("acme/repo")
        assert len(tree) == 2
        # Only called once (root), no recursion needed for files
        mock_vcs_provider.get_file_tree.assert_awaited_once_with("acme/repo", "")

    async def test_recurses_into_directories(self, mock_vcs_provider):
        """Directories trigger recursive traversal."""
        root_nodes = [
            FileNode(path="src", name="src", type="dir"),
            FileNode(path="README.md", name="README.md", type="file", size=100),
        ]
        src_nodes = [
            FileNode(path="src/app.py", name="app.py", type="file", size=500),
        ]

        async def tree_side_effect(repo_id, path=""):
            if path == "":
                return root_nodes
            elif path == "src":
                return src_nodes
            return []

        mock_vcs_provider.get_file_tree = AsyncMock(side_effect=tree_side_effect)
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        tree = await crawler._get_full_tree("acme/repo")
        paths = [n.path for n in tree]
        assert "src" in paths
        assert "README.md" in paths
        assert "src/app.py" in paths

    async def test_respects_max_depth(self, mock_vcs_provider):
        """Traversal stops at max_depth."""
        # Build a chain of nested dirs: d0/d1/d2/... each containing one subdir
        def make_dir_response(depth):
            dir_path = "/".join(f"d{i}" for i in range(depth + 1))
            return [FileNode(path=dir_path, name=f"d{depth}", type="dir")]

        call_count = 0

        async def tree_side_effect(repo_id, path=""):
            nonlocal call_count
            call_count += 1
            depth = path.count("/") + 1 if path else 0
            return make_dir_response(depth)

        mock_vcs_provider.get_file_tree = AsyncMock(side_effect=tree_side_effect)
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        await crawler._get_full_tree("acme/repo", max_depth=3)
        # depth 0 (root) + depth 1 + depth 2 + depth 3 = 4 calls
        # depth 4 would exceed max_depth=3, so recursion stops
        assert call_count <= 5  # root + up to 4 nested levels with boundary


# ── VCSCrawler.identify_key_files ──────────────────────────────────


class TestIdentifyKeyFiles:
    async def test_fetches_matching_files(self, mock_vcs_provider):
        tree = [
            FileNode(path="package.json", name="package.json", type="file", size=200),
            FileNode(path="src/main.py", name="main.py", type="file", size=500),
        ]
        mock_vcs_provider.get_file_content = AsyncMock(return_value='{"name":"test"}')
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        result = await crawler.identify_key_files("acme/repo", tree)
        assert "package.json" in result
        assert "src/main.py" not in result

    async def test_skips_directories(self, mock_vcs_provider):
        tree = [
            FileNode(path="src", name="src", type="dir"),
        ]
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        result = await crawler.identify_key_files("acme/repo", tree)
        assert result == {}
        mock_vcs_provider.get_file_content.assert_not_awaited()

    async def test_skips_oversized_files(self, mock_vcs_provider):
        tree = [
            FileNode(
                path="README.md",
                name="README.md",
                type="file",
                size=MAX_KEY_FILE_SIZE + 1,
            ),
        ]
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        result = await crawler.identify_key_files("acme/repo", tree)
        assert result == {}
        mock_vcs_provider.get_file_content.assert_not_awaited()

    async def test_file_at_exact_size_limit_is_fetched(self, mock_vcs_provider):
        tree = [
            FileNode(
                path="README.md",
                name="README.md",
                type="file",
                size=MAX_KEY_FILE_SIZE,
            ),
        ]
        mock_vcs_provider.get_file_content = AsyncMock(return_value="# README")
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        result = await crawler.identify_key_files("acme/repo", tree)
        assert "README.md" in result

    async def test_file_with_none_size_is_fetched(self, mock_vcs_provider):
        """When size is None, the file should still be attempted."""
        tree = [
            FileNode(path="Dockerfile", name="Dockerfile", type="file", size=None),
        ]
        mock_vcs_provider.get_file_content = AsyncMock(return_value="FROM python:3.12")
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        result = await crawler.identify_key_files("acme/repo", tree)
        assert "Dockerfile" in result


# ── GithubException handling ────────────────────────────────────────


class TestGithubExceptionHandling:
    @pytest.fixture
    def key_file_tree(self):
        return [
            FileNode(path="package.json", name="package.json", type="file", size=100),
        ]

    async def test_reraises_401(self, mock_vcs_provider, key_file_tree):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=GithubException(401, "Bad credentials", None)
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with pytest.raises(GithubException) as exc_info:
            await crawler.identify_key_files("acme/repo", key_file_tree)
        assert exc_info.value.status == 401

    async def test_reraises_403(self, mock_vcs_provider, key_file_tree):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=GithubException(403, "Forbidden", None)
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with pytest.raises(GithubException):
            await crawler.identify_key_files("acme/repo", key_file_tree)

    async def test_reraises_429_rate_limit(self, mock_vcs_provider, key_file_tree):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=GithubException(429, "Rate limit", None)
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with pytest.raises(GithubException):
            await crawler.identify_key_files("acme/repo", key_file_tree)

    async def test_logs_and_continues_on_404(self, mock_vcs_provider, key_file_tree, caplog):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=GithubException(404, "Not found", None)
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with caplog.at_level(logging.WARNING):
            result = await crawler.identify_key_files("acme/repo", key_file_tree)
        assert result == {}
        assert "GitHub error" in caplog.text

    async def test_logs_and_continues_on_500(self, mock_vcs_provider, key_file_tree, caplog):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=GithubException(500, "Server error", None)
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with caplog.at_level(logging.WARNING):
            result = await crawler.identify_key_files("acme/repo", key_file_tree)
        assert result == {}

    async def test_value_error_skips_binary_file(self, mock_vcs_provider, key_file_tree, caplog):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=ValueError("Binary content")
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with caplog.at_level(logging.DEBUG):
            result = await crawler.identify_key_files("acme/repo", key_file_tree)
        assert result == {}

    async def test_generic_exception_logged_and_skipped(
        self, mock_vcs_provider, key_file_tree, caplog
    ):
        mock_vcs_provider.get_file_content = AsyncMock(
            side_effect=RuntimeError("network timeout")
        )
        crawler = VCSCrawler(provider=mock_vcs_provider, config=VCSConfig())

        with caplog.at_level(logging.WARNING):
            result = await crawler.identify_key_files("acme/repo", key_file_tree)
        assert result == {}
        assert "Failed to fetch" in caplog.text
