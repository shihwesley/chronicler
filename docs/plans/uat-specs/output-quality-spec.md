---
name: output-quality-spec
phase: 2
sprint: 2
parent: root-spec
depends_on: [e2e-functional-spec]
status: draft
created: 2026-02-10
---

# Output Quality UAT Spec

## Requirements
- tech.md is technically detailed, not surface-level
- tech.md is not bloated with filler or repetition
- Codebase map covers all significant files
- Staleness detection works when files change
- Freshness re-generation produces updated output

## Acceptance Criteria
- [ ] tech.md contains architecture overview with real file references
- [ ] tech.md includes dependency analysis (not just listing package.json)
- [ ] tech.md has code patterns / conventions section
- [ ] No filler paragraphs or generic boilerplate in tech.md
- [ ] Word count reasonable (target: 500-3000 words depending on project size)
- [ ] Codebase map covers >90% of source files
- [ ] Modify a source file -> staleness detected on next run
- [ ] Re-run after change -> tech.md reflects update
- [ ] Staleness check doesn't require full re-generation
- [ ] No hallucinated file paths or made-up function names

## Technical Approach
### Quality Audit
Take tech.md from E2E runs. Score against rubric:
- Technical depth: does it explain HOW, not just WHAT?
- File references: are paths real and accurate?
- Bloat check: ratio of useful content vs filler
- Completeness: major components covered?

### Staleness Test
1. Capture hash/timestamp of initial tech.md
2. Modify a source file in target project
3. Run staleness check
4. Verify it flags the changed area
5. Re-run generation
6. Diff old vs new tech.md — verify change reflected

## Files
- E2E output: tech.md files from e2e-functional-spec
- Codebase maps from E2E runs

## Tasks
1. Quality audit tech.md from agent-reverse run
2. Quality audit tech.md from chronicler self-run
3. Bloat analysis — word count, filler detection
4. Staleness detection test (modify file -> detect)
5. Freshness re-gen test (re-run -> updated output)

## Dependencies
- Upstream: e2e-functional-spec (generated output to audit)
- Downstream: none (terminal spec)
