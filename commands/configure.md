---
name: configure
description: Update chronicler.yaml settings with key=value pairs
allowed-tools: ["Bash"]
---

# Chronicler Configure

Update `chronicler.yaml` settings from the command line. Pass key=value pairs using dot notation for nested keys.

Run the configure module:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.configure $ARGUMENTS
```

Example: `/chronicler:configure llm.provider=openai llm.model=gpt-4o`

Prints the updated config after changes.
