---
name: security-hardening-spec
phase: 1
sprint: 1
parent: null
depends_on: []
status: pending
created: 2026-02-10
severity: P1
finding_count: 7
---

# Security Hardening Spec

## Overview

The code review found 7 security issues: 3 path traversal vulnerabilities, 1 SSRF risk, 1 command injection vector, 1 environment variable leak, and 1 merkle tree path construction issue. None are remotely exploitable (this is a local CLI tool), but all should be fixed before shipping because:

1. Users run this on their codebases — file write escapes could damage projects
2. Config files are user-editable — a copy-paste from a malicious source could trigger issues
3. Defense in depth is cheap here — the fixes are small and localized

## Requirements

- REQ-1: Output writer validates final path resolves under `base_dir` before writing
- REQ-2: Hook `post_write.py` validates `file_path` is under `project_root` before any filesystem ops
- REQ-3: Merkle scanner validates `mercator_path` is an absolute path to an existing file
- REQ-4: Ollama adapter validates `base_url` is localhost/127.0.0.1 or explicitly configured host
- REQ-5: Config env var expansion restricted to allowlist of expected variable names
- REQ-6: Merkle tree `_find_doc_for_source` validates paths resolve under root
- REQ-7: All fixes have corresponding test cases

## Acceptance Criteria

- [ ] `writer.py`: path traversal with `../../../../etc/cron.d/evil` as component_id is rejected
- [ ] `writer.py`: absolute path component_id like `/tmp/malicious` is rejected
- [ ] `post_write.py`: file_path outside project_root is rejected before touching `.stale-candidates`
- [ ] `scanner.py`: `mercator_path` pointing to `/bin/rm` or relative path is rejected
- [ ] `ollama.py`: `base_url` of `http://169.254.169.254/` is rejected
- [ ] `ollama.py`: `base_url` with CRLF injection is rejected
- [ ] `loader.py`: `${AWS_SECRET_ACCESS_KEY}` in YAML does not expand (not in allowlist)
- [ ] `loader.py`: `${ANTHROPIC_API_KEY}` does expand (in allowlist)
- [ ] `tree.py`: `source_rel` with `..` sequences produces path under root or is rejected
- [ ] All existing tests pass

## Files to Modify

| File | Change | Finding # |
|------|--------|-----------|
| `packages/chronicler-core/src/chronicler_core/output/writer.py` | Add `resolve().is_relative_to()` check after sanitization | #5 |
| `packages/chronicler-lite/src/chronicler_lite/hooks/post_write.py` | Move `relative_to()` check earlier, before any file ops | #6 |
| `packages/chronicler-core/src/chronicler_core/merkle/scanner.py` | Validate `mercator_path` is absolute + exists + not a directory | #4 |
| `packages/chronicler-core/src/chronicler_core/llm/ollama.py` | URL validation on `base_url` (scheme, host allowlist, no CRLF) | #7 |
| `packages/chronicler-core/src/chronicler_core/config/loader.py` | Env var expansion allowlist | #18 |
| `packages/chronicler-core/src/chronicler_core/merkle/tree.py` | Path boundary check in `_find_doc_for_source` | #24 |
| `tests/test_security.py` (new) | Security-specific test file for all path/SSRF/injection tests | all |

## Technical Approach

### Path traversal guard pattern

```python
dest = self.base_dir / f"{safe_name}.tech.md"
if not dest.resolve().is_relative_to(self.base_dir.resolve()):
    raise ValueError(f"Path escape detected: {component_id}")
```

### URL validation for Ollama

```python
from urllib.parse import urlparse

def _validate_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Ollama base_url must be http(s), got {parsed.scheme}")
    if "\r" in url or "\n" in url:
        raise ValueError("CRLF injection detected in base_url")
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if parsed.hostname not in allowed_hosts:
        logger.warning("Ollama base_url %s is not localhost — ensure this is intentional", parsed.hostname)
    return url
```

Note: We warn on non-localhost but don't block it. Users with remote Ollama setups need this to work.

### Env var allowlist

```python
_ALLOWED_ENV_VARS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "GITHUB_TOKEN", "OLLAMA_HOST", "CHRONICLER_LOG_LEVEL",
}

def _expand_env_vars(raw: dict) -> dict:
    def replacer(m):
        var_name = m.group(1)
        if var_name not in _ALLOWED_ENV_VARS:
            raise ValueError(f"Env var ${{{var_name}}} not in allowlist. Add to _ALLOWED_ENV_VARS or use direct value.")
        return os.environ.get(var_name, "")
    # ... apply to string values recursively
```

## Tasks

1. Add path boundary validation to `output/writer.py` (finding #5)
2. Reorder validation in `hooks/post_write.py` (finding #6)
3. Validate `mercator_path` in `merkle/scanner.py` (finding #4)
4. Add URL validation to `llm/ollama.py` (finding #7)
5. Implement env var expansion allowlist in `config/loader.py` (finding #18)
6. Add path boundary check to `merkle/tree.py` (finding #24)
7. Write `tests/test_security.py` with attack-scenario tests for all 6 fixes

## Dependencies

- Upstream: none
- Downstream: type-invariants-spec
