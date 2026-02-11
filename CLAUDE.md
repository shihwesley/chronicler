# CLAUDE.md

Living Technical Ledger — enterprise doc system where every app gets a standardized `.tech.md`, replacing RAG with pre-digested AI-ready indexes.

**Companion project:** Mnemon (3D Knowledge Graph visualization) consumes Chronicler's GraphQL output.

## Architecture

Three core services (all planned):
1. **Orchestrator** — bootstraps repos with Technical Ledgers (VCS Crawler, Metadata Harvester, AI Drafter, PR Engine)
2. **Continuous Harvester** — webhook-driven diff analysis, drift detection (fails CI if docs stale)
3. **GraphQL Indexer** — crawls `.chronicler/` folders into graph DB, exposes query layer for Mnemon

## Exploration Protocol

When exploring or understanding this codebase:

1. **Start with the index.** Read `.chronicler/INDEX.md` for the full component map with one-line purposes.
2. **Dive into .tech.md** for any component you need to understand. Each has purpose, key functions, dependencies, and architectural notes. Path convention: `path/to/file.py` → `.chronicler/path--to--file.py.tech.md`
3. **Read source only when modifying.** The .tech.md gives you enough context for understanding; read the actual `.py` file only when you need to edit it or when the .tech.md is flagged stale.
4. **Check edges.** The `edges` field in each .tech.md frontmatter maps imports — use it to trace dependencies without grepping.

## AI Agent Rules

Before modifying code:
1. Read the `.tech.md` for target component
2. Check Mnemon graph for "Blast Radius" warnings
3. Verify proposed change doesn't violate `.invariants.md`

PRs incomplete unless: YAML updated, Audit Log entry added, QA-Blueprint updated if logic changed.

Flag discrepancies with `[FLAG:OUTDATED]` rather than making assumptions.

## Documentation

For naming patterns, YAML schema, hub-and-spoke model, and phases, see `docs/CONVENTIONS.md`
For product requirements, see `docs/prd.md`
For technical spec, see `docs/spec.md`
For design decisions, see `docs/plans/`
