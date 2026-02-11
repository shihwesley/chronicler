# Findings & Decisions

## Goal
Full User Acceptance Test of Chronicler Lite — from packaging through installation, real-project E2E runs, output quality, and efficiency benchmarking.

## Priority
Quality — thorough testing, edge cases, real-world scenarios before publish.

## Approach
Sequential pipeline: packaging -> install -> E2E -> quality/efficiency. Security and error paths run alongside once their deps are met.

## Requirements (Validated)
1. Pre-install prep & packaging (build core + lite, verify deps)
2. Installation testing — pip local, Claude Code CLI hooks, VS Code extension
3. E2E functional test on real projects (agent-reverse, orbit, identity-report, chronicler)
4. Output quality — tech.md technical depth vs bloat audit
5. Staleness detection and freshness re-generation
6. Token efficiency benchmarking — API usage per run, cost estimates
7. Security validation — existing tests + manual edge cases
8. Error path testing — missing deps, bad configs, graceful failures

## Project Structure Notes
- Monorepo: packages/chronicler-core (Python, hatchling), packages/chronicler-lite (Python, hatchling)
- chronicler-core deps: pygithub, anthropic, openai, google-generativeai, httpx, pydantic>=2.0, pyyaml, markitdown
- chronicler-lite deps: chronicler-core, memvid-sdk>=2.0.0, pyyaml
- VS Code extension: packages/chronicler-vscode (Node.js)
- Claude Code hooks: packages/chronicler-lite/hooks/

## Research Findings
- Python 3.14.2 available (/opt/homebrew/bin/python3), well above 3.11 minimum
- API keys (ANTHROPIC, OPENAI, GOOGLE) not set in this shell — needed for Sprint 3 E2E
- Venv created at .worktrees/uat-sprint1-packaging/.venv

### Test Target Baselines
| Project | Files | Git | Notes |
|---------|-------|-----|-------|
| agent-reverse | 233 | yes | Node.js, medium |
| Orbit | 125 | yes | small |
| IdentityReport | 1184 | yes | large, good stress test |
| Chronicler | 244 | yes | Python monorepo, self-test |

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Test on real Source projects | Realistic E2E validation, not synthetic repos |
| Measure tokens via Anthropic API usage headers | Direct measurement, no estimation needed |
| Separate output quality from functional pass | Functional = "it runs", quality = "output is good" |
| Use Orbit sandbox/microVM for install testing | Isolated environment, no host pollution, reproducible |
| Worktrees for parallel spec execution | Independent filesystem copies per sprint |

## Worktree Map
| Sprint | Branch | Worktree Path | Specs | Status |
|--------|--------|---------------|-------|--------|
| 1 | uat/sprint1-packaging | .worktrees/uat-sprint1-packaging | root-spec, packaging-uat-spec | ready |
| 2 | uat/sprint2-install | .worktrees/uat-sprint2-install | install-uat-spec, security-uat-spec | ready |
| 3 | uat/sprint3-e2e | .worktrees/uat-sprint3-e2e | e2e-functional-spec, error-paths-spec | ready |
| 4 | uat/sprint4-quality | .worktrees/uat-sprint4-quality | output-quality-spec, token-efficiency-spec | ready |

## Orbit Sandbox Notes
- Install testing (sprint 2) should use Orbit sandbox/microVM for clean isolation
- Security probes (sprint 2) run in sandbox to avoid host contamination
- E2E runs (sprint 3) can use host or sandbox depending on test target access

