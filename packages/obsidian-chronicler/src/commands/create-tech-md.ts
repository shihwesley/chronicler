import { App, Notice, Modal, Setting, TFile, FuzzySuggestModal } from 'obsidian';

import type { DiscoveryService, DiscoveredProject } from '../services/discovery';

const LAYERS = ['infrastructure', 'logic', 'api', 'data', 'external'] as const;

/**
 * Simple modal that prompts for a component name and layer.
 */
class NewTechDocModal extends Modal {
  private componentName = '';
  private layer: typeof LAYERS[number] = 'logic';
  private onSubmit: (name: string, layer: string) => void;

  constructor(app: App, onSubmit: (name: string, layer: string) => void) {
    super(app);
    this.onSubmit = onSubmit;
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl('h3', { text: 'New .tech.md' });

    new Setting(contentEl)
      .setName('Component name')
      .addText((text) => {
        text.setPlaceholder('e.g. AuthService');
        text.onChange((value) => {
          this.componentName = value.trim();
        });
        // Focus the input on open
        setTimeout(() => text.inputEl.focus(), 50);
      });

    new Setting(contentEl)
      .setName('Layer')
      .addDropdown((dropdown) => {
        for (const l of LAYERS) {
          dropdown.addOption(l, l);
        }
        dropdown.setValue(this.layer);
        dropdown.onChange((value) => {
          this.layer = value as typeof LAYERS[number];
        });
      });

    new Setting(contentEl)
      .addButton((btn) => {
        btn.setButtonText('Create')
          .setCta()
          .onClick(() => {
            if (!this.componentName) {
              new Notice('Component name is required');
              return;
            }
            this.onSubmit(this.componentName, this.layer);
            this.close();
          });
      });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

function buildTemplate(componentName: string, layer: string): string {
  const today = new Date().toISOString().slice(0, 10);
  const componentId = componentName
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .toLowerCase()
    .replace(/\s+/g, '-');

  return `---
component_id: "${componentId}"
layer: "${layer}"
owner: ""
tags: ["tech-doc"]
verification_status: "ai_draft"
last_updated: "${today}"
depends_on: []
---
# ${componentName}

## Purpose

## Architecture

## Dependencies

## API Surface
`;
}

/**
 * Project picker modal — only shown when multiple projects are discovered.
 */
class ProjectPickerModal extends FuzzySuggestModal<DiscoveredProject> {
  private projects: DiscoveredProject[];
  private onChoose: (project: DiscoveredProject) => void;

  constructor(app: App, projects: DiscoveredProject[], onChoose: (project: DiscoveredProject) => void) {
    super(app);
    this.projects = projects;
    this.onChoose = onChoose;
    this.setPlaceholder('Pick a project...');
  }

  getItems(): DiscoveredProject[] {
    return this.projects;
  }

  getItemText(item: DiscoveredProject): string {
    return `${item.projectName} (${item.folderPath})`;
  }

  onChooseItem(item: DiscoveredProject): void {
    this.onChoose(item);
  }
}

/**
 * Opens a modal to collect component info, creates the .tech.md file,
 * and opens it in the editor. Shows a project picker if multiple projects exist.
 */
export async function createTechDoc(app: App, discovery: DiscoveryService): Promise<void> {
  const projects = discovery.getProjects();

  if (projects.length === 0) {
    new Notice('No .chronicler/ folders found. Create one with at least one .tech.md file first.');
    return;
  }

  const createInProject = (project: DiscoveredProject) => {
    return new Promise<void>((resolve) => {
      const modal = new NewTechDocModal(app, async (name, layer) => {
        const fileName = name
          .replace(/([a-z])([A-Z])/g, '$1-$2')
          .toLowerCase()
          .replace(/\s+/g, '-');
        const filePath = `${project.folderPath}/${fileName}.tech.md`;

        const existing = app.vault.getAbstractFileByPath(filePath);
        if (existing) {
          new Notice(`File already exists: ${filePath}`);
          if (existing instanceof TFile) {
            await app.workspace.getLeaf().openFile(existing);
          }
          resolve();
          return;
        }

        try {
          const content = buildTemplate(name, layer);
          const file = await app.vault.create(filePath, content);
          await app.workspace.getLeaf().openFile(file);
          new Notice(`Created ${filePath}`);
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          new Notice(`Failed to create file: ${message}`, 5000);
        }

        resolve();
      });

      modal.open();
    });
  };

  if (projects.length === 1) {
    await createInProject(projects[0]);
  } else {
    // Multi-project: pick first
    const picker = new ProjectPickerModal(app, projects, async (project) => {
      await createInProject(project);
    });
    picker.open();
  }
}
