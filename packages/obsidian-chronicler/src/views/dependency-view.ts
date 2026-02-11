import { ItemView, TFile, WorkspaceLeaf } from 'obsidian';
import type ChroniclerPlugin from '../main';

export const DEPENDENCY_VIEW_TYPE = 'chronicler-dependency-explorer';

interface DepNode {
  id: string;
  file: TFile | null;
  depth: number;
  isCircular: boolean;
}

/**
 * Sidebar panel showing dependency relationships for the active .tech.md file.
 * Reads depends_on, depended_by, and connectivity_graph from frontmatter.
 */
export class DependencyExplorerView extends ItemView {
  plugin: ChroniclerPlugin;

  constructor(leaf: WorkspaceLeaf, plugin: ChroniclerPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType(): string {
    return DEPENDENCY_VIEW_TYPE;
  }

  getDisplayText(): string {
    return 'Dependencies';
  }

  getIcon(): string {
    return 'git-branch';
  }

  async onOpen(): Promise<void> {
    this.contentEl.empty();
    this.contentEl.addClass('chronicler-dep-tree');

    this.registerEvent(
      this.app.workspace.on('active-leaf-change', () => {
        this.refresh();
      })
    );

    await this.refresh();
  }

  async onClose(): Promise<void> {
    // Event listeners cleaned up automatically via registerEvent
  }

  private async refresh(): Promise<void> {
    this.contentEl.empty();

    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile || !activeFile.path.endsWith('.tech.md')) {
      this.renderEmpty('Open a .tech.md file to see dependencies.');
      return;
    }

    const cache = this.app.metadataCache.getFileCache(activeFile);
    const fm = cache?.frontmatter;
    if (!fm) {
      this.renderEmpty('No frontmatter found in this file.');
      return;
    }

    const componentId = (fm['component_id'] as string) || activeFile.basename.replace('.tech', '');
    const dependsOn = this.extractIds(fm['depends_on']);
    const dependedBy = this.extractIds(fm['depended_by']);
    const graphEdges = this.extractGraphEdges(fm['connectivity_graph']);

    // Merge graph edges into depends_on/depended_by
    for (const edge of graphEdges) {
      if (edge.from === componentId && !dependsOn.includes(edge.to)) {
        dependsOn.push(edge.to);
      }
      if (edge.to === componentId && !dependedBy.includes(edge.from)) {
        dependedBy.push(edge.from);
      }
    }

    // Build the header
    const header = this.contentEl.createEl('div', { cls: 'chronicler-dep-header' });
    header.createEl('strong', { text: componentId });
    header.createEl('span', { text: ' (current)', cls: 'chronicler-dep-current-label' });

    // Check for circular deps (component appears in both lists)
    const circular = new Set<string>();
    for (const id of dependsOn) {
      if (dependedBy.includes(id)) {
        circular.add(id);
      }
    }

    // Build "Depends On" section
    this.renderSection(
      'Depends On',
      dependsOn,
      circular,
      1
    );

    // Build "Depended By" section
    this.renderSection(
      'Depended By',
      dependedBy,
      circular,
      1
    );

    if (dependsOn.length === 0 && dependedBy.length === 0) {
      this.contentEl.createEl('p', {
        text: 'No dependencies found in frontmatter.',
        cls: 'chronicler-dep-empty',
      });
    }
  }

  private renderEmpty(message: string): void {
    this.contentEl.createEl('p', {
      text: message,
      cls: 'chronicler-dep-empty',
    });
  }

