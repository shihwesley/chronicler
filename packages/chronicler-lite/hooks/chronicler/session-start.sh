#!/bin/bash
# Chronicler session-start hook — reports doc staleness on Claude Code startup.
# Runs check_staleness against the current project and prints a summary line.
python3 -m chronicler_lite.hooks.session_start "$PWD" 2>/dev/null || true
exit 0
