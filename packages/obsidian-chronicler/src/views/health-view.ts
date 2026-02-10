import { ItemView, TFile, WorkspaceLeaf } from 'obsidian';
import type ChroniclerPlugin from '../main';

export const HEALTH_VIEW_TYPE = 'chronicler-health-dashboard';

/** Staleness threshold in days */
const STALE_DAYS = 30;

/** Required frontmatter fields for a complete .tech.md */
const REQUIRED_FIELDS = ['component_id', 'layer', 'owner'] as const;

/** Recognized layer values and their display colors */
const LAYER_COLORS: Record<string, string> = {
  infrastructure: 'var(--color-blue)',
  logic: 'var(--color-green)',
  api: 'var(--color-orange)',
};

interface ComponentHealth {
  file: TFile;
  componentId: string;
  layer: string | null;
  verificationStatus: string | null;
  lastUpdated: Date | null;
  daysSinceUpdate: number | null;
  missingFields: string[];
  hasOutdatedFlag: boolean;
  isStale: boolean;
}

/**
 * Dashboard view showing documentation health metrics across all
 * .tech.md files in the configured chronicler folder.
 */
export class HealthDashboardView extends ItemView {
  plugin: ChroniclerPlugin;

  constructor(leaf: WorkspaceLeaf, plugin: ChroniclerPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType(): string {
    return HEALTH_VIEW_TYPE;
  }

  getDisplayText(): string {
    return 'Doc Health';
  }

  getIcon(): string {
    return 'heart-pulse';
  }

  async onOpen(): Promise<void> {
    this.contentEl.empty();
    this.contentEl.addClass('chronicler-health');

    await this.refresh();
  }

  async onClose(): Promise<void> {
    // Nothing to clean up
  }

  private async refresh(): Promise<void> {
    this.contentEl.empty();

    // Header with refresh button
    const headerRow = this.contentEl.createEl('div', { cls: 'chronicler-health-header' });
    headerRow.createEl('strong', { text: 'Documentation Health' });
    const refreshBtn = headerRow.createEl('button', {
      cls: 'chronicler-health-refresh clickable-icon',
      attr: { 'aria-label': 'Refresh' },
    });
    refreshBtn.createEl('span', { text: '\u21BB' }); // refresh arrow
    refreshBtn.addEventListener('click', () => this.refresh());

    const components = await this.scanComponents();

    if (components.length === 0) {
      this.contentEl.createEl('p', {
        text: 'No .tech.md files found in the chronicler folder.',
        cls: 'chronicler-health-empty',
      });
      return;
    }

    // Summary stats
    this.renderSummary(components);

    // Stale files
    const stale = components.filter((c) => c.isStale);
    if (stale.length > 0) {
      this.renderWarningSection(
        '\u26A0 Stale (>30d)',
        stale,
        (c) => c.daysSinceUpdate !== null ? `${c.daysSinceUpdate} days ago` : 'unknown date'
      );
    }

    // Missing fields
    const incomplete = components.filter((c) => c.missingFields.length > 0);
    if (incomplete.length > 0) {
      this.renderWarningSection(
        '\u26A0 Missing Fields',
        incomplete,
        (c) => `no ${c.missingFields.join(', ')}`
      );
    }

    // AI drafts (unverified)
    const drafts = components.filter((c) => c.verificationStatus === 'ai_draft');
    if (drafts.length > 0) {
      this.renderWarningSection(
        '\u26A0 AI Draft (unverified)',
        drafts,
        () => 'ai_draft'
      );
    }

    // Outdated flags
    const flagged = components.filter((c) => c.hasOutdatedFlag);
    if (flagged.length > 0) {
      this.renderWarningSection(
        '\u26A0 Flagged Outdated',
        flagged,
        () => '[FLAG:OUTDATED]'
      );
    }

    // By Layer grouping (graph view enhancement)
    if (this.plugin.settings.graphColorByLayer) {
      this.renderByLayer(components);
    }
  }

  private renderSummary(components: ComponentHealth[]): void {
    const total = components.length;
    const verified = components.filter(
      (c) => c.verificationStatus === 'human_verified'
    ).length;
    const healthy = components.filter(
      (c) =>
        !c.isStale &&
        c.missingFields.length === 0 &&
        !c.hasOutdatedFlag &&
        c.verificationStatus !== 'ai_draft'
    ).length;

    const summaryEl = this.contentEl.createEl('div', { cls: 'chronicler-health-summary' });

    // Coverage bar
    const coveragePct = Math.round((healthy / total) * 100);
    const coverageRow = summaryEl.createEl('div', { cls: 'chronicler-health-stat' });
    coverageRow.createEl('span', { text: 'Healthy: ' });
    coverageRow.createEl('span', {
      text: `${coveragePct}% (${healthy}/${total})`,
      cls: coveragePct >= 80 ? 'chronicler-health-ok' : 'chronicler-health-stale',
    });

    // Verification stat
    const verifiedPct = Math.round((verified / total) * 100);
    const verifiedRow = summaryEl.createEl('div', { cls: 'chronicler-health-stat' });
    verifiedRow.createEl('span', { text: 'Verified: ' });
    verifiedRow.createEl('span', {
      text: `${verifiedPct}% (${verified}/${total})`,
      cls: verifiedPct >= 60 ? 'chronicler-health-ok' : 'chronicler-health-stale',
    });
  }

  private renderWarningSection(
    title: string,
    components: ComponentHealth[],
    detailFn: (c: ComponentHealth) => string
  ): void {
    const section = this.contentEl.createEl('div', { cls: 'chronicler-health-section' });
    section.createEl('div', { text: title, cls: 'chronicler-health-section-title' });

    const list = section.createEl('ul', { cls: 'chronicler-health-list' });
    for (const comp of components) {
      const li = list.createEl('li', { cls: 'chronicler-health-item' });

      const link = li.createEl('span', {
        text: comp.componentId,
        cls: 'chronicler-health-link is-clickable',
      });
      link.addEventListener('click', () => {
        this.app.workspace.openLinkText(comp.file.path, '');
      });

      li.createEl('span', {
        text: ` (${detailFn(comp)})`,
        cls: 'chronicler-health-detail',
      });
    }
  }

  /**
   * Groups components by their `layer` frontmatter field and renders
   * color-coded sections. Meant to complement Obsidian's graph view
   * where users can filter by tag:#tech-doc.
   */
  private renderByLayer(components: ComponentHealth[]): void {
    const byLayer = new Map<string, ComponentHealth[]>();

    for (const comp of components) {
      const layer = comp.layer || 'unknown';
      const existing = byLayer.get(layer);
      if (existing) {
        existing.push(comp);
      } else {
        byLayer.set(layer, [comp]);
      }
    }

    const section = this.contentEl.createEl('div', { cls: 'chronicler-health-section' });
    section.createEl('div', {
      text: 'By Layer',
      cls: 'chronicler-health-section-title',
    });

    // Sort layers so known ones come first
    const knownLayers = Object.keys(LAYER_COLORS);
    const sortedLayers = [...byLayer.keys()].sort((a, b) => {
      const aIdx = knownLayers.indexOf(a);
      const bIdx = knownLayers.indexOf(b);
      if (aIdx >= 0 && bIdx >= 0) return aIdx - bIdx;
      if (aIdx >= 0) return -1;
      if (bIdx >= 0) return 1;
      return a.localeCompare(b);
    });

    for (const layer of sortedLayers) {
      const layerComps = byLayer.get(layer);
      if (!layerComps) continue;

      const layerEl = section.createEl('div', { cls: 'chronicler-health-layer' });

      // Color indicator dot
      const indicatorColor = LAYER_COLORS[layer] || 'var(--text-muted)';
      const indicator = layerEl.createEl('span', {
        cls: 'chronicler-health-layer-dot',
      });
      indicator.style.backgroundColor = indicatorColor;

      layerEl.createEl('span', {
        text: `${layer} (${layerComps.length})`,
        cls: 'chronicler-health-layer-name',
      });

      const layerList = layerEl.createEl('div', { cls: 'chronicler-health-layer-items' });
      for (const comp of layerComps) {
        const item = layerList.createEl('span', {
          text: comp.componentId,
          cls: 'chronicler-health-link is-clickable',
        });
        item.addEventListener('click', () => {
          this.app.workspace.openLinkText(comp.file.path, '');
        });
      }
    }

    // Hint about native graph filtering
    const hint = section.createEl('div', { cls: 'chronicler-health-hint' });
    hint.createEl('small', {
      text: 'Tip: Use tag:#tech-doc in Obsidian\'s graph filter to isolate documented components.',
    });
  }

  /**
   * Scan all markdown files in the chronicler folder, read frontmatter,
   * and build a health report for each component.
   */
  private async scanComponents(): Promise<ComponentHealth[]> {
    const folder = this.plugin.settings.chroniclerFolder;
    const allFiles = this.app.vault.getMarkdownFiles();
    const techFiles = allFiles.filter((f) =>
      f.path.startsWith(folder + '/') && f.path.endsWith('.tech.md')
    );

    const now = Date.now();
    const results: ComponentHealth[] = [];

    for (const file of techFiles) {
      const cache = this.app.metadataCache.getFileCache(file);
      const fm = cache?.frontmatter;

      const componentId =
        (fm?.['component_id'] as string) ||
        file.basename.replace('.tech', '');

      const layer = (fm?.['layer'] as string) || null;

      const verificationStatus =
        (fm?.['verification_status'] as string) || null;

      let lastUpdated: Date | null = null;
      let daysSinceUpdate: number | null = null;
      if (fm?.['last_updated']) {
        const parsed = new Date(String(fm['last_updated']));
        if (!isNaN(parsed.getTime())) {
          lastUpdated = parsed;
          daysSinceUpdate = Math.floor(
            (now - parsed.getTime()) / (1000 * 60 * 60 * 24)
          );
        }
      }

      const missingFields: string[] = [];
      for (const field of REQUIRED_FIELDS) {
        if (!fm?.[field]) {
          missingFields.push(field);
        }
      }

      // Check file content for [FLAG:OUTDATED] markers
      let hasOutdatedFlag = false;
      const content = await this.app.vault.cachedRead(file);
      if (content.includes('[FLAG:OUTDATED]')) {
        hasOutdatedFlag = true;
      }

      const isStale =
        daysSinceUpdate !== null && daysSinceUpdate > STALE_DAYS;

      results.push({
        file,
        componentId,
        layer,
        verificationStatus,
        lastUpdated,
        daysSinceUpdate,
        missingFields,
        hasOutdatedFlag,
        isStale,
      });
    }

    // Sort: worst health first (stale > flagged > missing fields > drafts > healthy)
    results.sort((a, b) => {
      const scoreA = this.healthScore(a);
      const scoreB = this.healthScore(b);
      return scoreA - scoreB;
    });

    return results;
  }

  /** Lower score = worse health, so they sort first */
  private healthScore(c: ComponentHealth): number {
    let score = 100;
    if (c.isStale) score -= 40;
    if (c.hasOutdatedFlag) score -= 30;
    if (c.missingFields.length > 0) score -= 20;
    if (c.verificationStatus === 'ai_draft') score -= 10;
    return score;
  }

  /**
   * Documents graph filtering approach.
   * The sync daemon injects #tech-doc tags into .tech.md files, so
   * Obsidian's native graph view can filter with `tag:#tech-doc`.
   * No custom graph rendering needed -- users just apply the filter.
   */
  static graphFilterHint(): string {
    return 'Use tag:#tech-doc in Obsidian graph filter to show only documented components.';
  }
}
