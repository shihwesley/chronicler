---
name: error-handling-spec
phase: 1
sprint: 1
parent: null
depends_on: []
status: pending
created: 2026-02-10
severity: P1
finding_count: 10
---

# Error Handling Spec

## Overview

10 findings about missing or inadequate error handling. The LLM adapters have zero try/except around API calls. File I/O operations crash on disk errors. Plugin imports and YAML parsing fail silently. The config loader swallows missing env vars.

The pattern: agent-generated code handles the happy path well but doesn't account for network failures, disk errors, or missing dependencies. For a tool that runs unattended (via hooks), this is a real problem.

## Requirements

- REQ-1: All 4 LLM adapters catch provider-specific exceptions and wrap them in a common `LLMError`
- REQ-2: LLM errors include context: which provider, what operation, whether it's retryable
- REQ-3: File I/O in `output/writer.py` catches `OSError` for both write and YAML read
- REQ-4: `merkle/scanner.py` manifest parse catches `(json.JSONDecodeError, OSError)`
- REQ-5: `plugins/loader.py` logs warning on import failure before returning None
- REQ-6: `storage/memvid_storage.py` logs warning on YAML parse failure
- REQ-7: `config/loader.py` raises or warns when referenced env var is missing (not empty string)
- REQ-8: `freshness/watcher.py` stale set is bounded (max 10,000 entries)
- REQ-9: All new error handling has corresponding test coverage

## Acceptance Criteria

- [ ] `claude.py`: `anthropic.APIError` caught, wrapped in `LLMError` with provider name
- [ ] `openai_adapter.py`: `openai.OpenAIError` caught, wrapped in `LLMError`
- [ ] `gemini.py`: Google API exceptions caught, wrapped in `LLMError`
- [ ] `ollama.py`: `httpx.HTTPError`, `httpx.ConnectError` caught, wrapped in `LLMError`
- [ ] `ollama.py`: `json.JSONDecodeError` on streaming lines handled (skip line, log warning)
- [ ] `writer.py:61`: `OSError` caught with message about write failure
- [ ] `writer.py:81`: `yaml.YAMLError` caught, treats as empty index with warning
- [ ] `scanner.py:209`: `json.JSONDecodeError` caught, returns empty DiffResult
- [ ] `loader.py:41`: missing env var raises `ValueError` or logs warning (not silent empty string)
- [ ] `plugins/loader.py:80`: `logger.warning()` before returning None on import failure
- [ ] `memvid_storage.py:132`: `logger.warning()` before returning empty dict
- [ ] `watcher.py:57`: stale set capped at 10,000 with oldest eviction or periodic clear
- [ ] New `LLMError` exception class defined in `llm/models.py` or `llm/__init__.py`
- [ ] All existing tests pass + new error-path tests added

## Files to Modify

| File | Change | Finding # |
|------|--------|-----------|
| `chronicler_core/llm/__init__.py` or `llm/models.py` | Define `LLMError` exception | #8 |
| `chronicler_core/llm/claude.py` | Wrap API calls in try/except → LLMError | #8 |
| `chronicler_core/llm/openai_adapter.py` | Wrap API calls in try/except → LLMError | #8 |
| `chronicler_core/llm/gemini.py` | Wrap API calls in try/except → LLMError | #8 |
| `chronicler_core/llm/ollama.py` | Wrap API + streaming in try/except → LLMError | #8, #9 |
| `chronicler_core/output/writer.py` | Add OSError/YAMLError handling | #11 |
| `chronicler_core/merkle/scanner.py` | Add JSON parse error handling in _fallback_diff | #10 |
| `chronicler_core/config/loader.py` | Raise on missing env vars | #17 |
| `chronicler_core/plugins/loader.py` | Add logger.warning before return None | #12 |
| `chronicler_lite/storage/memvid_storage.py` | Add logger.warning before return empty | #13 |
| `chronicler_core/freshness/watcher.py` | Bound stale set size | #28 |
| `tests/test_error_handling.py` (new) | Error-path tests for all changes | all |

## Technical Approach

### LLMError exception

```python
class LLMError(Exception):
    """Wraps provider-specific exceptions with context."""
    def __init__(self, provider: str, operation: str, cause: Exception, retryable: bool = False):
        self.provider = provider
        self.operation = operation
        self.retryable = retryable
        super().__init__(f"{provider} {operation} failed: {cause}")
        self.__cause__ = cause
```

### LLM adapter pattern

```python
async def generate(self, system: str, user: str) -> LLMResponse:
    try:
        resp = await self._client.messages.create(...)
        return LLMResponse(text=resp.content[0].text, usage=...)
    except anthropic.APIError as e:
        raise LLMError("claude", "generate", e, retryable=isinstance(e, anthropic.RateLimitError)) from e
```

### Bounded watcher set

```python
_MAX_STALE = 10_000

def _on_modified(self, event):
    if len(self._stale) >= _MAX_STALE:
        self._stale.pop()  # drop arbitrary element — set has no ordering, but prevents unbounded growth
    self._stale.add(src)
```

## Tasks

1. Define `LLMError` exception class
2. Add error handling to all 4 LLM adapters (claude, openai, gemini, ollama)
3. Fix Ollama streaming JSON parse (finding #9)
4. Add error handling to writer.py file I/O (finding #11)
5. Add error handling to scanner.py manifest parse (finding #10)
6. Fix config loader missing env var behavior (finding #17)
7. Add warning logs to plugin loader and memvid storage (findings #12, #13)
8. Bound watcher stale set (finding #28)
9. Write error-path tests for all changes

## Dependencies

- Upstream: none
- Downstream: type-invariants-spec (error patterns inform validation approach)
