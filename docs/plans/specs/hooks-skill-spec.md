---
name: hooks-skill-spec
phase: 2
sprint: 1
parent: manifest
depends_on: [llm-adapters-spec, freshness-spec]
status: completed
created: 2026-02-10
---

# Hooks + Skill Spec: Ambient Claude Code Integration

## Goal

Make Chronicler invisible after first setup. The user runs `/chronicler init` once, and hooks handle everything from there: detecting stale docs, regenerating them, keeping the knowledge base fresh. This is the primary distribution channel for vibe coders using Claude Code.

## User Experience

### First time (manual):
```
User: /chronicler init
→ Skill detects project type, generates chronicler.yaml
→ Crawls codebase, generates all .tech.md files
→ Installs hooks into .claude/settings.json (or user's global hooks)
→ "Done. Chronicler will keep your docs fresh automatically."
```

### Every time after (ambient):
```
User opens Claude Code in project:
  → SessionStart hook: checks .merkle.json, reports N stale docs if any

User edits src/api/service.py:
  → PostToolUse hook (Write/Edit): marks api-service.tech.md as potentially stale

User reads .chronicler/api-service.tech.md:
  → PreToolUse hook (Read): checks freshness, regenerates if stale before Claude reads it
```

## Requirements

1. `/chronicler init` skill: auto-detect project, generate config, crawl entire codebase, install hooks
2. `/chronicler regenerate` skill: force-regenerate all or specific .tech.md files
3. `/chronicler status` skill: show staleness report (N fresh, N stale, N uncovered)
4. `/chronicler configure` skill: update chronicler.yaml settings
5. SessionStart hook: fast staleness summary (no regeneration unless user requests)
6. PostToolUse hook (Write/Edit): lightweight — just records changed file paths to a stale-candidates list
7. PreToolUse hook (Read on .tech.md): checks if target .tech.md is stale, regenerates if so
8. Hook installation: `/chronicler init` adds hooks to `.claude/settings.json` automatically
9. Hooks must be fast (<200ms for non-regeneration cases) to avoid blocking the user

## Acceptance Criteria

- [ ] `/chronicler init` in a Python project generates chronicler.yaml + all .tech.md files
- [ ] After init, hooks are registered in .claude/settings.json
- [ ] Editing a .py file triggers PostToolUse hook (records file as changed, <100ms)
- [ ] Reading a stale .tech.md triggers regeneration before content is returned
- [ ] SessionStart hook prints "Chronicler: 3 stale docs detected. Run /chronicler regenerate to update."
- [ ] `/chronicler status` shows table of fresh/stale/uncovered docs
- [ ] Hooks don't break if chronicler-lite isn't installed (graceful degradation)

## Technical Approach

### Hook Scripts

```
~/.claude/hooks/chronicler/
├── session-start.sh       # Check staleness on session open
├── post-write.sh          # Record changed files after Write/Edit
└── pre-read-techmd.sh     # Check freshness before reading .tech.md
```

Each hook calls the Python engine:
```bash
#!/bin/bash
# post-write.sh — runs after Write/Edit tool
python3 -m chronicler_lite.hooks.post_write "$TOOL_INPUT_FILE" 2>/dev/null
```

### Skill File

```
~/.claude/skills/chronicler.md
```

Provides `/chronicler` with subcommands: init, regenerate, status, configure.
The skill instructs Claude to call the Python engine via Bash.

### Hook Registration

`/chronicler init` adds to `.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [{"command": "~/.claude/hooks/chronicler/session-start.sh"}],
    "PostToolUse": [
      {"matcher": "Write|Edit", "command": "~/.claude/hooks/chronicler/post-write.sh"}
    ],
    "PreToolUse": [
      {"matcher": "Read", "command": "~/.claude/hooks/chronicler/pre-read-techmd.sh"}
    ]
  }
}
```

## Files to Create/Modify

- `packages/chronicler-lite/src/chronicler_lite/hooks/session_start.py`
- `packages/chronicler-lite/src/chronicler_lite/hooks/post_write.py`
- `packages/chronicler-lite/src/chronicler_lite/hooks/pre_read_techmd.py`
- `packages/chronicler-lite/src/chronicler_lite/skill/init.py` — project detection + full crawl
- `packages/chronicler-lite/src/chronicler_lite/skill/status.py` — staleness report
- Shell wrappers: `hooks/chronicler/session-start.sh`, `post-write.sh`, `pre-read-techmd.sh`
- Skill markdown: `chronicler.md`
- Tests: hook behavior, init flow, hook performance (<200ms)

## Tasks

1. Design hook architecture (shell wrapper → Python entry point)
2. Implement SessionStart hook (fast staleness check)
3. Implement PostToolUse hook (record changed files)
4. Implement PreToolUse hook (freshness gate for .tech.md reads)
5. Build /chronicler init skill (project detection, config gen, full crawl, hook installation)
6. Build /chronicler status + regenerate + configure skills
7. Tests: hook timing, graceful degradation, end-to-end flow

## Dependencies

- **Upstream:** llm-adapters-spec (init needs LLM for drafting), freshness-spec (hooks use staleness checker)
- **Downstream:** vscode-spec (may reuse hook patterns)
