---
name: freshness-spec
phase: 1
sprint: 2
parent: manifest
depends_on: [packaging-spec]
status: completed
created: 2026-02-10
---

# Freshness Spec: Merkle Staleness Detection + Auto-Regeneration

## Goal

Detect when source code changes make existing `.tech.md` files stale, and provide the mechanism to auto-regenerate them. This is the engine behind Chronicler's "set it and forget it" promise.

## Requirements

1. Merkle hash manifest (`.chronicler/.merkle.json`) maps each `.tech.md` to hashes of its source files
2. Staleness check: compare current file hashes against manifest — flag diffs
3. Incremental regeneration: only re-draft `.tech.md` files whose source files changed
4. File watcher mode: watch source files for changes, debounce, mark stale (for daemon/hook use)
5. Batch mode: scan entire project, report all stale docs, regenerate in priority order
6. The staleness check itself must be fast (<500ms for a 100-file project) — no LLM calls, just hashing

## Acceptance Criteria

- [ ] `.chronicler/.merkle.json` is created/updated on every generation
- [ ] `chronicler_core.freshness.check_staleness(project_path)` returns list of stale `.tech.md` files
- [ ] Modifying a source file makes its `.tech.md` appear in the stale list
- [ ] Adding a new source file (with no `.tech.md`) is flagged as "uncovered"
- [ ] Deleting a source file flags its `.tech.md` as "orphaned"
- [ ] Staleness check runs in <500ms for 100-file project (no LLM calls)
- [ ] `chronicler_core.freshness.regenerate_stale(project_path)` re-drafts only stale files

## Technical Approach

Merkle manifest structure:

```json
{
  "version": 1,
  "generated_at": "2026-02-10T12:00:00Z",
  "entries": {
    ".chronicler/api-service.tech.md": {
      "source_files": ["src/api/service.py", "src/api/routes.py"],
      "source_hash": "sha256:abc123...",
      "tech_md_hash": "sha256:def456...",
      "generated_at": "2026-02-10T12:00:00Z"
    }
  }
}
```

Staleness detection:
1. For each entry, hash current source files → compare to `source_hash`
2. If different → stale
3. Scan for source files with no entry → uncovered
4. Scan for entries whose source files don't exist → orphaned

File watcher (for hooks/daemon):
- Use `watchdog` library for filesystem events
- Debounce: 2 seconds after last change before marking stale
- Batch changes within debounce window

## Files to Create/Modify

- `packages/chronicler-core/src/chronicler_core/freshness/__init__.py`
- `packages/chronicler-core/src/chronicler_core/freshness/merkle.py` — hash manifest CRUD
- `packages/chronicler-core/src/chronicler_core/freshness/staleness.py` — check + report
- `packages/chronicler-core/src/chronicler_core/freshness/watcher.py` — file system watcher
- `packages/chronicler-core/src/chronicler_core/freshness/regenerator.py` — incremental re-draft
- `tests/test_freshness.py`

## Tasks

1. Design merkle manifest schema and CRUD operations
2. Implement staleness checker (hash comparison)
3. Implement file watcher with debounce
4. Implement incremental regenerator (calls drafter for stale files only)
5. Tests: staleness detection, file change scenarios, orphan/uncovered detection

## Dependencies

- **Upstream:** packaging-spec (needs monorepo structure)
- **Downstream:** hooks-skill-spec, vscode-spec, obsidian-spec (all need freshness checking)
