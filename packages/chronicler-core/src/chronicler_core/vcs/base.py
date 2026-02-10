"""Abstract VCS interface for Chronicler."""

from abc import ABC, abstractmethod

from chronicler_core.vcs.models import FileNode, RepoMetadata


class VCSProvider(ABC):
    """Abstract base class for VCS providers.

    Defines the interface for crawling repository structure and metadata,
    used by the Orchestrator to bootstrap Technical Ledgers.
    """

    @abstractmethod
    async def list_repos(self, org_or_user: str) -> list[RepoMetadata]:
        """List repositories for a given organization or user."""
        ...

    @abstractmethod
    async def get_repo_metadata(self, repo_id: str) -> RepoMetadata:
        """Get full metadata for a specific repository.

        Args:
            repo_id: Repository identifier in "owner/repo" format.
        """
        ...

    @abstractmethod
    async def get_file_tree(self, repo_id: str, path: str = "") -> list[FileNode]:
        """List files and directories at a given path in the repository.

        Args:
            repo_id: Repository identifier in "owner/repo" format.
            path: Directory path within the repo (empty string for root).
        """
        ...

    @abstractmethod
    async def get_file_content(self, repo_id: str, path: str) -> str:
        """Fetch decoded text content of a file.

        Args:
            repo_id: Repository identifier in "owner/repo" format.
            path: File path within the repository.
        """
        ...
