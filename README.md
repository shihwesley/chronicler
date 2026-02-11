# Chronicler

Automated `.tech.md` generation for codebases. Crawl a repo, draft structured technical documentation with an LLM, and track when those docs go stale — all from the command line.

> **This is Chronicler Lite** — built for vibe coders, indie developers, and small teams who want their codebase documented without the overhead. An enterprise version with org-wide governance, CI/CD enforcement, and team-scoped access control is on the way.

**Obsidian user?** Check out [obsidian-chronicler](https://github.com/shihwesley/obsidian-chronicler) — a plugin that auto-discovers your `.chronicler/` folders, renders `agent://` links as clickable navigation, and gives you dependency graphs + health dashboards right in your vault.

## Why this exists

Most technical documentation is written once and forgotten. The author moves on, the codebase changes, and six months later a new engineer opens the doc to find a half-finished description of an architecture that no longer exists.

This happens everywhere — startups, enterprises, open source. A developer gets assigned to modify a pipeline or extend a feature. They open the tech doc. The doc has a one-paragraph overview, a diagram from two versions ago, and no information about why the system was built that way. The developer ends up reading source code for hours, reconstructing context that someone already had and didn't write down.

Chronicler tries to fix that. It generates standardized, structured Markdown documentation from your actual codebase, keeps it in sync with your source files, and formats it so both humans and AI agents can use it without guessing.

## Why Markdown

Previous approaches to technical documentation stored knowledge in Google Docs, Confluence pages, PDFs, or Word files. These formats have a shared problem: they're hard for machines to parse and easy to lose track of.

Chronicler writes `.tech.md` files — plain Markdown with YAML frontmatter. The reasons:

- **Lives with the code.** Docs sit in a `.chronicler/` directory in your repo. They go through the same PR review, branching, and history as your source files.
- **AI-native format.** LLMs read Markdown natively. No conversion step, no extraction pipeline. An AI agent can read a `.tech.md` file and know what a component does, what it depends on, and what will break if you change it.
- **RAG-ready.** The structured YAML frontmatter and consistent section format make these files easy to chunk and index. Chronicler's companion project, Mnemon, consumes this output for 3D knowledge-graph visualization and semantic search.
- **Human-readable everywhere.** Obsidian, VS Code's Markdown preview, GitHub's web view, any text editor. No proprietary viewer required.

## How it works

Chronicler has a four-stage pipeline:

```
1. Crawl     →  Connect to GitHub, clone the file tree, collect key files
2. Draft     →  Send structured context to an LLM, get back a .tech.md
3. Validate  →  Check the output against the frontmatter schema
4. Track     →  Hash source files into a merkle tree, detect drift over time
```

### Crawl

The VCS crawler connects to GitHub (Azure DevOps and GitLab planned), pulls repo metadata, the file tree, and the contents of key files (README, package manifests, config files, entry points). It also converts PDFs, DOCX, and PPTX files it finds into Markdown for inclusion.

### Draft

The drafter builds a prompt context from the crawl data — file tree, dependencies, key file contents — and sends it to an LLM. The system prompt is explicit: strictly technical, no marketing language, no fluff. If the LLM can't determine something from the repo data, it writes "unknown" instead of guessing.

The output follows a fixed structure:

- YAML frontmatter (component ID, owner team, layer, edges, security level, governance metadata)
- Architectural intent (what this does, why it exists, key responsibilities)
- Connectivity graph (Mermaid diagram of dependencies)
- Links to satellite docs (QA blueprints, audit logs, invariants)

A word-count guard flags any draft that exceeds 1,500 words. The goal is density, not volume.

### Validate

`chronicler validate` checks every `.tech.md` file in your `.chronicler/` directory against the frontmatter schema. Strict mode (the default) fails on missing required fields. You can run this in CI to block PRs that ship without valid docs.

### Track freshness with merkle trees

This is where Chronicler differs from "run the doc generator once and forget about it."

Every source file in your repo gets SHA-256 hashed and placed into a merkle tree (stored as `.chronicler/.merkle.json`). When you run `chronicler check`, it recomputes hashes and compares them against the stored tree. Files whose hashes changed but whose corresponding `.tech.md` hasn't been updated are flagged as stale.

```
chronicler check
# Shows a table of files with ok/stale status

chronicler check --ci --fail-on-stale
# Machine-readable output, exits 1 if anything is stale
# Use this in your CI pipeline

chronicler draft --stale
# Only regenerate docs for files that changed
```

The `blast-radius` command walks the edge graph in your `.tech.md` frontmatter to show you what else might need updating:

```
chronicler blast-radius --changed src/auth/handler.py --depth 2
```

## Cross-document linking

Each `.tech.md` can declare edges to other components:

```yaml
edges:
  - target: "agent://auth-service/handler.tech.md"
    relationship: "CONSUMES"
    transport: "grpc"
```

These URIs (`agent://<service>/<path>`) let you navigate between docs and let tools build dependency graphs. The Obsidian integration rewrites these into wiki-links so you can click through your docs in a vault.

## Hub-and-spoke model

A single `.tech.md` file caps at roughly 1,500 words. Anything deeper — full audit logs, QA blueprints, invariant rules, logic maps — goes into satellite docs linked from the hub:

```yaml
satellite_docs:
  audit_log: "auth-service.audit.tech.md"
  qa_blueprint: "auth-service.qa.tech.md"
  invariants: "auth-service.invariants.md"
```

This keeps the main doc scannable while still capturing full operational history.

## LLM providers

Chronicler defaults to Claude Haiku 4.5 for drafting. Haiku was chosen because documentation generation is a high-volume, structured-output task — you don't need the most expensive model to fill in a template with facts from a repo. The drafting prompt is heavily constrained, so a smaller model following strict instructions produces output comparable to a larger model with loose instructions, at a fraction of the cost.

Supported providers:

| Provider | Config value | Model example |
|----------|-------------|---------------|
| Anthropic | `anthropic` | `claude-haiku-4-5-20251001` |
| OpenAI | `openai` | `gpt-4o-mini` |
| Google | `google` | `gemini-2.0-flash` |
| Ollama | `ollama` | Any local model |

Set `provider: "auto"` to let Chronicler detect which API key is available and pick accordingly.

## Security

A few deliberate choices:

- **Env var allowlist.** The config loader supports `${VAR}` expansion in YAML, but only for a hardcoded set of variable names (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, etc.). Arbitrary env var access is blocked.
- **Path traversal prevention.** Component IDs are sanitized before becoming filenames — `..` segments are stripped, slashes are replaced, and the final path is validated against the output directory.
- **RBAC interface.** A plugin protocol for role-based access control is defined (check/grant/revoke/list). The `.tech.md` frontmatter includes `security_level` and `visibility` fields so you can scope who sees what.
- **API keys stay in env vars.** Chronicler reads keys from environment variables referenced by name in the config. The keys themselves never appear in `chronicler.yaml`.
- **Validation modes.** Strict validation (default) fails on schema violations. This can be enforced in CI to prevent malformed docs from merging.

## Installation

Chronicler is a Claude Code plugin. Install it once, and it hooks into every Claude Code session with ambient documentation tracking.

### Requirements

- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI

### Install as Claude Code plugin

Inside a Claude Code session:

```
/plugin marketplace add shihwesley/chronicler
/plugin install chronicler
```

This registers the Chronicler marketplace and installs the plugin at user scope. Hooks for SessionStart, PostToolUse (Write/Edit), and PreToolUse (Read) are registered automatically.

### Commands

```
/chronicler:init                First-time project setup
/chronicler:status              Show freshness report (fresh, stale, uncovered, orphaned)
/chronicler:regenerate          Regenerate all stale docs
/chronicler:regenerate <path>   Regenerate docs for a specific file
/chronicler:configure <k=v>     Update chronicler.yaml (dot notation: llm.provider=openai)
```

### Configure

The generated `chronicler.yaml` has commented defaults for every option: LLM provider, VCS provider, output directory, monorepo detection, document conversion, merkle settings, and Obsidian sync.

Config resolution order: CLI flag (`--config`) > `./chronicler.yaml` > `~/.chronicler/config.yaml` > built-in defaults.

### Update

Inside a Claude Code session:

```
/plugin marketplace update shihwesley-chronicler
/plugin update chronicler
```

Restart Claude Code after updating for changes to take effect.

## Integrations

### Obsidian

The [obsidian-chronicler](https://github.com/shihwesley/obsidian-chronicler) plugin gives you a full browsing experience inside Obsidian — auto-discovers `.chronicler/` folders across your vault, renders `agent://` URIs as clickable links, and provides dependency explorer + health dashboard views. Install it via [BRAT](https://github.com/TfTHacker/obsidian42-brat) with `shihwesley/obsidian-chronicler`.

On the CLI side, `chronicler obsidian map` generates thin `_map.md` files with `[[wikilinks]]` so Obsidian's graph view draws connections between your components — no content duplication needed.

`chronicler obsidian export` syncs `.tech.md` files into a vault with full transform pipeline (link rewriting, frontmatter flattening, Dataview fields). Watch mode (`chronicler obsidian sync --watch`) monitors changes automatically.

### VS Code

A VS Code extension (`chronicler-vscode`) ships as a `.vsix` package with an interactive force-directed graph view of your documented components.

## CLI reference

```
chronicler crawl <repo>              Crawl a repository
chronicler draft <repo>              Generate .tech.md
chronicler draft --stale <path>      Regenerate only stale docs
chronicler validate [path]           Validate .tech.md schema
chronicler check [path]              Check source/doc drift
chronicler blast-radius --changed <file>   Show downstream impact
chronicler search <query>            Search the .mv2 knowledge base
chronicler deps <component>          Show dependency graph
chronicler rebuild                   Rebuild .mv2 index
chronicler config init               Create default config
chronicler config show               Print resolved config
chronicler obsidian export           Export to Obsidian vault
chronicler obsidian sync             Watch or REST sync
chronicler obsidian map              Generate _map.md with [[wikilinks]]
chronicler queue status              Show job queue stats
chronicler queue run                 Process pending jobs
```

## License

MIT
