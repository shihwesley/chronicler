import { App, TFile, CachedMetadata } from 'obsidian';
import { execFile } from 'child_process';

import { ChroniclerSettings } from '../settings';

export interface SyncResult {
  success: boolean;
  filesUpdated: number;
  message: string;
}

export interface FrontMatter {
  component_id?: string;
  layer?: string;
  owner?: string;
  tags?: string[];
  verification_status?: string;
  last_updated?: string;
  depends_on?: string[];
  [key: string]: unknown;
}

/**
 * Connects to the Chronicler CLI to run sync operations
 * and reads component metadata from the vault.
 */
export class ChroniclerClient {
  private app: App;
  private settings: ChroniclerSettings;

  constructor(app: App, settings: ChroniclerSettings) {
    this.app = app;
    this.settings = settings;
  }

  /**
   * Runs `chronicler obsidian export` via shell.
   * Obsidian is Electron, so Node child_process is available.
   */
  sync(): Promise<SyncResult> {
    const vaultPath = (this.app.vault.adapter as { getBasePath?(): string }).getBasePath?.() ?? '';
    const targetDir = `${vaultPath}/${this.settings.chroniclerFolder}`;

    return new Promise((resolve) => {
      execFile('chronicler', ['obsidian', 'export', '--vault', targetDir], { timeout: 60_000 }, (error, stdout, stderr) => {
        if (error) {
          resolve({
            success: false,
            filesUpdated: 0,
            message: stderr?.trim() || error.message,
          });
          return;
        }

        // Try to parse a count from stdout (e.g. "Exported 12 files")
        const countMatch = stdout.match(/(\d+)\s+file/i);
        const filesUpdated = countMatch ? parseInt(countMatch[1], 10) : 0;

        resolve({
          success: true,
          filesUpdated,
          message: stdout.trim() || 'Sync completed',
        });
      });
    });
  }

  /**
   * Lists all .md files inside the chronicler folder.
   */
  getComponentList(): Promise<string[]> {
    const folder = this.settings.chroniclerFolder;
    const files = this.app.vault.getFiles();
    const components = files
      .filter((f) => f.path.startsWith(folder + '/') && f.extension === 'md')
      .map((f) => f.path);

    return Promise.resolve(components);
  }

  /**
   * Reads frontmatter for a given component file using Obsidian's MetadataCache.
   */
  getComponentMetadata(componentPath: string): FrontMatter | null {
    const file = this.app.vault.getAbstractFileByPath(componentPath);
    if (!(file instanceof TFile)) {
      return null;
    }

    const cache: CachedMetadata | null = this.app.metadataCache.getFileCache(file);
    if (!cache?.frontmatter) {
      return null;
    }

    // Strip Obsidian's internal position field
    const { position: _pos, ...frontmatter } = cache.frontmatter;
    return frontmatter as FrontMatter;
  }
}
