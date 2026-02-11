#!/bin/bash
# Shared Python runner for Chronicler plugin commands.
# Resolves the right interpreter, then exec's the requested module.
#
# Usage: chronicler-run.sh <dotted.module> [args...]
# Example: chronicler-run.sh skill.status

set -euo pipefail

MODULE="$1"; shift

# 1. Explicit override
if [ -n "${CHRONICLER_PYTHON:-}" ]; then
  PYTHON="$CHRONICLER_PYTHON"
# 2. Dev mode — repo-local venv from `uv sync`
elif [ -x "${CLAUDE_PLUGIN_ROOT:-.}/.venv/bin/python3" ]; then
  PYTHON="${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3"
# 3. System python (pip-installed globally)
else
  PYTHON="python3"
fi

exec "$PYTHON" -m "chronicler_lite.${MODULE}" "$@"
