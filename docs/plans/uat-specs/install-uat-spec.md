---
name: install-uat-spec
phase: 1
sprint: 2
parent: root-spec
depends_on: [packaging-uat-spec]
status: draft
created: 2026-02-10
---

# Installation UAT Spec

## Requirements
- pip install from local wheel works in fresh venv
- Claude Code CLI hook installation works
- VS Code extension installs and activates
- Post-install verification commands succeed

## Acceptance Criteria
- [ ] Fresh venv + `pip install chronicler-lite-0.1.0.whl` succeeds
- [ ] Claude Code hooks installed: `ls ~/.claude/hooks/` shows chronicler files
- [ ] Hook registration: chronicler hook fires on test event
- [ ] VS Code extension: `code --install-extension chronicler-vscode-*.vsix` succeeds
- [ ] VS Code extension activates without errors (check Extension Host log)
- [ ] Uninstall path works cleanly for all three methods
- [ ] Document every issue encountered with fix applied

## Technical Approach
Test three install paths independently. For each: fresh environment, install, verify, uninstall. Log every issue in findings.md Install Issues Log.

### Path 1: pip install (user path)
Build wheel from packaging spec, install in fresh venv, verify CLI + imports.

### Path 2: Claude Code CLI hooks
Copy hooks to ~/.claude/hooks/ (or use install script if exists). Verify hook registration and trigger.

### Path 3: VS Code extension
Build .vsix from packages/chronicler-vscode, install via `code --install-extension`, verify activation.

## Files
- packages/chronicler-lite/hooks/
- packages/chronicler-vscode/package.json
- packages/chronicler-vscode/ (build scripts)
- Any install scripts at repo root

## Tasks
1. Test pip install from wheel in fresh venv
2. Test Claude Code hook installation and trigger
3. Test VS Code extension build, install, activation
4. Test uninstall for all three paths
5. Document all issues with fixes in findings.md

## Dependencies
- Upstream: packaging-uat-spec (built artifacts)
- Downstream: e2e-functional-spec, error-paths-spec
