---
name: security-uat-spec
phase: 1
sprint: 2
parent: root-spec
depends_on: [packaging-uat-spec]
status: draft
created: 2026-02-10
---

# Security UAT Spec

## Requirements
- Existing security tests pass (from code review hardening)
- Path traversal prevention verified
- Input sanitization on user-provided paths
- API key handling safe (no logging, no leaking)
- Environment variable fallback safe when vars missing

## Acceptance Criteria
- [ ] All existing security-related tests pass
- [ ] Path traversal attempt rejected (../../etc/passwd style inputs)
- [ ] Filenames with special chars handled safely
- [ ] API keys never appear in logs or output files
- [ ] Missing env var produces clear error, not stack trace
- [ ] No arbitrary code execution from user config files
- [ ] YAML parsing uses safe_load, not load

## Technical Approach
Run existing test suite for security tests. Add manual edge-case probes for anything not covered. Verify through code audit that hardening from code review is intact.

## Files
- Existing test files with security tests
- packages/chronicler-core/src/ (config loading, path handling)
- packages/chronicler-lite/src/ (any user-facing input points)

## Tasks
1. Run existing security test suite, log results
2. Manual path traversal probes
3. Verify API key handling (grep for logging patterns)
4. Test missing env var behavior
5. Verify YAML safe_load usage across codebase

## Dependencies
- Upstream: packaging-uat-spec (installed package to test)
- Downstream: none (terminal spec)
