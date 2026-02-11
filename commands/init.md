---
name: init
description: First-time project setup — detects language, generates config, builds merkle tree
allowed-tools: ["Bash"]
---

# Chronicler Init

Run first-time setup for the current project. This will:

1. Auto-detect the project language and framework (package.json, pyproject.toml, Package.swift, etc.)
2. Generate `chronicler.yaml` with sensible defaults
3. Build a merkle tree of the project for drift tracking
4. Register hooks for ambient documentation updates

Run the init module:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.init
```

After init completes, documentation updates happen in the background via hooks. No manual steps needed.
