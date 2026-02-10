import { App, FuzzySuggestModal, TFile, Notice } from 'obsidian';

import { ChroniclerSettings } from '../settings';
import { ChroniclerClient, FrontMatter } from '../services/chronicler-client';

const LAYERS = ['infrastructure', 'logic', 'api', 'data', 'external'] as const;

/**
 * First modal: pick a layer from the predefined list.
 */
class LayerPickerModal extends FuzzySuggestModal<string> {
  private onChoose: (layer: string) => void;

  constructor(app: App, onChoose: (layer: string) => void) {
    super(app);
    this.onChoose = onChoose;
    this.setPlaceholder('Pick a layer...');
  }

  getItems(): string[] {
    return [...LAYERS];
  }

  getItemText(item: string): string {
    return item;
  }

  onChooseItem(item: string): void {
    this.onChoose(item);
  }
}

/**
 * Second modal: shows components that belong to the selected layer.
 */
class ComponentPickerModal extends FuzzySuggestModal<string> {
  private components: string[];
  private onChoose: (path: string) => void;

  constructor(app: App, components: string[], onChoose: (path: string) => void) {
    super(app);
    this.components = components;
    this.onChoose = onChoose;
    this.setPlaceholder('Pick a component...');
  }

  getItems(): string[] {
    return this.components;
  }

  getItemText(item: string): string {
    // Show just the filename without the folder prefix
    const parts = item.split('/');
    return parts[parts.length - 1].replace(/\.tech\.md$/, '').replace(/\.md$/, '');
  }

  onChooseItem(item: string): void {
    this.onChoose(item);
  }
}

/**
 * Browse components by layer. Shows a layer picker, then a list of
 * components in that layer, then opens the selected file.
 */
export async function browseByLayer(app: App, settings: ChroniclerSettings): Promise<void> {
  const client = new ChroniclerClient(app, settings);

  return new Promise((resolve) => {
    const layerModal = new LayerPickerModal(app, async (layer) => {
      const allPaths = await client.getComponentList();

      // Filter to components whose frontmatter layer matches
      const matching = allPaths.filter((path) => {
        const meta: FrontMatter | null = client.getComponentMetadata(path);
        return meta?.layer === layer;
      });

      if (matching.length === 0) {
        new Notice(`No components found in layer: ${layer}`);
        resolve();
        return;
      }

      const componentModal = new ComponentPickerModal(app, matching, async (path) => {
        const file = app.vault.getAbstractFileByPath(path);
        if (file instanceof TFile) {
          await app.workspace.getLeaf().openFile(file);
        }
        resolve();
      });

      componentModal.open();
    });

    layerModal.open();
  });
}
