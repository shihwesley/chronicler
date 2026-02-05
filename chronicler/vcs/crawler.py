"""VCS Crawler — orchestrates repo listing, tree traversal, and key file extraction."""

from __future__ import annotations

import fnmatch
import logging

from github import GithubException

from chronicler.config.models import VCSConfig
from chronicler.vcs.base import VCSProvider
from chronicler.vcs.models import CrawlResult, FileNode

logger = logging.getLogger(__name__)

# Files/patterns that indicate project structure, build config, or CI.
# Simple glob patterns (*.yml) are matched with fnmatch against the full path.
KEY_FILES: list[str] = [
    # Package manifests
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "setup.cfg",
    "setup.py",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    # Monorepo
    "lerna.json",
    "pnpm-workspace.yaml",
    "nx.json",
    "rush.json",
    "turbo.json",
    # Config
    "tsconfig.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    # Docs
    "README.md",
    "CHANGELOG.md",
    # CI (glob)
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".gitlab-ci.yml",
]

MAX_KEY_FILE_SIZE = 100_000  # 100 KB


class VCSCrawler:
    """Orchestrates crawling a VCS provider for repo metadata, tree, and key files."""

    def __init__(self, provider: VCSProvider, config: VCSConfig) -> None:
        self.provider = provider
        self.config = config

    async def list_repos(self, target: str) -> list:
        """List repos for target org/user, filtered by allowed_orgs if configured."""
        repos = await self.provider.list_repos(target)
        if self.config.allowed_orgs:
            allowed = {o.lower() for o in self.config.allowed_orgs}
            repos = [
                r for r in repos if r.full_name.split("/")[0].lower() in allowed
            ]
        return repos

    async def crawl_repo(self, repo_id: str) -> CrawlResult:
        """Crawl a single repo: metadata, file tree, and key file contents."""
        metadata = await self.provider.get_repo_metadata(repo_id)
        tree = await self._get_full_tree(repo_id)
        key_files = await self.identify_key_files(repo_id, tree)
        return CrawlResult(metadata=metadata, tree=tree, key_files=key_files)

    async def _get_full_tree(self, repo_id: str, max_depth: int = 5) -> list[FileNode]:
        """Recursively traverse repo tree up to max_depth."""
        result: list[FileNode] = []

        async def _traverse(path: str = "", depth: int = 0) -> None:
            if depth > max_depth:
                return
            nodes = await self.provider.get_file_tree(repo_id, path)
            for node in nodes:
                result.append(node)
                if node.type == "dir":
                    await _traverse(node.path, depth + 1)

        await _traverse()
        return result

    async def identify_key_files(
        self, repo_id: str, tree: list[FileNode]
    ) -> dict[str, str]:
        """Identify and fetch content of key project files from the tree."""
        matched: dict[str, str] = {}
        for node in tree:
            if node.type != "file":
                continue
            if not _matches_key_file(node.path):
                continue
            if node.size is not None and node.size > MAX_KEY_FILE_SIZE:
                logger.debug("Skipping %s: too large (%d bytes)", node.path, node.size)
                continue
            try:
                content = await self.provider.get_file_content(repo_id, node.path)
                matched[node.path] = content
            except ValueError:
                logger.debug("Skipping binary/unreadable file: %s", node.path)
            except GithubException as e:
                if e.status in (401, 403, 429):
                    raise
                logger.warning("GitHub error fetching %s: %s", node.path, e)
            except Exception:
                logger.warning("Failed to fetch %s", node.path, exc_info=True)
        return matched


def _matches_key_file(path: str) -> bool:
    """Check if a file path matches any KEY_FILES pattern."""
    name = path.rsplit("/", 1)[-1] if "/" in path else path
    for pattern in KEY_FILES:
        # Patterns with '/' match against full path, others match filename only
        if "/" in pattern:
            if fnmatch.fnmatch(path, pattern):
                return True
        else:
            if fnmatch.fnmatch(name, pattern):
                return True
    return False
