import { App, TFile, TAbstractFile, EventRef } from 'obsidian';

type FileChangeCallback = (file: TFile) => void;

/**
 * Watches for .tech.md file changes inside the chronicler folder.
 * Debounces rapid changes and notifies registered callbacks.
 */
export class VaultWatcher {
  private app: App;
  private chroniclerFolder: string;
  private callbacks: FileChangeCallback[] = [];
  private eventRefs: EventRef[] = [];
  private debounceTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();

  private static readonly DEBOUNCE_MS = 100;

  constructor(app: App, chroniclerFolder: string) {
    this.app = app;
    this.chroniclerFolder = chroniclerFolder;
  }

  /**
   * Registers vault events filtered to the chronicler folder.
   */
  start(): void {
    // Stop any existing watchers first to avoid duplicates
    this.stop();

    const handleFile = (file: TAbstractFile) => {
      if (file instanceof TFile && this.isWatchedFile(file)) {
        this.debouncedNotify(file);
      }
    };

    const handleRename = (file: TAbstractFile, _oldPath: string) => {
      if (file instanceof TFile && this.isWatchedFile(file)) {
        this.debouncedNotify(file);
      }
    };

    this.eventRefs.push(
      this.app.vault.on('create', handleFile),
      this.app.vault.on('modify', handleFile),
      this.app.vault.on('delete', handleFile),
      this.app.vault.on('rename', handleRename),
    );
  }

  /**
   * Unregisters all vault event listeners and clears pending debounce timers.
   */
  stop(): void {
    for (const ref of this.eventRefs) {
      this.app.vault.offref(ref);
    }
    this.eventRefs = [];

    for (const timer of this.debounceTimers.values()) {
      clearTimeout(timer);
    }
    this.debounceTimers.clear();
  }

  /**
   * Registers a callback that fires when a watched .tech.md file changes.
   */
  onFileChange(callback: FileChangeCallback): void {
    this.callbacks.push(callback);
  }

  private isWatchedFile(file: TFile): boolean {
    return (
      file.path.startsWith(this.chroniclerFolder + '/') &&
      file.path.endsWith('.tech.md')
    );
  }

  private debouncedNotify(file: TFile): void {
    const existing = this.debounceTimers.get(file.path);
    if (existing) {
      clearTimeout(existing);
    }

    const timer = setTimeout(() => {
      this.debounceTimers.delete(file.path);
      for (const cb of this.callbacks) {
        cb(file);
      }
    }, VaultWatcher.DEBOUNCE_MS);

    this.debounceTimers.set(file.path, timer);
  }
}
