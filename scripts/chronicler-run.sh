#!/bin/bash
# Shared Python runner for Chronicler plugin commands.
# Resolves the right interpreter, then exec's the requested module.
#
# Usage: chronicler-run.sh <dotted.module> [args...]
# Example: chronicler-run.sh skill.status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/chronicler-resolve-python.sh"

MODULE="$1"; shift

# Bootstrap venv if needed (commands are interactive, so show progress)
bootstrap_venv
resolve_python

exec "$PYTHON" -m "chronicler_lite.${MODULE}" "$@"
