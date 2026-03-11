---
name: chronicler
description: "Ambient .tech.md documentation generator with freshness tracking. Auto-generates technical documentation alongside source files and tracks staleness per file. Use when user says /chronicler, wants to set up documentation for a project, check doc freshness, regenerate stale docs, or configure chronicler settings. Supports init, status, regenerate, and configure subcommands."
metadata:
  author: shihwesley
  version: 1.0.0
---

# Chronicler

Chronicler generates `.tech.md` files that live alongside your source code in a `.chronicler/` directory. Each doc captures a file's purpose, key components, dependencies, and architectural context in structured frontmatter + markdown. A merkle tree tracks which source files have changed, so you always know which docs are fresh and which need updating.

## Subcommands

### `/chronicler:init`

First-time project setup. Detects the project language, generates `chronicler.yaml`, builds a merkle tree, then generates `.tech.md` files for every tracked source file. Also builds `.chronicler/INDEX.md` with grouped component tables.

```
/chronicler:init
```

After init, hooks run automatically:
- **SessionStart** prints a freshness summary
- **PostToolUse (Write/Edit)** marks edited files as stale candidates
- **PreToolUse (Read)** warns when reading a `.tech.md` backed by stale source

### `/chronicler:status`

Shows a freshness report: how many files are fresh, stale, uncovered (source with no docs), or orphaned (docs with no source).

```
/chronicler:status
```

### `/chronicler:regenerate`

Regenerates `.tech.md` files whose source has changed since the last scan. Pass a specific file path to regenerate just that one, or run without arguments to regenerate all stale files. Rebuilds INDEX.md afterward.

```
/chronicler:regenerate
/chronicler:regenerate src/api/auth.ts
```

### `/chronicler:configure`

Updates `chronicler.yaml` settings using dot-notation key=value pairs.

```
/chronicler:configure llm.provider=openai llm.model=gpt-4o
```

## Example Workflow

```
# 1. Set up chronicler in a new project
/chronicler:init

# 2. Work on code for a while...
#    (hooks track which files you edit)

# 3. Check what's gone stale
/chronicler:status

# 4. Regenerate stale docs
/chronicler:regenerate

# 5. Tweak settings if needed
/chronicler:configure scan.exclude_patterns=["*.test.ts","dist/**"]
```

## Common Issues

- **"No chronicler.yaml found"** — Run `/chronicler:init` first. The config file is required for all other subcommands.
- **Orphaned docs after file renames** — `/chronicler:status` will flag these. Delete the old `.tech.md` and run `/chronicler:regenerate` for the renamed file.
- **Large repos take a while on init** — The init command processes files in batches of 5-10. For very large codebases, consider configuring `scan.exclude_patterns` to skip generated or vendored code before running init.
- **Stale warnings on read** — This is the PreToolUse hook working as intended. Run `/chronicler:regenerate <file>` to clear it.

## Sub-Operations

This skill dispatches to the following command files:

- `commands/init.md` — project setup and initial doc generation
- `commands/status.md` — freshness reporting
- `commands/regenerate.md` — stale doc regeneration
- `commands/configure.md` — config updates
