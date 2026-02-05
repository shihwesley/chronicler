"""VCS providers for Chronicler."""

import os

from chronicler.config.models import VCSConfig
from chronicler.vcs.base import VCSProvider
from chronicler.vcs.github import GitHubProvider
from chronicler.vcs.crawler import VCSCrawler
from chronicler.vcs.models import CrawlResult, FileNode, RepoMetadata


def create_provider(config: VCSConfig) -> VCSProvider:
    """Create a VCS provider from config.

    Resolves the token from the environment variable named in config.token_env.
    """
    if config.provider != "github":
        raise ValueError(
            f"Unsupported VCS provider: {config.provider!r}. "
            "Currently only 'github' is supported."
        )
    token = os.environ.get(config.token_env, "")
    if not token:
        raise ValueError(
            f"VCS token not found. Set the {config.token_env} environment variable."
        )
    return GitHubProvider(token=token)


__all__ = [
    "VCSProvider",
    "GitHubProvider",
    "VCSCrawler",
    "RepoMetadata",
    "FileNode",
    "CrawlResult",
    "create_provider",
]
