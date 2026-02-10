import { Plugin, WorkspaceLeaf } from 'obsidian';

import { AgentUriProcessor } from './processors/agent-uri-processor';
import { DependencyExplorerView, DEPENDENCY_VIEW_TYPE } from './views/dependency-view';
import { HealthDashboardView, HEALTH_VIEW_TYPE } from './views/health-view';
import { ChroniclerCommands } from './commands';
import { ChroniclerSettingTab, ChroniclerSettings, DEFAULT_SETTINGS } from './settings';

export default class ChroniclerPlugin extends Plugin {
  settings: ChroniclerSettings = DEFAULT_SETTINGS;

  private agentUriProcessor: AgentUriProcessor | null = null;
  private commands: ChroniclerCommands | null = null;

  async onload(): Promise<void> {
    await this.loadSettings();

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

    // Watch vault for .tech.md file changes
    this.registerEvent(
      this.app.vault.on('modify', (file) => {
        if (file.path.endsWith('.tech.md')) {
          this.handleTechFileModified(file.path);
        }
      })
    );
  }

  async onunload(): Promise<void> {
    // Views are automatically deregistered by Obsidian on unload
  }

  async loadSettings(): Promise<void> {
    const data = await this.loadData();
    this.settings = Object.assign({}, DEFAULT_SETTINGS, data);
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  /**
   * Called when a .tech.md file is modified in the vault.
   * Will be wired to the VaultWatcher service later.
   */
  private handleTechFileModified(path: string): void {
    // Stub — VaultWatcher will handle sync logic
    console.debug(`Chronicler: .tech.md modified — ${path}`);
  }
}
