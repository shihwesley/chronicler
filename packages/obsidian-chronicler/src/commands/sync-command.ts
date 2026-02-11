import { App, Notice } from 'obsidian';

import { ChroniclerClient } from '../services/chronicler-client';
import type { DiscoveryService } from '../services/discovery';

/**
 * Generates _map.md files for all discovered projects via CLI.
 */
export async function syncVault(app: App, discovery: DiscoveryService): Promise<void> {
  const client = new ChroniclerClient(app);

  new Notice('Chronicler: Generating maps...');

  try {
    const result = await client.syncAll(discovery);

    if (result.success) {
      new Notice(`Chronicler: Maps generated — ${result.filesUpdated} project(s)`);
    } else {
      new Notice(`Chronicler: Map generation failed — ${result.message}`, 5000);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    new Notice(`Chronicler: Sync error — ${message}`, 5000);
  }
}
