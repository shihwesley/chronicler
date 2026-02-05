# Obsidian Integration Design: Sync Daemon + Community Plugin

> Date: 2026-02-05
> Status: Draft
> Depends on: Product Architecture (Lite/Enterprise split), AI Drafter output format

## Goal

Make Chronicler's `.tech.md` documentation browsable in Obsidian as a rich, interconnected knowledge base. Two-phase approach: (A) sync daemon that keeps an Obsidian vault in sync with `.chronicler/` output, and (B) a native Obsidian community plugin for deeper integration.

Target audience: "vibe coders" and developers who use Obsidian for personal knowledge management and want to browse their project's technical documentation with Obsidian's graph view, backlinks, and Dataview queries.

## Research: Obsidian Ecosystem (Key Takeaways)

**Vault = folder of .md files.** No proprietary format. Drop `.md` files in, Obsidian auto-indexes them. YAML frontmatter is parsed automatically into Properties.

**Wiki-links**: `[[note-name]]` creates bidirectional links. Obsidian resolves by filename (case-insensitive, normalizes spaces/hyphens). Supports `[[note#heading]]` and `[[note|alias]]`.

**Dataview plugin**: SQL-like query language over YAML frontmatter. `TABLE tags, version FROM #tech-doc WHERE layer = "api"` creates live, auto-updating tables. This is the killer feature for Chronicler integration.

**Key integration points:**
| Mechanism | Purpose |
|-----------|---------|
| File system write | Simplest: copy .md files to vault folder |
| Local REST API plugin | HTTPS REST for programmatic CRUD on vault notes |
| Advanced URI plugin | `obsidian://adv-uri?file=...` for deep linking |
| Obsidian Plugin API | Full vault access: read, write, events, UI panels |
| MCP Server | AI agent integration via Model Context Protocol |

**Critical insight**: Chronicler's `.tech.md` files with YAML frontmatter already contain everything Obsidian needs. The challenge is format adaptation (component_id-based names → Obsidian-friendly names, agent:// → [[wiki-links]]).

## Architecture

### Phase A: Sync Daemon

```
chronicler-obsidian-sync/
  src/
    sync/
      daemon.ts              # File watcher + sync loop
      transformer.ts         # .tech.md → Obsidian-ready .md
      link-rewriter.ts       # agent:// → [[wiki-links]]
      frontmatter-mapper.ts  # YAML schema → Obsidian Properties
      vault-writer.ts        # Write to vault (filesystem or REST API)
    config.ts                # Sync configuration
    cli.ts                   # chronicler obsidian sync/export commands
```

**Data flow:**
```mermaid
stateDiagram-v2
    [*] --> Watch: chronicler obsidian sync --watch

    state "File Watcher" as Watch {
        [*] --> DetectChange
        DetectChange --> ReadTechMd: .tech.md changed
        ReadTechMd --> Transform
    }

    state "Transform Pipeline" as Transform {
        [*] --> RewriteLinks: agent:// → [[wiki-links]]
        RewriteLinks --> MapFrontmatter: Add Obsidian-friendly props
        MapFrontmatter --> AddDataviewFields: Inline [key:: value] fields
        AddDataviewFields --> GenerateIndex: Update _index.md
        GenerateIndex --> [*]
    }

    state "Vault Writer" as Write {
        [*] --> CheckMode
        CheckMode --> FileSystem: filesystem mode
        CheckMode --> RestAPI: rest-api mode
        FileSystem --> WriteFile
        RestAPI --> PostToAPI
    }

    Transform --> Write
    Write --> [*]
```

#### Transform Pipeline Detail

**1. Link Rewriting (`link-rewriter.ts`)**

| Input (Chronicler) | Output (Obsidian) |
|---------------------|-------------------|
| `agent://auth-service/api.tech.md` | `[[auth-service - api]]` |
| `agent://other-repo/service.tech.md` | `[[other-repo/service]]` (or external link) |
| `[[db-connector]]` | `[[db-connector]]` (passthrough) |
| Standard markdown links | Passthrough |

