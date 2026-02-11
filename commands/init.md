---
name: init
description: First-time project setup — detects language, generates config, builds merkle tree, generates initial docs
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
---

# Chronicler Init

Run first-time setup for the current project.

## Step 1: Initialize project structure

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.init
```

This will:
1. Auto-detect the project language and framework
2. Generate `chronicler.yaml` with sensible defaults
3. Build a merkle tree of the project for drift tracking

## Step 2: Generate initial .tech.md files

After init, run the regenerate command to see which files need documentation:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.regenerate
```

If no LLM drafter is configured yet, this reports uncovered files but won't write docs. To enable auto-generation, edit `chronicler.yaml` and set an LLM provider:

```yaml
llm:
  provider: anthropic  # or openai, google, ollama
  model: claude-haiku-4-5-20251001
```

Then re-run regenerate to generate `.tech.md` files for all source files.

## After init

Hooks run in the background via the plugin — no manual setup needed:
- **SessionStart**: prints a freshness summary
- **PostToolUse (Write/Edit)**: marks edited files as stale candidates
- **PreToolUse (Read)**: warns when reading a `.tech.md` backed by stale source
