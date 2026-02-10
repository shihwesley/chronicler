---
name: vscode-spec
phase: 2
sprint: 2
parent: manifest
depends_on: [hooks-skill-spec, freshness-spec]
status: draft
created: 2026-02-10
---

# VS Code Extension Spec: Generation + Rich Viewing

## Goal

A VS Code extension that (a) runs Chronicler on the current workspace to generate `.tech.md` files, and (b) provides rich rendering: clickable links, graph visualization, backlinks sidebar, and hover previews. Works in VS Code, Cursor, Windsurf, and any VS Code fork.

Because VS Code is the foundation for most AI-native IDEs, this single extension covers the widest possible audience.

## Requirements

1. **Command: Chronicler Init** — runs Python engine on workspace, generates all .tech.md
2. **Command: Chronicler Regenerate** — force-regenerate stale docs
3. **Command: Chronicler Status** — show staleness summary in output panel
4. **File watcher** — detects source file changes, marks .tech.md stale (status bar indicator)
5. **Link provider** — makes `agent://` URIs and `[[wiki-links]]` in .tech.md clickable
6. **Hover provider** — preview target .tech.md on hover over links
7. **Backlinks panel** — TreeView sidebar showing what links to the current .tech.md
8. **Graph panel** — WebView with interactive dependency graph (D3.js force layout)
9. **Diagnostics** — broken link warnings (squiggly underlines)
10. **LLM provider selection** — use workspace's configured LLM (Copilot, OpenAI key, local model via settings)
11. **Status bar** — shows "Chronicler: 3 stale" with click to regenerate

## Acceptance Criteria

- [ ] Extension activates when `.chronicler/` folder exists in workspace
- [ ] "Chronicler: Init" command generates .tech.md files for workspace
- [ ] Clicking an `agent://` link in .tech.md opens the target file
- [ ] Hovering over a link shows preview of target .tech.md
- [ ] Backlinks panel shows incoming references for current .tech.md
- [ ] Graph panel renders interactive force-directed graph
- [ ] Status bar shows stale count, updates on file changes
- [ ] Works in Cursor and Windsurf (no VS Code-specific APIs)

## Technical Approach

Follow the architecture from `docs/plans/2026-02-05-ide-integration-design.md`:

```
chronicler-vscode/
  src/
    core/                    # Platform-agnostic
      workspace.ts           # Manages .tech.md resources
      graph.ts               # Dependency graph from YAML edges
      link-resolver.ts       # Resolves agent:// and [[wiki-links]]
      parser.ts              # Parse .tech.md frontmatter + body
    features/                # VS Code providers
      link-provider.ts       # DocumentLinkProvider
      definition-provider.ts # Go to Definition (F12)
      hover-provider.ts      # Preview on hover
      completion-provider.ts # Autocomplete [[links]]
      diagnostics.ts         # Broken link warnings
      graph-panel.ts         # WebView graph (D3.js)
      connections-panel.ts   # TreeView backlinks
    services/
      python-bridge.ts       # Calls chronicler-lite Python engine
      file-watcher.ts        # Watch for source changes
      config.ts              # Extension settings
    extension.ts             # Activation + registration
  webview/
    graph/                   # D3.js force-directed graph
```

Python bridge: the extension calls `python3 -m chronicler_lite.cli` as a subprocess for generation/validation. Viewing features are pure TypeScript (parse .tech.md, build graph, render).

## Files to Create

- Full VS Code extension project in `packages/chronicler-vscode/`
- `package.json` — extension manifest with commands, views, activation events
- All TypeScript source files per architecture above
- WebView assets for graph visualization

## Tasks

1. Scaffold VS Code extension with package.json, activation
2. Implement Python bridge (subprocess calls to chronicler-lite)
3. Build .tech.md parser (YAML frontmatter + markdown body)
4. Implement DocumentLinkProvider + DefinitionProvider
5. Implement HoverProvider + CompletionProvider
6. Build backlinks TreeView panel
7. Build graph WebView panel (D3.js force layout)
8. Add diagnostics for broken links
9. Status bar integration (stale count + file watcher)
10. Test in VS Code, Cursor, Windsurf

## Dependencies

- **Upstream:** hooks-skill-spec (reuses Python engine patterns), freshness-spec (staleness API)
- **Downstream:** None
