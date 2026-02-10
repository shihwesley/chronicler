"""Chronicler Core - shared library for VCS crawling, LLM drafting, and document generation."""

from chronicler_core.vcs import VCSProvider, GitHubProvider, VCSCrawler, create_provider
from chronicler_core.llm import LLMProvider, create_llm_provider
from chronicler_core.drafter import Drafter, ContextBuilder
from chronicler_core.output import TechMdWriter, TechMdValidator
from chronicler_core.converter import DocumentConverter
from chronicler_core.config import ChroniclerConfig, load_config

__version__ = "0.1.0"

__all__ = [
    "ChroniclerConfig",
    "ContextBuilder",
    "DocumentConverter",
    "Drafter",
    "GitHubProvider",
    "LLMProvider",
    "TechMdValidator",
    "TechMdWriter",
    "VCSCrawler",
    "VCSProvider",
    "create_llm_provider",
    "create_provider",
    "load_config",
]
