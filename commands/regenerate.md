---
name: regenerate
description: Force-regenerate documentation for stale files, or a specific path
allowed-tools: ["Bash"]
---

# Chronicler Regenerate

Force-regenerate documentation. Without arguments, processes all stale files. With a path argument, targets just that file.

Run the regenerate module:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.regenerate $ARGUMENTS
```

Without a configured LLM drafter, this reports which files are stale but doesn't rewrite them. Full regeneration requires a working LLM provider in `chronicler.yaml`.
