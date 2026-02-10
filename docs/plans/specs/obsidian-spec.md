---
name: obsidian-spec
phase: 2
sprint: 2
parent: manifest
depends_on: [freshness-spec]
status: draft
created: 2026-02-10
---

# Obsidian Spec: Vault Sync + Graph Browsing

## Goal

Let developers browse their project's `.tech.md` documentation in Obsidian as a rich knowledge base — with graph view, backlinks, Dataview queries, and mobile access. A sync daemon watches `.chronicler/` and mirrors transformed files into an Obsidian vault.

Target: vibe coders who already use Obsidian for personal notes and want their project docs in the same place.

## Requirements

1. **Sync daemon** — watches `.chronicler/` for changes, transforms and writes to Obsidian vault
2. **Link rewriting** — `agent://service/file.tech.md` → `[[file]]` (Obsidian wiki-links)
3. **Frontmatter mapping** — YAML schema adapted for Obsidian Properties (Dataview-compatible)
4. **Dataview fields** — inline `[key:: value]` fields for Dataview table queries
5. **Index generation** — `_index.md` per project with MOC (Map of Content) linking all docs
6. **Vault structure** — one folder per project: `Chronicler/project-name/`
7. **Graph-friendly** — wiki-links produce edges in Obsidian's graph view automatically
8. **Export command** — one-shot export (no daemon) for users who prefer manual sync
9. **Mobile-friendly** — synced vault works on Obsidian Mobile (iCloud/Obsidian Sync)

## Acceptance Criteria

- [ ] `chronicler obsidian sync --watch` starts daemon, mirrors .tech.md to vault
- [ ] `agent://` links are rewritten to `[[wiki-links]]` in vault copies
- [ ] YAML frontmatter contains Obsidian-compatible Properties
- [ ] Dataview query `TABLE tags, layer FROM "Chronicler/my-project"` returns results
- [ ] Obsidian graph view shows interconnected .tech.md docs
- [ ] `_index.md` provides a Map of Content for the project
- [ ] `chronicler obsidian export` does one-shot sync (no daemon)
- [ ] Files sync to mobile via iCloud/Obsidian Sync

## Technical Approach

Follow the architecture from `docs/plans/2026-02-05-obsidian-integration-design.md`:

### Transform Pipeline

```
.chronicler/api-service.tech.md
    → Parse YAML frontmatter + body
    → Rewrite agent:// links → [[wiki-links]]
    → Map frontmatter fields to Obsidian Properties
    → Add Dataview inline fields
    → Write to vault: ~/Obsidian/Chronicler/project-name/api-service.md
```

### Sync Daemon

```python
# Uses watchdog for file system events
class ObsidianSyncDaemon:
    def __init__(self, project_path: str, vault_path: str):
        self.watcher = FileWatcher(project_path / ".chronicler")
        self.transformer = TechMdToObsidianTransformer()
        self.writer = VaultWriter(vault_path)

    async def run(self):
        async for event in self.watcher.watch():
            transformed = self.transformer.transform(event.file)
            self.writer.write(transformed)
```

### Vault Writer Modes

1. **Filesystem** (default) — direct file write to vault folder
2. **REST API** — via Obsidian Local REST API plugin (for locked vaults)

## Files to Create/Modify

- `packages/chronicler-lite/src/chronicler_lite/obsidian/__init__.py`
- `packages/chronicler-lite/src/chronicler_lite/obsidian/daemon.py` — file watcher + sync loop
- `packages/chronicler-lite/src/chronicler_lite/obsidian/transformer.py` — .tech.md → Obsidian .md
- `packages/chronicler-lite/src/chronicler_lite/obsidian/link_rewriter.py` — agent:// → [[wiki-links]]
- `packages/chronicler-lite/src/chronicler_lite/obsidian/frontmatter_mapper.py` — YAML → Properties
- `packages/chronicler-lite/src/chronicler_lite/obsidian/vault_writer.py` — write to vault
- `packages/chronicler-lite/src/chronicler_lite/obsidian/index_generator.py` — MOC page
- `tests/test_obsidian_sync.py`

## Tasks

1. Build .tech.md → Obsidian transformer (link rewriting + frontmatter mapping)
2. Implement vault writer (filesystem mode)
3. Implement sync daemon with watchdog
4. Build index/MOC generator
5. Add Dataview inline field injection
6. CLI commands: `chronicler obsidian sync --watch` and `chronicler obsidian export`
7. Tests: transform fidelity, link rewriting, frontmatter mapping

## Dependencies

- **Upstream:** freshness-spec (reuses file watcher, knows which files changed)
- **Downstream:** None
