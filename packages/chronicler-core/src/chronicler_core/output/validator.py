"""YAML schema validator for .tech.md files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Required top-level YAML fields and their expected types.
_REQUIRED_FIELDS: dict[str, type] = {
    "component_id": str,
    "version": str,
    "layer": str,
}

# Optional top-level fields and their expected types.
_OPTIONAL_FIELDS: dict[str, type] = {
    "owner_team": str,
    "security_level": str,
    "governance": dict,
    "edges": list,
}


class ValidationResult(BaseModel):
    """Result of validating a single .tech.md file."""

    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    path: str = ""


def _split_frontmatter(content: str) -> tuple[str | None, str]:
    """Split a .tech.md file into YAML frontmatter and body.

    Returns (yaml_str, body). yaml_str is None if no frontmatter found.
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing --- marker (skip the opening one)
    end = content.find("---", 3)
    if end == -1:
        return None, content

    yaml_str = content[3:end].strip()
    body = content[end + 3:]
    return yaml_str, body


class TechMdValidator:
    """Validates .tech.md files against the expected YAML schema.

    Supports three modes via OutputConfig.validation:
      - "strict": missing required fields or type errors → invalid
      - "warn": log warnings but still return valid
      - "off": skip validation, always return valid
    """

    def __init__(self, mode: str = "strict") -> None:
        if mode not in ("strict", "warn", "off"):
            raise ValueError(f"Unknown validation mode: {mode!r}")
        self.mode = mode

    def validate_file(self, path: str | Path) -> ValidationResult:
        """Validate a single .tech.md file."""
        path = Path(path)
        result = ValidationResult(path=str(path))

        if self.mode == "off":
            return result

        if not path.exists():
            result.errors.append(f"File not found: {path}")
            result.valid = False
            return result

        content = path.read_text(encoding="utf-8")
        return self._validate_content(content, result)

    def validate_content(self, content: str, source: str = "<string>") -> ValidationResult:
        """Validate .tech.md content from a string."""
        result = ValidationResult(path=source)

        if self.mode == "off":
            return result

        return self._validate_content(content, result)

    def validate_directory(self, path: str | Path) -> list[ValidationResult]:
        """Validate all .tech.md files in a directory."""
        path = Path(path)
        results: list[ValidationResult] = []

        if not path.is_dir():
            r = ValidationResult(path=str(path), valid=False)
            r.errors.append(f"Not a directory: {path}")
            results.append(r)
            return results

        for md_file in sorted(path.rglob("*.tech.md")):
            results.append(self.validate_file(md_file))

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_content(self, content: str, result: ValidationResult) -> ValidationResult:
        """Run schema checks against raw file content."""
        yaml_str, _body = _split_frontmatter(content)

        if yaml_str is None:
            self._add_issue(result, "No YAML frontmatter found (missing --- markers)")
            return result

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as exc:
            self._add_issue(result, f"YAML parse error: {exc}")
            return result

        if not isinstance(data, dict):
            self._add_issue(result, f"Frontmatter is not a mapping, got {type(data).__name__}")
            return result

        # Check required fields
        for field, expected_type in _REQUIRED_FIELDS.items():
            if field not in data:
                self._add_issue(result, f"Missing required field: {field}")
            elif not isinstance(data[field], expected_type):
                self._add_issue(
                    result,
                    f"Field {field!r} should be {expected_type.__name__}, "
                    f"got {type(data[field]).__name__}",
                )

        # Check verification_status — lives inside governance dict
        governance = data.get("governance")
        if isinstance(governance, dict):
            vs = governance.get("verification_status")
            if vs is None:
                self._add_issue(result, "Missing required field: governance.verification_status")
            elif vs != "ai_draft":
                self._add_issue(
                    result,
                    f"governance.verification_status must be 'ai_draft', got {vs!r}",
                )
        elif governance is not None:
            self._add_issue(result, f"Field 'governance' should be dict, got {type(governance).__name__}")
        else:
            # governance key missing entirely — also check top-level as fallback
            vs = data.get("verification_status")
            if vs is None:
                self._add_issue(result, "Missing required field: governance.verification_status")
            elif vs != "ai_draft":
                self._add_issue(
                    result,
                    f"verification_status must be 'ai_draft', got {vs!r}",
                )

        # Check optional field types
        for field, expected_type in _OPTIONAL_FIELDS.items():
            if field in data and not isinstance(data[field], expected_type):
                self._add_issue(
                    result,
                    f"Field {field!r} should be {expected_type.__name__}, "
                    f"got {type(data[field]).__name__}",
                    warning=True,
                )

        return result

    def _add_issue(self, result: ValidationResult, message: str, *, warning: bool = False) -> None:
        """Add an error or warning depending on mode."""
        if self.mode == "strict":
            if warning:
                result.warnings.append(message)
            else:
                result.errors.append(message)
                result.valid = False
        elif self.mode == "warn":
            # Everything becomes a warning; file stays valid
            result.warnings.append(message)
            logger.warning("%s: %s", result.path, message)
