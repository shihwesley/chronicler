import { Plugin } from 'obsidian';

import { DEPENDENCY_VIEW_TYPE } from '../views/dependency-view';
import { HEALTH_VIEW_TYPE } from '../views/health-view';
import { syncVault } from './sync-command';
import { createTechDoc } from './create-tech-md';
import { browseByLayer } from './browse-graph';

import type ChroniclerPlugin from '../main';

/**
 * Registers all Chronicler commands in the command palette.
 */
export class ChroniclerCommands {
  registerAll(plugin: Plugin): void {
    const chronicler = plugin as ChroniclerPlugin;

    plugin.addCommand({
      id: 'chronicler-sync',
      name: 'Chronicler: Sync Now',
      callback: () => {
        syncVault(plugin.app, chronicler.discovery);
      },
    });

    plugin.addCommand({
      id: 'chronicler-create',
      name: 'Chronicler: Create .tech.md',
      callback: () => {
        createTechDoc(plugin.app, chronicler.discovery);
      },
    });

    plugin.addCommand({
      id: 'chronicler-show-deps',
      name: 'Chronicler: Show Dependencies',
      callback: () => {
        activateView(plugin, DEPENDENCY_VIEW_TYPE);
      },
    });

    plugin.addCommand({
      id: 'chronicler-health',
      name: 'Chronicler: Check Health',
      callback: () => {
        activateView(plugin, HEALTH_VIEW_TYPE);
      },
    });

    plugin.addCommand({
      id: 'chronicler-browse-layer',
      name: 'Chronicler: Browse by Layer',
      callback: () => {
        browseByLayer(plugin.app, chronicler.discovery);
      },
    });
  }
}

/**
 * Opens or focuses a view in the right sidebar.
 * If the view is already open, it gets revealed instead of duplicated.
 */
async function activateView(plugin: Plugin, viewType: string): Promise<void> {
  const { workspace } = plugin.app;

  // If a leaf with this view already exists, reveal it
  const existing = workspace.getLeavesOfType(viewType);
  if (existing.length > 0) {
    workspace.revealLeaf(existing[0]);
    return;
  }

  // Otherwise open in the right sidebar
  const leaf = workspace.getRightLeaf(false);
  if (leaf) {
    await leaf.setViewState({ type: viewType, active: true });
    workspace.revealLeaf(leaf);
  }
}
