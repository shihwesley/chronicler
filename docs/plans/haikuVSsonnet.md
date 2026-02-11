# LLM Model Selection: Haiku vs Sonnet vs Opus

**Decision:** Haiku (claude-haiku-4-5-20251001)
**Date:** 2026-02-10
**Context:** Default model for `.tech.md` generation in Chronicler's AI Drafter

## Why This Matters Less Than You'd Think

Most of the `.tech.md` output is deterministic — no LLM involved:

| Component | LLM? | What it does |
|-----------|------|-------------|
| FrontmatterGenerator | No | Layer inference from dirs, CODEOWNERS parsing |
| generate_connectivity_graph | No | Import/manifest parsing to Mermaid diagram |
| ContextBuilder | No | Assembles repo metadata into prompt context |
| draft_architectural_intent | **Yes** | Prose summary of architecture and patterns |

Only `draft_architectural_intent` hits the LLM. The system prompt in `drafter/prompts.py` constrains output with strict schema rules and anti-examples, which narrows the quality gap between models.

## Scenario Comparison

### Standard repos (Express API, Rails app, FastAPI service)

Haiku handles these fine. The system prompt tells it exactly what to extract — stack, dependencies, entry points, layer classification. Template-following is Haiku's strength. Sonnet produces marginally better word choices. Opus adds nothing meaningful.

### Complex monorepos (microservices, shared libs, cross-package deps)

Haiku occasionally misses subtle cross-package dependencies or shared-lib patterns that aren't explicit in imports. Sonnet catches most of these. Opus reads between the lines slightly better but not enough to justify 5x the cost over Sonnet.

### Novel architectures (custom frameworks, unusual patterns)

This is where model quality shows. A repo with a hand-rolled actor system or an unusual plugin architecture will get a generic "modular application" description from Haiku. Sonnet names the pattern. Opus infers intent from indirect evidence (test structure, config shape, naming conventions).

### Vibe-coded repos (no README, inconsistent structure, mixed patterns)

Honestly, any model struggles here. The input quality caps the output quality. Haiku's structured extraction is about as useful as Sonnet's deeper reasoning when the source material is chaotic. Garbage in, slightly-better-worded garbage out.

### Enterprise codebases (strict conventions, extensive docs)

Haiku actually performs well here — the repo itself provides so much structure that the LLM's job is mostly transcription. The CODEOWNERS file, CI configs, and directory naming do the heavy lifting. All three models produce nearly identical output.

## Cost at Scale

Per-repo estimate (~4K input tokens, ~2K output tokens):

| Model | Per Repo | 50 Repos | 500 Repos |
|-------|----------|----------|-----------|
| Haiku | ~$0.003 | $0.15 | $1.50 |
| Sonnet | ~$0.04 | $2.00 | $20 |
| Opus | ~$0.19 | $9.50 | $95 |

Haiku is 13x cheaper than Sonnet, 63x cheaper than Opus.

## Why Haiku Wins for Chronicler

1. **Prompt design compensates for model quality.** The system prompt includes anti-examples and strict YAML schema. This turns a creative writing task (where Opus shines) into structured extraction (where Haiku is nearly as good).

2. **Word count validation catches failures.** The drafter warns when architectural intent exceeds 1500 words — but the inverse signal matters too. A suspiciously short or generic intent section flags repos where Haiku phoned it in. Those can be re-run with Sonnet selectively.

3. **Batch economics matter.** Chronicler targets 500+ repos. At $1.50 vs $20 vs $95, Haiku is the only model where you don't think twice about re-running the full corpus after a prompt tweak.

4. **Lite users won't notice.** Chronicler Lite targets individual developers and small teams. For their typical repo — one service, one language, maybe a Dockerfile — Haiku produces output indistinguishable from Sonnet.

## Escape Hatch

The `chronicler.yaml` config accepts any model string:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929  # override per-project
```

Power users who want better architectural intent on specific repos can override the default without changing the global setting. A future `--quality high` flag could automate this — run Haiku first, check intent word count and specificity, re-run with Sonnet if below threshold.

## Related

- Default model set in `config/models.py` (LLMSettings.model)
- Auto-detect fallback in `llm/auto_detect.py`
- System prompt constraints in `drafter/prompts.py`
- Word count validation in `drafter/drafter.py:51-56`
