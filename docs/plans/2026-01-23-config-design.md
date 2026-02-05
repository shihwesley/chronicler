# Configuration Design for Chronicler

**Date:** 2026-01-23
**Status:** Proposed
**Author:** Claude + User

## Summary

YAML-based configuration with environment variable support. Supports project-local and user-global config files.

## File Format

YAML chosen for:
- Human-readable with comments
- Matches `.tech.md` frontmatter format
- Widely supported

## Config File Locations

**Resolution order (highest to lowest priority):**
1. CLI flags (`--config <path>`)
2. Environment variables
3. Project-local: `./chronicler.yaml`
4. User global: `~/.chronicler/config.yaml`
5. Built-in defaults

## Schema

```yaml
# chronicler.yaml

# =============================================================================
# LLM Provider Configuration
# =============================================================================
llm:
  # Provider: anthropic | openai | google
  provider: "anthropic"

  # Model identifier
  model: "claude-sonnet-4-20250514"

  # API key - read from environment variable (DO NOT hardcode)
  api_key_env: "ANTHROPIC_API_KEY"

  # Generation settings
  max_tokens: 4096
  timeout: 60  # seconds

  # Retry settings (inherited from LLM interface design)
  max_retries: 3
  retry_delay: 1.0

# =============================================================================
# Queue Configuration (for enterprise scale)
# =============================================================================
queue:
  # Provider: sqs | pubsub | servicebus | local
  # Use "local" for single-machine / MVP mode
  provider: "local"

  # Queue URLs (use env vars in production)
  url: "${AWS_SQS_URL}"
  dlq_url: "${AWS_SQS_DLQ_URL}"

  # Worker pool size
  max_workers: 5

  # Visibility timeout (seconds)
  visibility_timeout: 300

# =============================================================================
# VCS Configuration
# =============================================================================
vcs:
  # Provider: github | azure | gitlab
  provider: "github"

  # Auth token - read from environment variable
  token_env: "GITHUB_TOKEN"

  # Optional: restrict crawling to specific orgs
  allowed_orgs: []
  #  - "my-company"
  #  - "my-company-internal"

  # Rate limit safety margin (pause when remaining < this)
  rate_limit_buffer: 100

# =============================================================================
# Output Configuration
# =============================================================================
output:
  # Base directory for .tech.md files
  base_dir: ".chronicler"

  # Generate _index.yaml for monorepos
  create_index: true

  # Validation mode: strict | warn | off
  # - strict: fail if validation fails
  # - warn: write file but log warnings
  # - off: no validation
  validation: "strict"

# =============================================================================
# Monorepo Detection
# =============================================================================
monorepo:
  # Detection mode: auto | manifest-only | convention-only | disabled
  detection: "auto"

  # Convention directories to scan (if not using manifest)
  package_dirs:
    - "packages"
    - "apps"
    - "services"
    - "libs"
    - "modules"

# =============================================================================
# Logging
# =============================================================================
log_level: "info"  # debug | info | warn | error
log_format: "text"  # text | json
```

## Environment Variable Mapping

Config values can reference env vars with `${VAR_NAME}` syntax:

```yaml
llm:
  api_key_env: "ANTHROPIC_API_KEY"  # Reads $ANTHROPIC_API_KEY
queue:
  url: "${AWS_SQS_URL}"  # Reads $AWS_SQS_URL
```

## Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import Literal

class LLMConfig(BaseModel):
    provider: Literal["anthropic", "openai", "google"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0

class QueueConfig(BaseModel):
    provider: Literal["sqs", "pubsub", "servicebus", "local"] = "local"
    url: str | None = None
    dlq_url: str | None = None
    max_workers: int = 5
    visibility_timeout: int = 300

class VCSConfig(BaseModel):
    provider: Literal["github", "azure", "gitlab"] = "github"
    token_env: str = "GITHUB_TOKEN"
    allowed_orgs: list[str] = []
    rate_limit_buffer: int = 100

class OutputConfig(BaseModel):
    base_dir: str = ".chronicler"
    create_index: bool = True
    validation: Literal["strict", "warn", "off"] = "strict"

class MonorepoConfig(BaseModel):
    detection: Literal["auto", "manifest-only", "convention-only", "disabled"] = "auto"
    package_dirs: list[str] = ["packages", "apps", "services", "libs", "modules"]

class ChroniclerConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    vcs: VCSConfig = Field(default_factory=VCSConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    monorepo: MonorepoConfig = Field(default_factory=MonorepoConfig)
    log_level: Literal["debug", "info", "warn", "error"] = "info"
    log_format: Literal["text", "json"] = "text"
```

## Loading Logic

```python
import os
import yaml
from pathlib import Path

def load_config(cli_path: str | None = None) -> ChroniclerConfig:
    """Load config with resolution order."""
    config_paths = [
        cli_path,
        Path("./chronicler.yaml"),
        Path.home() / ".chronicler" / "config.yaml",
    ]

    for path in config_paths:
        if path and Path(path).exists():
            with open(path) as f:
                raw = yaml.safe_load(f)
                raw = _expand_env_vars(raw)
                return ChroniclerConfig(**raw)

    return ChroniclerConfig()  # Defaults

def _expand_env_vars(obj):
    """Recursively expand ${VAR} in strings."""
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        return os.environ.get(var_name, "")
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(v) for v in obj]
    return obj
```

## Dependencies

```
pydantic>=2.0.0
pyyaml>=6.0.0
```
