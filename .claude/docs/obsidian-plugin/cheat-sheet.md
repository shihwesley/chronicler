# Obsidian Plugin API Cheat Sheet

## Plugin Scaffold

**manifest.json** (repository root)
```json
{
  "id": "chronicler-obsidian",
  "name": "Chronicler",
  "version": "1.0.0",
  "minAppVersion": "1.0.0",
  "description": "Sync and browse Chronicler technical docs in Obsidian",
  "author": "Chronicler",
  "isDesktopOnly": false
}
```

**main.ts** — Plugin lifecycle
```typescript
import { App, Plugin, PluginSettingTab, Setting, WorkspaceLeaf } from 'obsidian';

export default class ChroniclerPlugin extends Plugin {
  settings: ChroniclerSettings;
  async onload() {
    await this.loadSettings();
    this.addSettingTab(new ChroniclerSettingTab(this.app, this));
    this.registerView(VIEW_TYPE, (leaf) => new DependencyExplorerView(leaf));
    this.addCommand({ id: 'sync', name: 'Sync from repo', callback: () => this.sync() });
    this.registerMarkdownPostProcessor((el, ctx) => this.processAgentLinks(el, ctx));
    this.registerEvent(this.app.vault.on('modify', (file) => { /* track changes */ }));
  }
  onunload() { /* automatic cleanup via registerEvent/registerView */ }
  async loadSettings() { this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData()); }
  async saveSettings() { await this.saveData(this.settings); }
}
```

## MarkdownPostProcessor (agent:// URIs)

```typescript
processAgentLinks(element: HTMLElement, context: MarkdownPostProcessorContext) {
  const codeblocks = element.querySelectorAll('code');
  codeblocks.forEach(el => {
    if (el.textContent?.startsWith('agent://')) {
      el.classList.add('agent-link');
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => this.handleAgentURI(el.textContent!));
    }
  });
}

// Custom code block processor
this.registerMarkdownCodeBlockProcessor('agent', (source, el, ctx) => {
  const btn = el.createEl('button', { text: 'Open in Chronicler' });
  btn.onclick = () => { /* handle agent block */ };
});

// URI protocol handler
this.registerObsidianProtocolHandler('agent', async (params) => {
  const { action, id } = params;
  // obsidian://agent?action=open&id=auth-service
});
```

## ItemView (Custom Sidebar — Dependency Explorer)

```typescript
const VIEW_TYPE = 'chronicler-dependency-explorer';

class DependencyExplorerView extends ItemView {
  getViewType() { return VIEW_TYPE; }
  getDisplayText() { return 'Dependencies'; }

  async onOpen() {
    const container = this.containerEl.children[1];
    container.empty();
    container.createEl('h4', { text: 'Dependency Explorer' });
    // Build tree UI here
  }
  async onClose() { /* cleanup */ }
}

// Open view:
async openExplorer() {
  const leaf = this.app.workspace.getRightLeaf(false);
  await leaf.setViewState({ type: VIEW_TYPE, active: true });
  this.app.workspace.revealLeaf(leaf);
}
```

## Vault API

```typescript
// Read
const file = this.app.vault.getAbstractFileByPath('path/to/note.md');
if (file instanceof TFile) {
  const content = await this.app.vault.read(file);
  const cached = await this.app.vault.cachedRead(file); // faster
}
const mdFiles = this.app.vault.getMarkdownFiles();

// Write
await this.app.vault.create('chronicler/auth-service.md', '# Auth Service\n...');
await this.app.vault.modify(file, newContent);
await this.app.vault.createFolder('chronicler/');
await this.app.vault.rename(file, 'new-name.md');

// Events
this.registerEvent(this.app.vault.on('create', (f) => {}));
this.registerEvent(this.app.vault.on('modify', (f) => {}));
this.registerEvent(this.app.vault.on('delete', (f) => {}));
this.registerEvent(this.app.vault.on('rename', (f, oldPath) => {}));
```

## MetadataCache

```typescript
const metadata = this.app.metadataCache.getFileCache(file);
if (metadata) {
  const fm = metadata.frontmatter;        // YAML properties
  const headings = metadata.headings;      // [{level, heading, position}]
  const links = metadata.links;            // [[wikilinks]]
  const embeds = metadata.embeds;          // ![[embedded]]
}

// Resolve link globally
const resolved = this.app.metadataCache.getFirstLinkpathDest('note-name', file.path);

// Backlinks
const backlinks = this.app.metadataCache.getBacklinksForFile(file);

// Unresolved (broken) links
const unresolved = this.app.metadataCache.unresolvedLinks[file.path];

this.registerEvent(this.app.metadataCache.on('changed', (file) => {}));
```

## Settings

```typescript
interface ChroniclerSettings {
  vaultPath: string;
  autoSync: boolean;
  syncInterval: number;
  restApiUrl: string;
}
const DEFAULT_SETTINGS: ChroniclerSettings = {
  vaultPath: '', autoSync: false, syncInterval: 300, restApiUrl: 'http://127.0.0.1:27123'
};

class ChroniclerSettingTab extends PluginSettingTab {
  plugin: ChroniclerPlugin;
  constructor(app: App, plugin: ChroniclerPlugin) { super(app, plugin); this.plugin = plugin; }
  display() {
    const { containerEl } = this;
    containerEl.empty();
    new Setting(containerEl).setName('Vault Path').addText(t => t
      .setValue(this.plugin.settings.vaultPath)
      .onChange(async v => { this.plugin.settings.vaultPath = v; await this.plugin.saveSettings(); }));
    new Setting(containerEl).setName('Auto Sync').addToggle(t => t
      .setValue(this.plugin.settings.autoSync)
      .onChange(async v => { this.plugin.settings.autoSync = v; await this.plugin.saveSettings(); }));
  }
}
```

## Commands

```typescript
this.addCommand({ id: 'sync', name: 'Sync from repo', callback: () => this.sync() });
this.addCommand({
  id: 'create-tech-doc', name: 'Create .tech.md',
  editorCallback: (editor, view) => { editor.replaceSelection('---\ncomponent_id: \n---\n'); }
});
this.addCommand({
  id: 'browse-graph', name: 'Browse dependency graph',
  checkCallback: (checking) => {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (view) { if (!checking) this.openGraph(); return true; }
    return false;
  }
});
```

## Obsidian Local REST API

```bash
# Read note
GET http://127.0.0.1:27123/vault/path/to/note.md
Authorization: Bearer <API_KEY>

# Create note
POST http://127.0.0.1:27123/vault/chronicler/new.md
Body: {"content": "# New Note"}

# Update note
PUT http://127.0.0.1:27123/vault/chronicler/existing.md

# For the sync daemon — use this to write to vault from CLI:
chronicler obsidian sync --rest  # uses Local REST API mode
```

## Build & Publish

**esbuild.config.mjs**
```javascript
import esbuild from 'esbuild';
esbuild.build({
  entryPoints: ['main.ts'],
  bundle: true,
  external: ['obsidian', 'electron', '@codemirror/*', '@lezer/*'],
  format: 'cjs',
  target: 'ES6',
  outfile: 'main.js',
  sourcemap: process.argv[2] !== 'production' ? 'inline' : false,
  minify: process.argv[2] === 'production',
});
```

Publishing: Create GitHub release with `main.js`, `styles.css`, `manifest.json` attached.
BRAT: Users install via Settings > Community Plugins > BRAT with repo URL.