  private renderSection(
    title: string,
    ids: string[],
    circular: Set<string>,
    depth: number
  ): void {
    if (ids.length === 0) return;

    const section = this.contentEl.createEl('div', { cls: 'chronicler-dep-section' });
    const toggle = section.createEl('div', { cls: 'tree-item-self is-clickable' });
    const collapseIcon = toggle.createEl('span', { cls: 'tree-item-icon collapse-icon' });
    collapseIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';
    toggle.createEl('span', { text: title, cls: 'tree-item-inner' });
    toggle.createEl('span', {
      text: String(ids.length),
      cls: 'tree-item-flair',
    });

    const childContainer = section.createEl('div', { cls: 'tree-item-children' });

    for (const id of ids) {
      this.renderNode(childContainer, {
        id,
        file: this.resolveFile(id),
        depth,
        isCircular: circular.has(id),
      });
    }

    // Toggle collapse on click
    let collapsed = false;
    toggle.addEventListener('click', () => {
      collapsed = !collapsed;
      childContainer.toggleClass('is-collapsed', collapsed);
      collapseIcon.toggleClass('is-collapsed', collapsed);
    });
  }

  private renderNode(parent: Element, node: DepNode): void {
    const item = parent.createEl('div', { cls: 'tree-item-self is-clickable' });

    // Depth indicator
    if (node.depth > 0) {
      item.createEl('span', {
        text: `${'  '.repeat(node.depth)}`,
        cls: 'chronicler-dep-indent',
      });
    }

    // Warning icon for circular deps
    if (node.isCircular) {
      const warn = item.createEl('span', {
        cls: 'chronicler-dep-circular',
        attr: { 'aria-label': 'Circular dependency' },
      });
      warn.createEl('span', { text: '\u26A0 ' }); // warning triangle
    }

    // Component name (clickable if file exists)
    const nameEl = item.createEl('span', {
      text: node.id,
      cls: 'chronicler-dep-name',
    });

    // Depth badge
    if (node.depth > 0) {
      item.createEl('span', {
        text: `${node.depth} hop${node.depth > 1 ? 's' : ''}`,
        cls: 'chronicler-dep-depth-badge',
      });
    }

    if (node.file) {
      nameEl.addClass('is-clickable');
      item.addEventListener('click', () => {
        if (node.file) {
          this.app.workspace.openLinkText(node.file.path, '');
        }
      });
    } else {
      nameEl.addClass('chronicler-dep-missing');
      item.createEl('span', {
        text: '(not found)',
        cls: 'chronicler-dep-not-found',
      });
    }
  }

  /**
   * Find the .tech.md file for a given component ID across all projects.
   * Uses DiscoveryService with context from the active file for same-project preference.
   */
  private resolveFile(componentId: string): TFile | null {
    const activeFile = this.app.workspace.getActiveFile();
    const contextPath = activeFile?.path;
    const matches = this.plugin.discovery.resolveComponent(componentId, contextPath);
    if (matches.length > 0) {
      return matches[0];
    }

    // Fallback: search all markdown files for matching component_id in frontmatter
    const allFiles = this.app.vault.getMarkdownFiles();
    for (const file of allFiles) {
      const cache = this.app.metadataCache.getFileCache(file);
      if (cache?.frontmatter?.['component_id'] === componentId) {
        return file;
      }
    }

    return null;
  }

  private extractIds(value: unknown): string[] {
    if (Array.isArray(value)) {
      return value.filter((v): v is string => typeof v === 'string');
    }
    if (typeof value === 'string') {
      return value.split(',').map((s) => s.trim()).filter(Boolean);
    }
    return [];
  }

  /**
   * Parse connectivity_graph frontmatter, which can be an array of
   * { from, to } objects or an array of "from -> to" strings.
   */
  private extractGraphEdges(
    value: unknown
  ): Array<{ from: string; to: string }> {
    if (!Array.isArray(value)) return [];

    const edges: Array<{ from: string; to: string }> = [];
    for (const item of value) {
      if (
        typeof item === 'object' &&
        item !== null &&
        'from' in item &&
        'to' in item
      ) {
        edges.push({
          from: String(item.from),
          to: String(item.to),
        });
      } else if (typeof item === 'string') {
        const match = item.match(/^(.+?)\s*->\s*(.+)$/);
        if (match) {
          edges.push({ from: match[1].trim(), to: match[2].trim() });
        }
      }
    }
    return edges;
  }
}
