import { App, TFile, CachedMetadata } from 'obsidian';
import { execFile } from 'child_process';

import type { DiscoveryService, DiscoveredProject } from './discovery';

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
 * Connects to the Chronicler CLI to run sync/map operations
 * and reads component metadata from the vault.
 */
export class ChroniclerClient {
  private app: App;

  constructor(app: App) {
    this.app = app;
  }

  /**
   * Run `chronicler obsidian map` for each discovered project.
   */
  async syncAll(discovery: DiscoveryService): Promise<SyncResult> {
    const projects = discovery.getProjects();
    if (projects.length === 0) {
      return { success: true, filesUpdated: 0, message: 'No projects discovered' };
    }

    const vaultPath = (this.app.vault.adapter as { getBasePath?(): string }).getBasePath?.() ?? '';
    let totalUpdated = 0;
    const errors: string[] = [];

    for (const project of projects) {
      const projectDir = `${vaultPath}/${project.folderPath}`;
      const result = await this.runMap(projectDir);
      if (result.success) {
        totalUpdated += result.filesUpdated;
      } else {
        errors.push(`${project.projectName}: ${result.message}`);
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        filesUpdated: totalUpdated,
        message: errors.join('; '),
      };
    }

    return {
      success: true,
      filesUpdated: totalUpdated,
      message: `Generated maps for ${projects.length} project(s)`,
    };
  }

  /**
   * Runs `chronicler obsidian map --source <dir>` for a single project.
   */
  private runMap(sourceDir: string): Promise<SyncResult> {
    return new Promise((resolve) => {
      execFile(
        'chronicler',
        ['obsidian', 'map', '--source', sourceDir],
        { timeout: 60_000 },
        (error, stdout, stderr) => {
          if (error) {
            resolve({
              success: false,
              filesUpdated: 0,
              message: stderr?.trim() || error.message,
            });
            return;
          }

          const countMatch = stdout.match(/(\d+)\s+map/i);
          const filesUpdated = countMatch ? parseInt(countMatch[1], 10) : 1;

          resolve({
            success: true,
            filesUpdated,
            message: stdout.trim() || 'Map generated',
          });
        },
      );
    });
  }

  /**
   * Lists all .tech.md files across discovered projects.
   */
  getComponentList(discovery: DiscoveryService): string[] {
    const byProject = discovery.getAllTechFiles();
    const paths: string[] = [];
    for (const files of byProject.values()) {
      for (const f of files) {
        paths.push(f.path);
      }
    }
    return paths;
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

    const { position: _pos, ...frontmatter } = cache.frontmatter;
    return frontmatter as FrontMatter;
  }
}
