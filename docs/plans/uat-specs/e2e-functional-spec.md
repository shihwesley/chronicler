---
name: e2e-functional-spec
phase: 2
sprint: 1
parent: root-spec
depends_on: [install-uat-spec]
status: draft
created: 2026-02-10
---

# E2E Functional UAT Spec

## Requirements
- Chronicler Lite runs successfully on real projects
- Codebase map (CODEBASE_MAP.md) generated correctly
- tech.md generated from codebase map
- Multiple target repos tested for variety
- Full pipeline: map -> navigate -> draft -> output

## Acceptance Criteria
- [ ] Run on agent-reverse — codebase map + tech.md produced
- [ ] Run on orbit — codebase map + tech.md produced
- [ ] Run on chronicler (self) — codebase map + tech.md produced
- [ ] Run on identity-report — codebase map + tech.md produced (if exists)
- [ ] Codebase map accurately reflects project structure
- [ ] tech.md contains correct project name, architecture, files
- [ ] No crashes or unhandled exceptions during any run
- [ ] Output files written to expected locations
- [ ] Runs complete within reasonable time (< 5 min per project)

## Technical Approach
Run Chronicler Lite against 3-4 real projects in ~/Source. For each:
1. Clear any prior chronicler output
2. Run the tool
3. Verify codebase map generated
4. Verify tech.md generated
5. Spot-check content accuracy
6. Log timing and any errors

## Test Targets
| Project | Path | Approx Size | Notes |
|---------|------|-------------|-------|
| agent-reverse | ~/Source/agent-reverse | medium | Node.js |
| orbit | ~/Source/orbit | small-medium | mixed |
| chronicler | ~/Source/Chronicler | large | Python monorepo, self-test |
| identity-report | ~/Source/identity-report | small | if available |

## Files
- Chronicler entry point / CLI
- Output: CODEBASE_MAP.md, .tech.md per target

## Tasks
1. Run Chronicler on agent-reverse, capture output + timing
2. Run Chronicler on orbit, capture output + timing
3. Run Chronicler on self (chronicler), capture output + timing
4. Run Chronicler on identity-report if available
5. Verify codebase map accuracy per project
6. Verify tech.md basic structure per project

## Dependencies
- Upstream: install-uat-spec (working installation)
- Downstream: output-quality-spec, token-efficiency-spec
