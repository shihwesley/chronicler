---
name: packaging-spec
phase: 1
sprint: 1
parent: manifest
depends_on: []
status: completed
created: 2026-02-10
---

# Packaging Spec: Monorepo Restructure + pip Install

## Goal

Restructure the flat `chronicler/` directory into a monorepo with `chronicler-core` as a shared package, installable via `pip install chronicler-lite`.

## Requirements

1. Extract current code (27 .py files) into `packages/chronicler-core/`
2. Create `packages/chronicler-lite/` with local-specific implementations (SQLite queue, JSON graph)
3. Set up uv workspaces at the root `pyproject.toml`
4. `pip install chronicler-lite` pulls in `chronicler-core` as a dependency
5. All existing tests pass against the new layout (import paths updated)
6. Console script entry point: `chronicler` command available after install

## Acceptance Criteria

- [ ] `pip install -e packages/chronicler-lite` succeeds
- [ ] `python -c "from chronicler_core.vcs import GitHubProvider"` works
- [ ] `python -c "from chronicler_lite.queue import SQLiteQueue"` works
- [ ] `pytest tests/` passes with 0 failures
- [ ] `chronicler --version` prints version after install

## Technical Approach

Follow the layout from `docs/plans/2026-02-02-product-architecture-design.md`:

```
chronicler/
├── packages/
│   ├── chronicler-core/
│   │   ├── pyproject.toml
│   │   └── src/chronicler_core/
│   │       ├── __init__.py
│   │       ├── vcs/
│   │       ├── llm/
│   │       ├── converter/
│   │       ├── drafter/
│   │       ├── output/
│   │       └── config/
│   └── chronicler-lite/
│       ├── pyproject.toml
│       └── src/chronicler_lite/
│           ├── __init__.py
│           ├── queue/sqlite_queue.py
│           ├── graph/json_graph.py
│           └── cli.py
├── pyproject.toml  (workspace root)
└── tests/
```

## Files to Create/Modify

- `pyproject.toml` (root) — uv workspace config
- `packages/chronicler-core/pyproject.toml` — core package metadata
- `packages/chronicler-core/src/chronicler_core/**` — moved from `chronicler/`
- `packages/chronicler-lite/pyproject.toml` — lite package, depends on core
- `packages/chronicler-lite/src/chronicler_lite/**` — SQLite queue, JSON graph, CLI
- `tests/**` — update imports from `chronicler.*` → `chronicler_core.*`

## Tasks

1. Create monorepo workspace root with uv
2. Move existing code into `packages/chronicler-core/`
3. Create `packages/chronicler-lite/` skeleton with SQLite queue + JSON graph
4. Update all test imports and verify passing
5. Add console_scripts entry point for `chronicler` CLI

## Dependencies

- **Upstream:** None (root spec)
- **Downstream:** llm-adapters-spec, freshness-spec (both need the package structure)
