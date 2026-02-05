"""GitHub VCS provider using PyGithub."""

import asyncio
import os
from functools import cached_property

from github import Auth, Github
from github.Repository import Repository

from chronicler.vcs.base import VCSProvider
from chronicler.vcs.models import FileNode, RepoMetadata


class GitHubProvider(VCSProvider):
    """GitHub implementation of VCSProvider using PyGithub.

    PyGithub is synchronous, so all blocking calls are wrapped
    with asyncio.to_thread() to avoid blocking the event loop.
    """

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self._token:
            raise ValueError(
                "GitHub token required. Pass token= or set GITHUB_TOKEN env var."
            )

    @cached_property
    def _client(self) -> Github:
        auth = Auth.Token(self._token)
        return Github(auth=auth)

    def _get_repo(self, repo_id: str) -> Repository:
        """Get a PyGithub Repository object by 'owner/repo' identifier."""
        return self._client.get_repo(repo_id)

    def _build_repo_metadata(self, repo: Repository) -> RepoMetadata:
        """Convert a PyGithub Repository to our RepoMetadata model."""
        languages = repo.get_languages()
        topics = repo.get_topics()
        return RepoMetadata(
            component_id=repo.full_name,
            name=repo.name,
            full_name=repo.full_name,
            description=repo.description,
            languages=languages,
            default_branch=repo.default_branch,
            size=repo.size,
            topics=topics,
            url=repo.html_url,
        )

    async def list_repos(self, org_or_user: str) -> list[RepoMetadata]:
        """List repositories for a GitHub user or organization."""

        def _sync() -> list[RepoMetadata]:
            try:
                named_user = self._client.get_organization(org_or_user)
            except Exception:
                named_user = self._client.get_user(org_or_user)
            repos = named_user.get_repos()
            return [self._build_repo_metadata(r) for r in repos]

        return await asyncio.to_thread(_sync)

    async def get_repo_metadata(self, repo_id: str) -> RepoMetadata:
        """Get metadata for a specific repository."""

        def _sync() -> RepoMetadata:
            repo = self._get_repo(repo_id)
            return self._build_repo_metadata(repo)

        return await asyncio.to_thread(_sync)

    async def get_file_tree(self, repo_id: str, path: str = "") -> list[FileNode]:
        """List files and directories at a path in the repository."""

        def _sync() -> list[FileNode]:
            repo = self._get_repo(repo_id)
            contents = repo.get_contents(path, ref=repo.default_branch)
            # get_contents returns a single item for files, list for dirs
            if not isinstance(contents, list):
                contents = [contents]
            return [
                FileNode(
                    path=c.path,
                    name=c.name,
                    type="dir" if c.type == "dir" else "file",
                    size=c.size,
                    sha=c.sha,
                )
                for c in contents
            ]

        return await asyncio.to_thread(_sync)

    async def get_file_content(self, repo_id: str, path: str) -> str:
        """Fetch decoded text content of a file from GitHub."""

        def _sync() -> str:
            repo = self._get_repo(repo_id)
            content = repo.get_contents(path, ref=repo.default_branch)
            if isinstance(content, list):
                raise ValueError(f"Path '{path}' is a directory, not a file.")
            return content.decoded_content.decode()

        return await asyncio.to_thread(_sync)
