---
name: error-paths-spec
phase: 2
sprint: 1
parent: root-spec
depends_on: [install-uat-spec]
status: draft
created: 2026-02-10
---

# Error Paths UAT Spec

## Requirements
- Graceful failure when dependencies missing
- Clear errors for bad config files
- Network failure handling (API unreachable)
- Permission errors handled (read-only dirs)
- Empty / nonexistent repos handled
- Oversized repos handled (if limits exist)

## Acceptance Criteria
- [ ] Missing chronicler-core dep: clear error message
- [ ] Malformed YAML config: parse error with line number, no crash
- [ ] Invalid API key: auth error message, no stack trace
- [ ] Network timeout: retry or clear timeout message
- [ ] Read-only output dir: permission error, not crash
- [ ] Empty git repo (no commits): handled gracefully
- [ ] Non-git directory: clear "not a repo" or handled as plain dir
- [ ] Max file size exceeded: skip with warning, continue

## Technical Approach
Systematically break each input condition and verify the error output is human-readable, non-crashing, and actionable.

## Files
- Config loading code
- CLI entry points
- LLM adapter error handling
- File I/O paths

## Tasks
1. Test missing dependency scenarios
2. Test malformed config inputs
3. Test API/network failure scenarios
4. Test filesystem permission errors
5. Test edge-case repos (empty, non-git, oversized)

## Dependencies
- Upstream: install-uat-spec (working baseline to break)
- Downstream: none (terminal spec)
