# LLM Interface Design for Chronicler AI Drafter

**Date:** 2026-01-23
**Status:** Proposed
**Author:** Claude + User

## Summary

Provider-agnostic LLM interface for generating `.tech.md` files. Cloud-first with support for Claude/GPT-4/Gemini via configuration. Local model support deferred.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Custom interface (not LiteLLM/LangChain) | Lean, controlled, fewer dependencies |
| Cloud-first | Faster MVP, defer local model complexity |
| Streaming support | Long documents (500-1500 words) benefit from incremental output |
| Retry at interface level | Consistent behavior across providers |
| Strict validation | Reject invalid output, don't write partial files |
| Mermaid validation | Ensure connectivity graphs are syntactically valid |

## Architecture

```
┌─────────────────────────────────────┐
│         ChroniclerDrafter           │  ← Business logic
├─────────────────────────────────────┤
│         LLMInterface (ABC)          │  ← Abstract contract
├──────────┬──────────┬───────────────┤
│ Claude   │ OpenAI   │ Gemini        │  ← Provider adapters
│ Adapter  │ Adapter  │ Adapter       │
└──────────┴──────────┴───────────────┘
```

## Interface Contract

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

@dataclass
class LLMConfig:
    provider: str       # "anthropic" | "openai" | "google"
    model: str          # e.g. "claude-sonnet-4-20250514", "gpt-4o"
    api_key: str
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 60.0
    max_tokens: int = 4096

class LLMInterface(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """Synchronous generation."""

    @abstractmethod
    def generate_stream(self, prompt: str, system: str = "") -> Iterator[str]:
        """Streaming generation - yields chunks."""

    @abstractmethod
    def generate_structured(self, prompt: str, schema: dict) -> dict:
        """Returns validated dict matching schema."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate tokens for context management."""

    def _with_retry(self, fn, *args, **kwargs):
        """Exponential backoff - shared by all adapters."""
        for attempt in range(self.config.max_retries):
            try:
                return fn(*args, **kwargs)
            except (RateLimitError, TimeoutError) as e:
                if attempt == self.config.max_retries - 1:
                    raise
                sleep(self.config.retry_delay * (2 ** attempt))
```

## Factory

```python
def create_llm(config: LLMConfig) -> LLMInterface:
    match config.provider:
        case "anthropic": return ClaudeAdapter(config)
        case "openai": return OpenAIAdapter(config)
        case "google": return GeminiAdapter(config)
        case _: raise ValueError(f"Unknown provider: {config.provider}")
```

## Input Context

```python
@dataclass
class RepoContext:
    name: str
    description: str
    languages: dict[str, int]
    default_branch: str
    topics: list[str]
    file_tree: list[str]
    readme_content: str | None
    package_json: dict | None
    dockerfile: str | None
    has_terraform: bool
```

## Output Validation

### YAML Frontmatter (Pydantic)

```python
from pydantic import BaseModel
from typing import Literal

class GovernanceBlock(BaseModel):
    business_impact: Literal["P0", "P1", "P2", "P3"] | None = None
    verification_status: Literal["ai_draft", "human_verified", "verified_in_ci"]
    visibility: Literal["internal", "confidential", "secret"]

class ChroniclerFrontmatter(BaseModel):
    component_id: str
    version: str = "0.1.0"
    owner_team: str = "unknown"
    layer: Literal["infrastructure", "logic", "api"]
    security_level: Literal["low", "medium", "high", "critical"] = "medium"
    governance: GovernanceBlock
    edges: list[dict] | None = None
    contracts: dict | None = None
```

### Mermaid Syntax

```python
import subprocess
import tempfile

def validate_mermaid(mermaid_code: str) -> tuple[bool, str | None]:
    with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False) as f:
        f.write(mermaid_code)
        f.flush()
        result = subprocess.run(
            ["mmdc", "-i", f.name, "-o", "/dev/null", "--quiet"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return False, result.stderr
        return True, None
```

### Validation Pipeline

1. Parse YAML frontmatter → Pydantic validation
2. Extract Mermaid blocks → mmdc validation
3. Both pass → write file
4. Either fails → retry once with error context
5. Still fails → raise `ValidationError`, do NOT write file

## Dependencies

```
anthropic>=0.40.0
openai>=1.50.0
google-generativeai>=0.8.0
pydantic>=2.0.0
pyyaml>=6.0.0
```

Optional: `@mermaid-js/mermaid-cli` (npm) for Mermaid validation

## Future Work

- Local model support (Ollama/vLLM)
- Async interface for concurrent processing
- Token budget management per repo
