import { Plugin, WorkspaceLeaf } from 'obsidian';

import { AgentUriProcessor } from './processors/agent-uri-processor';
import { DependencyExplorerView, DEPENDENCY_VIEW_TYPE } from './views/dependency-view';
import { HealthDashboardView, HEALTH_VIEW_TYPE } from './views/health-view';
import { ChroniclerCommands } from './commands';
import { ChroniclerSettingTab, ChroniclerSettings, DEFAULT_SETTINGS } from './settings';
import { DiscoveryService, createManualDiscovery } from './services/discovery';
import { VaultWatcher } from './services/watcher';

export default class ChroniclerPlugin extends Plugin {
  settings: ChroniclerSettings = DEFAULT_SETTINGS;
  discovery!: DiscoveryService;

  private agentUriProcessor: AgentUriProcessor | null = null;
  private commands: ChroniclerCommands | null = null;
  private watcher: VaultWatcher | null = null;

  async onload(): Promise<void> {
    await this.loadSettings();

    // Set up discovery based on mode
    if (this.settings.discoveryMode === 'manual') {
      this.discovery = createManualDiscovery(this.app, this.settings.chroniclerFolder);
    } else {
      this.discovery = new DiscoveryService(this.app);
    }
    await this.discovery.discover();

    this.addSettingTab(new ChroniclerSettingTab(this.app, this));

    // Register the markdown post-processor for agent:// links
    this.agentUriProcessor = new AgentUriProcessor();
    this.agentUriProcessor.register(this);

    // Register custom views
    this.registerView(DEPENDENCY_VIEW_TYPE, (leaf: WorkspaceLeaf) => {
      return new DependencyExplorerView(leaf, this);
    });

    this.registerView(HEALTH_VIEW_TYPE, (leaf: WorkspaceLeaf) => {
      return new HealthDashboardView(leaf, this);
    });

    // Register commands
    this.commands = new ChroniclerCommands();
    this.commands.registerAll(this);

    // Watch vault for .tech.md file changes across all discovered projects
    this.watcher = new VaultWatcher(this.app, this.discovery);
    this.watcher.onFileChange((file, project) => {
      this.handleTechFileModified(file.path, project.folderPath);
    });
    this.watcher.start();
  }

  async onunload(): Promise<void> {
    this.watcher?.stop();
    this.discovery?.stopWatching();
  }

  async loadSettings(): Promise<void> {
    const data = await this.loadData();
    this.settings = Object.assign({}, DEFAULT_SETTINGS, data);
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  /**
   * Called when a .tech.md file is modified. Triggers _map.md regeneration
   * for the project that owns the file.
   */
  private handleTechFileModified(path: string, projectFolder: string): void {
    console.debug(`Chronicler: .tech.md modified — ${path}`);

    // Regenerate _map.md for this project
    const client = new ChroniclerClient(this.app);
    const vaultPath = (this.app.vault.adapter as { getBasePath?(): string }).getBasePath?.() ?? '';
    const sourceDir = `${vaultPath}/${projectFolder}`;

    // Fire-and-forget CLI call
    const { execFile } = require('child_process');
    execFile(
      'chronicler',
      ['obsidian', 'map', '--source', sourceDir],
      { timeout: 30_000 },
      () => { /* ignore result for background regen */ },
    );
  }
}
