#!/bin/bash
# Chronicler post-write hook — records written file paths as stale candidates.
# Called by Claude Code after Write/Edit tool use. TOOL_INPUT_FILE points to
# a temp JSON with the tool's input parameters.
python3 -m chronicler_lite.hooks.post_write "$TOOL_INPUT_FILE" 2>/dev/null || true
exit 0
