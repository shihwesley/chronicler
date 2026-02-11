---
name: packaging-uat-spec
phase: 1
sprint: 1
parent: root-spec
depends_on: [root-spec]
status: draft
created: 2026-02-10
---

# Packaging UAT Spec

## Requirements
- chronicler-core builds and installs from source
- chronicler-lite builds and installs from source
- All transitive deps resolve without conflicts
- Package metadata correct (name, version, entry points)
- No missing modules at import time

## Acceptance Criteria
- [ ] `pip install -e packages/chronicler-core` succeeds
- [ ] `pip install -e packages/chronicler-lite` succeeds
- [ ] `python -c "import chronicler_core"` succeeds
- [ ] `python -c "import chronicler_lite"` succeeds
- [ ] All entry points / CLI commands registered and callable
- [ ] No dependency version conflicts in pip check
- [ ] `pip check` reports no broken requirements
- [ ] Build sdist and wheel for both packages without errors

## Technical Approach
Install in editable mode first (developer path), then test wheel build (user path). Log every warning and error. Verify import chains resolve.

## Files
- packages/chronicler-core/pyproject.toml
- packages/chronicler-lite/pyproject.toml
- packages/chronicler-core/src/chronicler_core/__init__.py
- packages/chronicler-lite/src/chronicler_lite/__init__.py

## Tasks
1. pip install -e chronicler-core, capture full output
2. pip install -e chronicler-lite, capture full output
3. Run import smoke tests for both packages
4. Run `pip check` for dependency conflicts
5. Build sdist + wheel for both, verify artifacts

## Dependencies
- Upstream: root-spec (clean venv)
- Downstream: install-uat-spec, security-uat-spec

## Install Issues Log
<!-- Every issue encountered during packaging goes here -->
