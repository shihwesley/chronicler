"""AI Drafter subsystem — generates .tech.md documents from repo context."""

from chronicler_core.drafter.context import ContextBuilder
from chronicler_core.drafter.dependency_parser import PARSERS, DependencyParser
from chronicler_core.drafter.drafter import Drafter
from chronicler_core.drafter.file_tree import FileTreeFormatter
from chronicler_core.drafter.key_files import KeyFileLocator
from chronicler_core.drafter.models import (
    FrontmatterModel,
    GovernanceModel,
    PromptContext,
    TechDoc,
)

__all__ = [
    "ContextBuilder",
    "DependencyParser",
    "Drafter",
    "FileTreeFormatter",
    "FrontmatterModel",
    "GovernanceModel",
    "KeyFileLocator",
    "PARSERS",
    "PromptContext",
    "TechDoc",
]
