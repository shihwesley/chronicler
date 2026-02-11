#!/bin/bash
# Shared Python resolver for Chronicler plugin scripts.
# Sources into chronicler-run.sh and chronicler-hook.sh.
# Sets $PYTHON to the best available interpreter with chronicler_lite installed.
#
# Resolution order:
#   1. $CHRONICLER_PYTHON env var (explicit override)
#   2. $CLAUDE_PLUGIN_ROOT/.venv/bin/python3 (dev mode — repo has .venv from uv sync)
#   3. ~/.chronicler/.venv/bin/python3 (auto-bootstrapped for plugin installs)
#   4. System python3 (if user pip-installed chronicler-lite globally)

# Auto-detect CLAUDE_PLUGIN_ROOT from script location if not set.
# Scripts live in $PLUGIN_ROOT/scripts/, so parent dir is the root.
if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  CLAUDE_PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

CHRONICLER_HOME="${HOME}/.chronicler"
CHRONICLER_VENV="${CHRONICLER_HOME}/.venv"

resolve_python() {
  # 1. Explicit override
  if [ -n "${CHRONICLER_PYTHON:-}" ]; then
    PYTHON="$CHRONICLER_PYTHON"
    return
  fi

  # 2. Dev mode — local venv from uv sync
  if [ -x "${CLAUDE_PLUGIN_ROOT:-.}/.venv/bin/python3" ]; then
    PYTHON="${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3"
    return
  fi

  # 3. Bootstrapped venv — auto-created on first plugin use
  if [ -x "${CHRONICLER_VENV}/bin/python3" ]; then
    PYTHON="${CHRONICLER_VENV}/bin/python3"
    return
  fi

  # 4. System python (chronicler-lite pip-installed globally)
  PYTHON="python3"
}

# Bootstrap: create ~/.chronicler/.venv and install workspace packages
# from the plugin cache. Only runs once — subsequent calls hit step 3.
bootstrap_venv() {
  if [ -x "${CHRONICLER_VENV}/bin/python3" ]; then
    return 0
  fi

  # Need CLAUDE_PLUGIN_ROOT to find the packages
  if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    return 1
  fi

  echo "Chronicler: setting up Python environment (one-time)..."
  mkdir -p "$CHRONICLER_HOME"
  python3 -m venv "$CHRONICLER_VENV" || return 1
  "$CHRONICLER_VENV/bin/pip" install --quiet \
    "${CLAUDE_PLUGIN_ROOT}/packages/chronicler-core" \
    "${CLAUDE_PLUGIN_ROOT}/packages/chronicler-lite" || return 1
  echo "Chronicler: setup complete."
}
