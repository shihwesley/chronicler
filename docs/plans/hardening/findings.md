# Findings & Decisions

## Goal
Remediate all 34 code review findings (P0-P3) before Chronicler Lite ships.

## Priority
Quality — proper fixes, real validation, production-ready. No quick patches.

## Approach
Spec-driven: 5 specs across 2 phases, 3 sprints. Independent specs run in parallel (Phase 1 Sprint 1), dependent specs run after their prerequisites.

## Requirements
- All P0 (3) and P1 (14) findings fixed with tests
- All P2 (12) findings fixed with tests
- P3 (5) findings fixed opportunistically when touching the same file
- Zero test regressions (496 existing tests must pass)
- No behavior changes to public API surface

## Research Findings
- Pydantic v2 `model_config = ConfigDict(frozen=True)` prevents mutable model issues
- `Path.resolve().is_relative_to()` available in Python 3.9+ — safe to use
- Anthropic SDK has `anthropic.APIError` base, `RateLimitError`, `AuthenticationError` subclasses
- OpenAI SDK has `openai.OpenAIError` base with similar hierarchy
- Google's `google.generativeai` deprecated — Gemini adapter needs `google-genai` migration eventually (separate task, not in this plan)

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Common `LLMError` wrapper | Callers catch one type instead of 4 provider-specific exceptions |
| Env var allowlist (not blocklist) | Safer default — only known vars expand |
| Warn on non-localhost Ollama (not block) | Remote Ollama is a valid use case |
| Frozen MerkleNode via dataclass(frozen=True) | Prevents accidental mutation, uses replace() for updates |
| Split QueuePlugin → BasicQueue + DeadLetterQueue | ISP compliance, simpler implementations for basic use |
| Delete RendererPlugin entirely | No implementations exist, YAGNI |
| Rename config LLMConfig → LLMSettings | Disambiguates from runtime LLMConfig |
