# Findings & Decisions

## Goal
Package Chronicler Lite for vibe coders with ambient, zero-thought documentation that stays fresh.

## Priority
Quality — polish, docs, error handling, production-ready first impression.

## Approach
Ambient Hooks + Skill + Python Engine. No MCP server. No separate daemon to manage.
- Hooks make it invisible after `/chronicler init`
- Skill provides manual override commands
- Python engine (pip installable) does the actual work
- VS Code extension for IDE users (generation + rich viewing)
- Obsidian sync for knowledge graph browsing + mobile

## Requirements (validated by user)
1. Claude Code integration: ambient hooks + /chronicler skill
2. VS Code extension: generation + viewing (links, graph, backlinks)
3. Obsidian vault sync: graph view, Dataview, mobile access
4. Freshness daemon: auto-detect stale .tech.md, regenerate
5. Multi-LLM: Claude, OpenAI, Gemini, Ollama/local
6. Zero-thought after init: user never manually invokes Chronicler again

## Key Decision: No MCP Server
User's experience with MCP in Claude Code wasn't great — tools feel like things you have to remember to invoke. Hooks are ambient; they run without user thought. The hook + skill pattern matches the user's existing workflow (TLDR hooks, session-catchup, etc.).

## Key Decision: MCP-first → Hooks-first
Original plan was MCP server. Revised to hooks + skill after user feedback. The Python engine is still pip-installable and callable from any context (VS Code, Obsidian daemon, CLI if needed later).

## Research Findings
- Existing design docs cover VS Code extension architecture in detail (Foam-inspired)
- Existing design docs cover Obsidian sync daemon architecture
- Product architecture design already defines monorepo layout
- Post-MVP task plan already outlines phases 5a-5e, 7a-7d, 8a-8b
- Current codebase has 27 .py files in flat `chronicler/` — needs monorepo restructure

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Hooks over MCP | Ambient UX — user never thinks about Chronicler after init |
| uv workspaces | Modern Python packaging, fast installs, workspace support |
| watchdog for file watching | Proven, cross-platform, used in existing Obsidian design |
| D3.js for VS Code graph | Same as existing IDE design doc, lightweight for WebView |
| Multi-LLM via provider protocol | Vibe coders use different tools — meet them where they are |
| Monorepo (all packages) | Core + Lite + Enterprise in one repo for dev. Enterprise extracts at publish time. |
| VS Code + Obsidian under Lite | They're distribution channels of Lite, not independent products |
| Lite is open source (MIT/Apache) | Public GitHub, public PyPI. Enterprise goes private at publish time. |
| chronicler-lite[obsidian] extra | Obsidian sync is optional — not all Lite users need it |

## Visual/Browser Findings
(none yet)