Cross-repo `agent://` links that can't resolve locally become markdown links to the GraphQL explorer UI (enterprise) or are tagged with `[external]`.

**2. Frontmatter Mapping (`frontmatter-mapper.ts`)**

Chronicler YAML → Obsidian Properties:

```yaml
# Input (.tech.md)
---
component_id: "auth-service"
version: "2.1.0"
owner_team: "platform-team"
layer: "api"
security_level: "high"
governance:
  verification_status: "human_verified"
  visibility: "internal"
edges:
  - target: "db-connector"
    type: "reads"
    protocol: "SQL"
---

# Output (Obsidian-ready)
---
title: "Auth Service"
aliases: ["auth-service"]
tags: [tech-doc, api, security-high, platform-team]
component_id: "auth-service"
version: "2.1.0"
owner_team: "platform-team"
layer: "api"
security_level: "high"
verification_status: "human_verified"
visibility: "internal"
dependencies: ["db-connector", "crypto-utils"]
cssclass: chronicler-doc
---
```

Key mappings:
- `component_id` → `aliases` (for wiki-link resolution)
- `layer` + `security_level` + `owner_team` → flattened into `tags` for graph filtering
- `governance` → flattened (Obsidian Properties UI doesn't handle deep nesting well)
- `edges[].target` → `dependencies` array (Dataview-queryable)
- Added `cssclass: chronicler-doc` for custom Obsidian CSS styling

**3. Dataview Fields (`AddDataviewFields`)**

Inject inline Dataview fields for rich querying:

```markdown
## Dependencies

[depends_on:: [[db-connector]]] via SQL
[depends_on:: [[crypto-utils]]] via internal API
[called_by:: [[api-gateway]]]
```

This enables Dataview queries like:
```
TABLE depends_on, called_by FROM #tech-doc
WHERE layer = "api"
SORT component_id ASC
```

**4. Index Generation (`GenerateIndex`)**

Auto-generate `_index.md` in vault root:

```markdown
---
title: "Chronicler Documentation Index"
tags: [chronicler-index]
---

# Project Documentation

## By Layer
### Infrastructure
- [[db-connector]]
- [[redis-cache]]

### Logic
- [[auth-service]]
- [[payment-processor]]

### API
- [[api-gateway]]
- [[webhook-handler]]

## Dataview: All Services

\`\`\`dataview
TABLE version, owner_team, security_level
FROM #tech-doc
SORT layer, component_id
\`\`\`

## Dataview: Dependency Graph

\`\`\`dataview
TABLE dependencies AS "Depends On", called_by AS "Called By"
FROM #tech-doc
WHERE length(dependencies) > 0
SORT component_id
\`\`\`
```

#### Sync Modes

| Mode | Command | Mechanism |
|------|---------|-----------|
| One-shot export | `chronicler obsidian export --vault ~/my-vault` | Copy transformed files to vault folder |
| Watch mode | `chronicler obsidian sync --watch` | chokidar watcher on `.chronicler/`, writes on change |
| REST API mode | `chronicler obsidian sync --rest` | Push via Obsidian Local REST API plugin |

#### Configuration (`chronicler.yaml` addition)

```yaml
obsidian:
  vault_path: "~/Documents/TechDocs"        # Target vault
  sync_mode: "filesystem"                    # filesystem | rest-api
  rest_api:
    url: "https://localhost:27124"
    token: "${OBSIDIAN_REST_TOKEN}"
  transform:
    rewrite_agent_uris: true
    flatten_governance: true
    add_dataview_fields: true
    generate_index: true
    css_class: "chronicler-doc"
  mapping:
    tags_from: ["layer", "security_level", "owner_team"]
    aliases_from: ["component_id"]
```

---

### Phase B: Obsidian Community Plugin

```
obsidian-chronicler/
  src/
    main.ts                  # Plugin entry point
    settings.ts              # Plugin settings tab
    views/
      dependency-view.ts     # Custom leaf: dependency explorer
      health-view.ts         # Custom leaf: doc health dashboard
    commands/
      sync-command.ts        # Manual sync trigger
      create-tech-md.ts      # Create new .tech.md from template
      browse-graph.ts        # Open filtered graph view
    services/
      chronicler-client.ts   # Connect to Chronicler CLI or GraphQL
      watcher.ts             # Watch for .tech.md changes
      link-resolver.ts       # Resolve agent:// within Obsidian
    processors/
      agent-uri-processor.ts # Render agent:// links as clickable
      tech-md-processor.ts   # Custom rendering for .tech.md
    styles.css               # Custom styles for .tech.md rendering
  manifest.json              # Obsidian plugin manifest
```

#### Plugin Features

**1. Agent URI Handler**
Register custom markdown post-processor:
- Detects `agent://` in rendered markdown
- Converts to clickable Obsidian internal links
- Shows tooltip with target service metadata

**2. Dependency Explorer View**
Custom Obsidian leaf (sidebar panel):
- Tree view of current .tech.md's dependencies
- Click to navigate
- Shows dependency chain depth
- Warning icons for circular dependencies

**3. Doc Health Dashboard**
Custom Obsidian leaf:
- Lists all `.tech.md` files with health scores
- Flags: outdated versions, missing fields, `[FLAG:OUTDATED]` markers
- Percentage of docs with `human_verified` vs `ai_draft`
- Stale docs (not updated in X days)

**4. Chronicler Commands**
| Command | Description |
|---------|-------------|
| `Chronicler: Sync Now` | Pull latest .tech.md from repo/CLI |
| `Chronicler: Create .tech.md` | Template-based creation with YAML scaffold |
| `Chronicler: Show Dependencies` | Open dependency explorer for current note |
| `Chronicler: Browse by Layer` | Filter graph view by infrastructure/logic/api |
| `Chronicler: Check Health` | Open health dashboard |

**5. Custom CSS (`styles.css`)**
```css
/* Style .tech.md files distinctively */
.chronicler-doc .markdown-preview-view {
  --tag-color: var(--interactive-accent);
}
.chronicler-doc .yaml-frontmatter {
  background: var(--background-secondary);
  border-left: 3px solid var(--interactive-accent);
  padding: 8px;
}
```

**6. Graph View Enhancements**
- Color nodes by `layer` (infrastructure=blue, logic=green, api=orange)
- Filter graph to show only `#tech-doc` tagged notes
- Highlight `security_level: critical` nodes in red

#### Obsidian Plugin API Usage

| API | Purpose |
|-----|---------|
| `Plugin.registerMarkdownPostProcessor()` | Custom rendering for agent:// links |
| `Plugin.addCommand()` | Register Chronicler commands |
| `Plugin.addSettingTab()` | Configuration UI |
| `Plugin.registerView()` | Custom sidebar panels |
| `Vault.on('modify')` | Watch for .tech.md changes |
| `MetadataCache.getFileCache()` | Read parsed YAML frontmatter |
| `Workspace.getLeaf()` | Open custom views |

## Implementation Phases

| Phase | Deliverable | Effort |
|-------|-------------|--------|
| 8a | Sync daemon: transform pipeline + filesystem export | Core |
| 8b | Sync daemon: watch mode + REST API mode | Enhancement |
| 8c | Obsidian plugin: agent:// handler + dependency view | Core |
| 8d | Obsidian plugin: health dashboard + graph enhancements | Polish |

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Sync daemon first, plugin second | Sync is simpler, delivers value immediately, plugin can build on synced files |
| Transform pipeline (not raw copy) | .tech.md needs adaptation: link rewriting, frontmatter flattening, Dataview fields |
| Filesystem + REST API modes | Filesystem is simplest; REST API enables real-time sync without file watching |
| Community plugin (not core) | Obsidian's plugin ecosystem is the standard distribution channel |
| Dataview fields injection | Turns passive docs into queryable database — Obsidian's killer feature |
| _index.md generation | Instant overview of entire documentation set with Dataview queries |
| CSS class tagging | Visual distinction between Chronicler docs and user's personal notes |
| Aliases from component_id | Wiki-link `[[auth-service]]` resolves even if filename is different |
