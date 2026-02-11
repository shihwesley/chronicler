# Chronicler AI Ledger

Automated `.tech.md` generation and browsing for VS Code. Crawl a repo, draft structured technical documentation with an LLM, and track when those docs go stale — all from your editor.

## Features

- **Dependency graph** — interactive force-directed graph of your documented components
- **Clickable links** — `agent://` URIs and `[[wiki-links]]` resolve to the right `.tech.md` file
- **Hover preview** — see a component's purpose and dependencies without leaving your current file
- **Broken link diagnostics** — red squiggles on references that point to missing docs
- **Backlinks panel** — see which components reference the one you're editing
- **Tags panel** — browse components by layer, team, or security level
- **Staleness tracking** — status bar shows how many docs need regeneration, updates when source files change
- **LLM provider setup** — configure Anthropic, OpenAI, Google, or Ollama from the command palette; API keys stored in OS keychain via VS Code SecretStorage

## Commands

| Command | What it does |
|---------|--------------|
| `Chronicler: Init` | Set up a project with config + merkle tree |
| `Chronicler: Regenerate Stale` | Re-draft docs for changed source files |
| `Chronicler: Show Status` | Print staleness report to output channel |
| `Chronicler: Create .tech.md` | Scaffold a new component doc from template |
| `Chronicler: Show Dependency Graph` | Open interactive graph view |
| `Chronicler: Setup LLM Provider` | Configure which LLM to use for drafting |

## How it works

Chronicler writes `.tech.md` files — plain Markdown with YAML frontmatter — into a `.chronicler/` directory in your repo. Each file follows a fixed structure:

- YAML frontmatter (component ID, owner team, layer, edges, security level)
- Architectural intent (what this does, why it exists, key responsibilities)
- Connectivity graph (Mermaid diagram of dependencies)
- Links to satellite docs (QA blueprints, audit logs, invariants)

Source files are SHA-256 hashed into a merkle tree. When hashes change but the corresponding doc hasn't been updated, it's flagged stale. The status bar reflects this in real time.

## Requirements

- Python 3.11+ with `chronicler-lite` installed
- An LLM API key (Anthropic, OpenAI, Google) or a local Ollama instance

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `chronicler.pythonPath` | `python3` | Python interpreter with chronicler-lite |
| `chronicler.llm.provider` | `anthropic` | LLM provider for doc generation |
| `chronicler.watch.sourceGlob` | `**/*.{ts,js,py,rs,go,java}` | Source files to watch for staleness |
| `chronicler.techMdGlob` | `**/.chronicler/**/*.tech.md` | Where to find `.tech.md` files |
| `chronicler.graph.layout` | `force-directed` | Graph layout algorithm |
| `chronicler.graph.colorBy` | `layer` | Node color scheme |

## Cross-document linking

Each `.tech.md` can declare edges to other components:

```yaml
edges:
  - target: "agent://auth-service/handler.tech.md"
    relationship: "CONSUMES"
    transport: "grpc"
```

These URIs let you click-navigate between docs. The extension resolves them to local files or, with a GraphQL endpoint configured, to components in other repos.

## Companion tools

- **[Chronicler CLI](https://github.com/shihwesley/chronicler)** — Claude Code plugin for automated doc generation
- **[obsidian-chronicler](https://github.com/shihwesley/obsidian-chronicler)** — Obsidian plugin with graph view and `agent://` link rendering

## Security

API keys are stored in VS Code's SecretStorage (OS keychain) and injected as environment variables at subprocess spawn time. They never touch disk or appear in settings JSON.

## License

MIT
