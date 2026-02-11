---
name: init
description: First-time project setup — detects language, generates config, builds merkle tree, generates initial docs
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
---

# Chronicler Init

Run first-time setup for the current project and generate initial `.tech.md` documentation.

## Step 1: Initialize project structure

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.init
```

This detects the project type, generates `chronicler.yaml`, and builds a merkle tree.

## Step 2: Generate initial .tech.md files

After init completes, generate documentation for the project's source files. You are the LLM — read each source file and write a `.tech.md` for it.

For each source file tracked by the merkle tree:

1. Read the source file
2. Write a `.tech.md` file in `.chronicler/` with this format:

```markdown
---
component_id: "<relative-path-to-source>"
version: "0.1.0"
layer: "<service|library|config|test|ui|infra>"
owner_team: "unknown"
security_level: "low"
governance:
  business_impact: null
  verification_status: "ai_draft"
  visibility: "internal"
edges:
  - target: "<component_id of imported/used module>"
    relationship: "imports"
---

## Purpose
<1-2 sentence summary of what this file does>

## Key Components
<list the main classes, functions, or exports with one-line descriptions>

## Dependencies
<what this file imports or depends on>

## Architectural Notes
<how this fits into the broader system, any non-obvious design decisions>
```

The filename should be the source path with `/` replaced by `--`, e.g. `src/utils/auth.ts` becomes `.chronicler/src--utils--auth.ts.tech.md`.

Process files in batches — read 5-10 source files, write their `.tech.md` files, then continue with the next batch. Skip test files, config files, and generated files unless they contain meaningful logic.

## After init

Hooks run automatically via the plugin:
- **SessionStart**: prints a freshness summary
- **PostToolUse (Write/Edit)**: marks edited files as stale candidates
- **PreToolUse (Read)**: warns when reading a `.tech.md` backed by stale source
