---
name: token-efficiency-spec
phase: 2
sprint: 2
parent: root-spec
depends_on: [e2e-functional-spec]
status: draft
created: 2026-02-10
---

# Token Efficiency UAT Spec

## Requirements
- Measure Claude API token usage per Chronicler run
- Identify which steps consume most tokens
- Calculate approximate cost per project
- Flag optimization opportunities
- Compare token usage across different project sizes

## Acceptance Criteria
- [ ] Token usage logged per API call (input + output tokens)
- [ ] Total tokens per run captured for each test project
- [ ] Breakdown by step: map generation vs tech.md drafting vs other
- [ ] Cost estimate per run (using current Anthropic pricing)
- [ ] Comparison table: project size vs token usage
- [ ] At least 2 optimization opportunities identified
- [ ] Recommendations documented for post-publish improvement

## Technical Approach
### Measurement
- Intercept/log Anthropic API response headers (usage field)
- If Chronicler already tracks this: use built-in metrics
- If not: add lightweight logging wrapper for this test
- Capture: input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens per call

### Analysis
- Sum totals per run
- Break down by pipeline stage
- Compute $/run using Anthropic pricing
- Plot: project file count vs total tokens
- Identify: redundant calls, oversized prompts, cacheable content

### Optimization Identification
Look for:
- Repeated context in multiple calls (could use caching)
- Full file contents when summaries would suffice
- Sequential calls that could be batched
- Prompts with boilerplate that could be trimmed

## Files
- LLM adapter code (where API calls happen)
- Any existing metrics/logging infrastructure

## Tasks
1. Add token usage logging (if not already present)
2. Run Chronicler on small project, capture token metrics
3. Run Chronicler on large project, capture token metrics
4. Build comparison table (size vs tokens vs cost)
5. Identify and document optimization opportunities

## Dependencies
- Upstream: e2e-functional-spec (runs to measure)
- Downstream: none (terminal spec)
