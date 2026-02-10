import { App, PluginSettingTab, Setting } from 'obsidian';
import type ChroniclerPlugin from './main';

export interface ChroniclerSettings {
  chroniclerFolder: string;
  autoSync: boolean;
  syncInterval: number;
  restApiUrl: string;
  restApiToken: string;
  mermaidTheme: string;
  graphColorByLayer: boolean;
}

export const DEFAULT_SETTINGS: ChroniclerSettings = {
  chroniclerFolder: 'chronicler',
  autoSync: false,
  syncInterval: 300,
  restApiUrl: 'http://localhost:3000',
  restApiToken: '',
  mermaidTheme: 'default',
  graphColorByLayer: true,
};

export class ChroniclerSettingTab extends PluginSettingTab {
  plugin: ChroniclerPlugin;

  constructor(app: App, plugin: ChroniclerPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl('h2', { text: 'Chronicler Settings' });

    new Setting(containerEl)
      .setName('Chronicler folder')
      .setDesc('Subfolder in your vault for .tech.md files')
      .addText((text) =>
        text
          .setPlaceholder('chronicler')
          .setValue(this.plugin.settings.chroniclerFolder)
          .onChange(async (value) => {
            this.plugin.settings.chroniclerFolder = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Auto sync')
      .setDesc('Automatically sync documents from the Chronicler API')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.autoSync)
          .onChange(async (value) => {
            this.plugin.settings.autoSync = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Sync interval')
      .setDesc('How often to sync, in seconds')
      .addText((text) =>
        text
          .setPlaceholder('300')
          .setValue(String(this.plugin.settings.syncInterval))
          .onChange(async (value) => {
            const parsed = parseInt(value, 10);
            if (!isNaN(parsed) && parsed > 0) {
              this.plugin.settings.syncInterval = parsed;
              await this.plugin.saveSettings();
            }
          })
      );

    new Setting(containerEl)
      .setName('REST API URL')
      .setDesc('Base URL for the Chronicler REST API')
      .addText((text) =>
        text
          .setPlaceholder('http://localhost:3000')
          .setValue(this.plugin.settings.restApiUrl)
          .onChange(async (value) => {
            this.plugin.settings.restApiUrl = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('REST API token')
      .setDesc('Authentication token for the Chronicler API')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Token')
          .setValue(this.plugin.settings.restApiToken)
          .onChange(async (value) => {
            this.plugin.settings.restApiToken = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName('Mermaid theme')
      .setDesc('Theme for beautiful-mermaid rendered diagrams')
      .addDropdown((dropdown) =>
        dropdown
          .addOption('default', 'Default')
          .addOption('dark', 'Dark')
          .addOption('forest', 'Forest')
          .addOption('neutral', 'Neutral')
          .setValue(this.plugin.settings.mermaidTheme)
          .onChange(async (value) => {
            this.plugin.settings.mermaidTheme = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName('Color graph by layer')
      .setDesc('Color dependency graph nodes by their architecture layer')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.graphColorByLayer)
          .onChange(async (value) => {
            this.plugin.settings.graphColorByLayer = value;
            await this.plugin.saveSettings();
          })
      );
  }
}
