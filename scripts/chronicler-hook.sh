#!/bin/bash
# Unified hook entry point for Chronicler plugin.
# Dispatches to the right Python hook module based on the first argument.
#
# Usage: chronicler-hook.sh <hook_name>
# Hooks never block Claude Code — all paths guarded with || true.

HOOK="$1"

# Resolve Python interpreter (same chain as chronicler-run.sh)
if [ -n "${CHRONICLER_PYTHON:-}" ]; then
  PYTHON="$CHRONICLER_PYTHON"
elif [ -x "${CLAUDE_PLUGIN_ROOT:-.}/.venv/bin/python3" ]; then
  PYTHON="${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3"
else
  PYTHON="python3"
fi

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
