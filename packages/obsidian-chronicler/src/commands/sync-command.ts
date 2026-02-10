import { App, Notice } from 'obsidian';

import { ChroniclerSettings } from '../settings';
import { ChroniclerClient } from '../services/chronicler-client';

/**
 * Triggers a Chronicler sync via CLI and reports the result.
 */
export async function syncVault(app: App, settings: ChroniclerSettings): Promise<void> {
  const client = new ChroniclerClient(app, settings);

  new Notice('Chronicler: Syncing...');

  try {
    const result = await client.sync();

    if (result.success) {
      new Notice(`Chronicler: Sync complete — ${result.filesUpdated} file(s) updated`);
    } else {
      new Notice(`Chronicler: Sync failed — ${result.message}`, 5000);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    new Notice(`Chronicler: Sync error — ${message}`, 5000);
  }
}
