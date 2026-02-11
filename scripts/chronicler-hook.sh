#!/bin/bash
# Unified hook entry point for Chronicler plugin.
# Dispatches to the right Python hook module based on the first argument.
#
# Usage: chronicler-hook.sh <hook_name>
# Hooks never block Claude Code — all paths guarded with || true.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/chronicler-resolve-python.sh"

HOOK="$1"

# Bootstrap on first hook fire (silent on failure — hooks don't block)
bootstrap_venv 2>/dev/null || true
resolve_python

case "$HOOK" in
  session_start)
    "$PYTHON" -m chronicler_lite.hooks.session_start "$PWD" 2>/dev/null || true
    ;;
  post_write)
    "$PYTHON" -m chronicler_lite.hooks.post_write "$TOOL_INPUT_FILE" 2>/dev/null || true
    ;;
  pre_read_techmd)
    "$PYTHON" -m chronicler_lite.hooks.pre_read_techmd "$TOOL_INPUT_FILE" 2>/dev/null || true
    ;;
  *)
    # Unknown hook — silently ignore
    ;;
esac

exit 0
