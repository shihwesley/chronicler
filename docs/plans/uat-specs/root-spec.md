---
name: root-spec
phase: 1
sprint: 1
parent: null
depends_on: []
status: draft
created: 2026-02-10
---

# Root Spec: UAT Environment & Orchestration

## Requirements
- Clean Python 3.11+ environment for testing
- Access to real Source projects for E2E targets
- Anthropic API key available for LLM calls
- Git repos in testable state (no uncommitted WIP blocking)

## Acceptance Criteria
- [ ] Python venv created and activated
- [ ] All test target repos identified and accessible
- [ ] API keys verified (Anthropic at minimum)
- [ ] Test runner / harness ready (pytest + manual scripts)
- [ ] Baseline metrics captured (repo sizes, file counts)

## Technical Approach
Create a dedicated venv, verify API access, enumerate test targets in ~/Source, capture baseline measurements for later comparison.

## Files
- packages/chronicler-core/pyproject.toml
- packages/chronicler-lite/pyproject.toml
- Any existing test infrastructure

## Tasks
1. Create clean Python 3.11+ venv for UAT
2. Verify API key access (dry-run Anthropic call)
3. Enumerate and validate test target repos
4. Capture baseline metrics (file counts, repo sizes)

## Dependencies
- Upstream: none (root)
- Downstream: packaging-uat-spec needs clean environment
