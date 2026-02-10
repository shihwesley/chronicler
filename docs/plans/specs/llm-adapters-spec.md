---
name: llm-adapters-spec
phase: 1
sprint: 2
parent: manifest
depends_on: [packaging-spec]
status: completed
created: 2026-02-10
---

# LLM Adapters Spec: Multi-Provider Interface

## Goal

Make Chronicler's AI drafter work with any LLM the user already has: Claude (API key or via Claude Code), OpenAI, Gemini, Ollama/local models. The user shouldn't need to switch providers — Chronicler uses whatever's available.

## Requirements

1. Provider interface (protocol/ABC) that all LLM adapters implement
2. Claude adapter (existing — extract and wrap)
3. OpenAI adapter (GPT-4o, GPT-4-turbo)
4. Gemini adapter (via google-genai SDK)
5. Ollama adapter (local models via HTTP API)
6. Auto-detection: if running inside Claude Code, use Claude's context; otherwise check for API keys in env/config
7. Fallback chain: configured provider → env vars → Claude Code context → error with clear message
8. Provider-specific prompt tuning (different models need slightly different system prompts)

## Acceptance Criteria

- [ ] `chronicler_core.llm.create_provider("claude")` returns working Claude adapter
- [ ] `chronicler_core.llm.create_provider("openai")` returns working OpenAI adapter
- [ ] `chronicler_core.llm.create_provider("ollama", model="llama3")` returns working Ollama adapter
- [ ] `chronicler_core.llm.create_provider("auto")` auto-detects best available provider
- [ ] Drafter produces valid .tech.md with each provider (may vary in quality)
- [ ] Missing API key gives a clear, actionable error message

## Technical Approach

Extend the existing `chronicler/llm/` module which already has a `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    async def generate(self, prompt: str, system: str | None = None) -> str: ...
    async def generate_structured(self, prompt: str, schema: type[T]) -> T: ...

class ProviderConfig(BaseModel):
    provider: Literal["claude", "openai", "gemini", "ollama", "auto"]
    model: str | None = None  # override default model
    api_key: str | None = None  # override env var
    base_url: str | None = None  # for Ollama or custom endpoints
```

Auto-detection priority:
1. Explicit config in `chronicler.yaml`
2. Environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
3. Ollama running on localhost:11434
4. Error: "No LLM provider found. Set provider in chronicler.yaml or export an API key."

## Files to Create/Modify

- `packages/chronicler-core/src/chronicler_core/llm/providers/claude.py` — extract from existing
- `packages/chronicler-core/src/chronicler_core/llm/providers/openai.py` — new
- `packages/chronicler-core/src/chronicler_core/llm/providers/gemini.py` — new
- `packages/chronicler-core/src/chronicler_core/llm/providers/ollama.py` — new
- `packages/chronicler-core/src/chronicler_core/llm/providers/__init__.py` — registry
- `packages/chronicler-core/src/chronicler_core/llm/auto_detect.py` — provider auto-detection
- `tests/test_llm_providers.py` — provider tests (mocked)

## Tasks

1. Define provider protocol and config model
2. Extract existing Claude adapter into provider pattern
3. Implement OpenAI adapter
4. Implement Gemini adapter
5. Implement Ollama adapter
6. Build auto-detection logic with fallback chain
7. Tests for each provider (mocked API calls)

## Dependencies

- **Upstream:** packaging-spec (needs monorepo structure)
- **Downstream:** hooks-skill-spec (needs to know which LLM to use)
