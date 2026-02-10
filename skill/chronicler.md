---
name: chronicler
version: "1.0.0"
description: Ambient documentation for vibe coders. Init once, never think about docs again.
user-invocable: true
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
---

# Chronicler — Ambient Documentation

Auto-generates and maintains `.tech.md` files alongside your code. Run `/chronicler init` in any project to get started.

## Subcommands

### `/chronicler init`

First-time setup for a project. Detects project type, generates config, crawls the codebase, and installs Claude Code hooks so documentation stays fresh automatically.

**Run:**
```bash
python3 -m chronicler_lite.skill.init
```

This will:
1. Auto-detect project language/framework (package.json, pyproject.toml, Package.swift, etc.)
2. Generate `chronicler.yaml` with sensible defaults
3. Build a merkle tree of the project for drift tracking
4. Install hooks into `.claude/settings.json` for ambient updates

After init, documentation updates happen in the background via hooks — no manual steps needed.

### `/chronicler status`

Show a freshness report: how many files are fresh, stale, uncovered (no docs), or orphaned (docs with no source).

**Run:**
```bash
python3 -m chronicler_lite.skill.status
```

Output is a formatted table. Use this to check whether any docs need attention.

### `/chronicler regenerate [path]`

Force-regenerate documentation. Without arguments, processes all stale files. With a path argument, targets just that file.

**Run (all stale):**
```bash
python3 -m chronicler_lite.skill.regenerate
```

**Run (specific file):**
```bash
python3 -m chronicler_lite.skill.regenerate src/components/Button.tsx
```

Note: Without a configured LLM drafter, this reports which files are stale but doesn't rewrite them. Full regeneration requires a working LLM provider in `chronicler.yaml`.

### `/chronicler configure`

Update `chronicler.yaml` settings from the command line.

**Run:**
```bash
python3 -m chronicler_lite.skill.configure llm.provider=openai llm.model=gpt-4o
```

Pass `key=value` pairs using dot notation for nested keys. Prints the updated config after changes.
