#!/bin/bash
# Chronicler pre-read hook — warns if a .tech.md file is backed by stale source.
# Called by Claude Code before Read tool use on .tech.md files.
python3 -m chronicler_lite.hooks.pre_read_techmd "$TOOL_INPUT_FILE" 2>/dev/null || true
exit 0
