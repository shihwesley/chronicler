"""YAML config loading with env var expansion."""

import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ChroniclerConfig


def load_config(cli_path: str | None = None) -> ChroniclerConfig:
    """Load config with resolution order: CLI > project-local > user-global > defaults."""
    config_paths = [
        Path(cli_path) if cli_path else None,
        Path("./chronicler.yaml"),
        Path.home() / ".chronicler" / "config.yaml",
    ]

    for path in config_paths:
        if path and path.exists():
            try:
                with open(path) as f:
                    raw = yaml.safe_load(f)
                if raw is None:
                    continue
                raw = _expand_env_vars(raw)
                return ChroniclerConfig(**raw)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {path}: {e}") from e
            except ValidationError as e:
                raise ValueError(f"Invalid config in {path}: {e}") from e

    return ChroniclerConfig()


def _expand_env_vars(obj: object) -> object:
    """Recursively expand ${VAR} references in strings."""
    if isinstance(obj, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), obj)
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(v) for v in obj]
    return obj


# Default YAML template for `chronicler config init`
DEFAULT_CONFIG_TEMPLATE = """\
# chronicler.yaml

# LLM Provider
llm:
  provider: "anthropic"        # anthropic | openai | google
  model: "claude-sonnet-4-20250514"
  api_key_env: "ANTHROPIC_API_KEY"
  max_tokens: 4096
  timeout: 60
  max_retries: 3
  retry_delay: 1.0

# VCS Provider
vcs:
  provider: "github"           # github | azure | gitlab
  token_env: "GITHUB_TOKEN"
  # allowed_orgs: []
  rate_limit_buffer: 100

# Output
output:
  base_dir: ".chronicler"
  create_index: true
  validation: "strict"         # strict | warn | off

# Monorepo Detection
monorepo:
  detection: "auto"            # auto | manifest-only | convention-only | disabled
  # package_dirs: [packages, apps, services, libs, modules]

# Queue (enterprise)
# queue:
#   provider: "local"          # sqs | pubsub | servicebus | local
#   max_workers: 5

# Document Conversion
document_conversion:
  enabled: true
  formats:
    pdf: true
    docx: true
    pptx: true
    xlsx: false
    images: true
  ocr:
    enabled: true
    use_llm: false               # use LLM for OCR (slower, more accurate)
  max_file_size_mb: 50
  max_pages: 100
  cache:
    enabled: true
    directory: ".chronicler/doc_cache"
    ttl_days: 7

# Logging
log_level: "info"              # debug | info | warn | error
log_format: "text"             # text | json
"""
