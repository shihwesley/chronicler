"""TransformPipeline — runs ordered transforms on .tech.md content before writing to vault."""

from abc import ABC, abstractmethod


class Transform(ABC):
    @abstractmethod
    def apply(self, content: str, metadata: dict) -> str:
        """Transform markdown content. metadata contains parsed frontmatter."""
        ...


class TransformPipeline:
    def __init__(self, transforms: list[Transform]):
        self.transforms = transforms

    def apply(self, content: str, metadata: dict) -> str:
        for t in self.transforms:
            content = t.apply(content, metadata)
        return content