## Install Issues Log
<!-- Track every install issue encountered and how it was fixed -->
1. **google.generativeai deprecation warning** — `gemini.py:7` imports deprecated `google.generativeai` package. FutureWarning says to migrate to `google.genai`. Not a blocker but should be addressed post-publish.
2. **chronicler_lite missing `__version__`** — `chronicler_core` exposes `__version__ = "0.1.0"` but `chronicler_lite.__init__.py` does not. Minor packaging hygiene.
3. **pip backtracking on google deps** — pip tried ~20 versions of `googleapis-common-protos` before settling. The `google-generativeai` -> `google-ai-generativelanguage` -> `grpcio-status` chain is heavy. Install took noticeably longer because of this.
4. **pip 25.3 -> 26.0.1 upgrade notice** — not a problem, just noise.
5. **No hook install script or documentation** — hooks exist at `packages/chronicler-lite/hooks/chronicler/` but there's no install script, no README, and no CLI command to register them in `~/.claude/settings.json`. Users would need to: (a) copy hook scripts somewhere persistent, (b) manually add entries to settings.json with correct event matchers. FIX NEEDED: Add a `chronicler install-hooks` CLI command or document the manual process.
6. **Hook execution requires pip package** — the shell hooks call `python3 -m chronicler_lite.hooks.*`, so the pip package must already be installed for hooks to work. Install order matters: pip install first, then hook registration. This should be documented.
7. **Wheel install works clean** — fresh venv + wheel install works. All deps resolve from the pre-built wheel, no build tooling needed on user side.
8. **VS Code extension: @types/node conflict** — `vitest@^4.0.18` requires `@types/node@^20.0.0 || ^22.0.0 || >=24.0.0` but package.json specifies `@types/node@^18.0.0`. `npm install` fails with ERESOLVE. FIX: bump `@types/node` to `^20.0.0` (minimum compat with vitest 4.x).
9. **VS Code CLI (`code`) not on PATH** — can't test `code --install-extension` without it. This is environment-specific, not a Chronicler issue.
10. **VSIX build warnings** — missing `repository` field in package.json, no LICENSE file, no `.vscodeignore`. Functional but won't pass marketplace review. FIX: add repository URL, LICENSE.md, and .vscodeignore before publish.
11. **VSIX includes source AND compiled** — both `src/` and `out/` are in the .vsix (99KB total). Should add `.vscodeignore` to exclude `src/`, `tsconfig.json`, `vitest.config.ts` from the bundle. Would cut size ~40%.
12. **@types/node bump from ^18 to ^20** — required to fix vitest 4.x peer dep conflict. Applied and verified. This change should be committed.
13. **Missing test deps in pyproject.toml** — `watchdog` and `pytest-asyncio` not listed as test dependencies. Tests fail to collect without them. FIX: add `[project.optional-dependencies] test = ["pytest", "pytest-asyncio", "watchdog"]` to both pyproject.toml files.
14. **Security audit clean** — no `yaml.load()` usage (all safe), no API key logging, all 16 security tests pass, all 20 type invariant tests pass, env var handling tested.

