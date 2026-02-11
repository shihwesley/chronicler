---
name: status
description: Show documentation freshness report — fresh, stale, uncovered, orphaned
allowed-tools: ["Bash"]
---

# Chronicler Status

Show a freshness report for the current project's documentation.

Run the status module:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.status
```

Output is a formatted table showing how many files are fresh, stale, uncovered (source with no docs), or orphaned (docs with no source). Use this to check whether any docs need attention.
