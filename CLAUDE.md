# CLAUDE.md

Living Technical Ledger — enterprise doc system where every app gets a standardized `.tech.md`, replacing RAG with pre-digested AI-ready indexes.

**Companion project:** Mnemon (3D Knowledge Graph visualization) consumes Chronicler's GraphQL output.

## Architecture

Three core services (all planned):
1. **Orchestrator** — bootstraps repos with Technical Ledgers (VCS Crawler, Metadata Harvester, AI Drafter, PR Engine)
2. **Continuous Harvester** — webhook-driven diff analysis, drift detection (fails CI if docs stale)
3. **GraphQL Indexer** — crawls `.chronicler/` folders into graph DB, exposes query layer for Mnemon

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