15. **MerkleTree indexes .worktrees/** — MerkleTree.build() doesn't respect .gitignore. On Chronicler self-test, 1197/1235 indexed files were from `.worktrees/`, only 38 actual source. This would cause huge token waste in tech.md generation. FIX NEEDED: respect .gitignore or at minimum exclude `.worktrees/`, `.venv/`, `node_modules/`.
16. **Orbit merkle count inflated by node_modules?** — Orbit showed 370 files indexed but baseline was 125. May also be indexing node_modules. Need to verify.

## Error Path Results (Sprint 3)
| Scenario | Result | Severity |
|----------|--------|----------|
| Non-existent dir | Raw FileNotFoundError traceback | HIGH — needs try/catch |
| Empty temp dir | Works fine, 1 file indexed | OK |
| Status on non-init dir (/tmp) | Indexes 9312 files, no warning | MEDIUM — should check .chronicler/ |
| Malformed YAML config | Skips (exists check), continues | LOW — fails later when read |
| Read-only dir | Raw PermissionError traceback | HIGH — needs try/catch |
| Regenerate without drafter | Clean message, exits 0 | OK |
| Session-start hook | One-line summary, exits 0 | OK |

## E2E Init Results (Sprint 3)
| Project | Detected As | Files Indexed | Merkle Size | Notes |
|---------|-------------|---------------|-------------|-------|
| agent-reverse | node | 150 | 52KB | clean, accurate |
| Orbit | node | 370 | ? | possibly includes node_modules |
| Chronicler | python | 1235 (38 real) | ? | 97% from .worktrees/ — BUG |

## Output Quality Assessment (Sprint 4)

### Prompt Design Quality
| Aspect | Assessment | Notes |
|--------|-----------|-------|
| Anti-bloat | GOOD | System prompt: "strictly technical, no marketing, ~1000 words" |
| Truncation | GOOD | max_readme=2000 chars, max_file_tree=50 entries, max_dockerfile=1000 |
| Honesty | GOOD | verification_status defaults to "ai_draft", uses "unknown" for unknowns |
| Structure | GOOD | YAML frontmatter + architectural intent + Mermaid connectivity graph |
| Output validation | MISSING | No programmatic word count or bloat check on LLM output |
| Section variety | MODERATE | Only 2 content sections (intent + graph). No API surface, testing, or deployment info |

### Bloat Risk Analysis
- Prompt caps at ~1000 words but nothing enforces this on the response
- Without post-generation validation, a verbose LLM could produce 3000+ words
- Recommendation: add a post-draft word count check with warning if >1500 words

### Staleness Detection Design
| Check | Assessment | Notes |
|-------|-----------|-------|
| Hash-based comparison | GOOD | Merkle tree stores source_hash per file |
| Status command | GOOD | Shows fresh/stale/uncovered/orphaned counts |
| Regenerate command | GOOD | Identifies stale, skips gracefully without drafter |
| Session-start hook | GOOD | One-line staleness summary |
| Incremental check | NOT TESTED | Can't verify without LLM-generated docs to compare against |

## Token Efficiency Analysis (Sprint 4)

### Per-Project Token Usage (medium repo, ~150 files)
| Component | Chars | Est. Tokens | Notes |
|-----------|-------|-------------|-------|
| System prompt | 2,128 | ~530 | Fixed cost, identical for all projects |
| User prompt | 3,131 | ~780 | Varies by repo size, README length |
| **Total input** | 5,259 | **~1,314** | |
| **Output** (est) | - | **~1,300** | ~1000 words tech.md |

### Cost Per Project (single generation)
| Model | Input Cost | Output Cost | Total |
|-------|-----------|-------------|-------|
| Claude Haiku 4.5 | $0.001 | $0.005 | **$0.006** |
| GPT-4o | $0.003 | $0.013 | **$0.016** |
| Claude Sonnet 4.5 | $0.004 | $0.020 | **$0.023** |
| Claude Opus 4.6 | $0.020 | $0.098 | **$0.117** |

### Batch Cost Estimates (10 projects)
| Model | Without Caching | With Prompt Cache | Savings |
|-------|----------------|-------------------|---------|
| Haiku | $0.06 | ~$0.04 | ~33% |
| Sonnet | $0.23 | ~$0.15 | ~35% |

### Optimization Opportunities
1. **Prompt caching** — System prompt (530 tokens) is identical across all runs. Anthropic's prompt caching would save ~40% input tokens on batch runs. Not implemented yet.
2. **Haiku default** — For initial draft generation, Haiku produces adequate quality at 1/4 the cost of Sonnet. Could default to Haiku with Sonnet as quality tier.
3. **Incremental regeneration** — Currently re-drafts the entire tech.md on stale detection. Could diff only changed sections and re-draft those, saving 50-80% tokens on updates.
4. **File tree pruning** — TruncationConfig caps at 50 files, but doesn't prioritize. Could rank by importance (src/ over node_modules/) to give better context in fewer tokens.
5. **Streaming not needed for batch** — Streaming has slightly higher overhead vs one-shot. For batch/CI runs, one-shot would be ~5% cheaper.

### Token Usage Already Tracked
Good: `LLMResponse` includes `TokenUsage(input_tokens, output_tokens)`. The infrastructure for logging already exists. Missing: no aggregation layer to sum across a session, no cost calculator.

### Cannot Test (requires API key)
- Actual tech.md generation quality (output content)
- Diff between regenerated and original tech.md
- Token usage per generation (Sprint 4 / token-efficiency spec)

## Security Test Results (Sprint 2)
| Suite | Passed | Failed | Notes |
|-------|--------|--------|-------|
| test_security.py | 16/16 | 0 | path traversal, symlink, env var, URL validation |
| test_type_invariants.py | 20/20 | 0 | component ID, numeric bounds, mutable defaults |
| test_config.py | 26/26 | 0 | config loading, expansion, validation |
| test_error_handling.py | 19/19 | 0 | after installing pytest-asyncio + watchdog |
| YAML audit | N/A | N/A | no yaml.load() — all safe |
| API key audit | N/A | N/A | no logging/printing of keys |

## Packaging Results (Sprint 1)
| Check | Result |
|-------|--------|
| pip install -e chronicler-core | PASS |
| pip install -e chronicler-lite | PASS |
| import chronicler_core | PASS (v0.1.0) |
| import chronicler_lite | PASS (no __version__) |
| pip check | PASS (no broken requirements) |
| build core sdist+wheel | PASS (59k whl, 37k tar.gz) |
| build lite sdist+wheel | PASS (14k whl, 9.1k tar.gz) |

## Visual/Browser Findings
-
