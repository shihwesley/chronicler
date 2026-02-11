import { App, TFile, TFolder, TAbstractFile, EventRef } from 'obsidian';
import type { DiscoveryService, DiscoveredProject } from './discovery';

type FileChangeCallback = (file: TFile, project: DiscoveredProject) => void;

/**
 * Watches for .tech.md file changes inside any discovered project folder.
 * Debounces rapid changes and notifies registered callbacks.
 * Also triggers discovery rescan on folder create/delete.
 */
export class VaultWatcher {
  private app: App;
  private discovery: DiscoveryService;
  private callbacks: FileChangeCallback[] = [];
  private eventRefs: EventRef[] = [];
  private debounceTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();

  private static readonly DEBOUNCE_MS = 100;

  constructor(app: App, discovery: DiscoveryService) {
    this.app = app;
    this.discovery = discovery;
  }

  /**
   * Registers vault events filtered to discovered chronicler folders.
   */
  start(): void {
    this.stop();

    const handleFile = (file: TAbstractFile) => {
      if (file instanceof TFile && this.isWatchedFile(file)) {
        const project = this.discovery.getProjectForFile(file.path);
        if (project) this.debouncedNotify(file, project);
      }
    };

    const handleRename = (file: TAbstractFile, _oldPath: string) => {
      if (file instanceof TFile && this.isWatchedFile(file)) {
        const project = this.discovery.getProjectForFile(file.path);
        if (project) this.debouncedNotify(file, project);
      }
    };

    const handleFolderChange = (file: TAbstractFile) => {
      if (file instanceof TFolder) {
        this.discovery.rescan();
      }
    };

    this.eventRefs.push(
      this.app.vault.on('create', (f) => { handleFile(f); handleFolderChange(f); }),
      this.app.vault.on('modify', handleFile),
      this.app.vault.on('delete', (f) => { handleFile(f); handleFolderChange(f); }),
      this.app.vault.on('rename', handleRename),
    );
  }

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

  onFileChange(callback: FileChangeCallback): void {
    this.callbacks.push(callback);
  }

  private isWatchedFile(file: TFile): boolean {
    return (
      this.discovery.getProjectForFile(file.path) !== null &&
      file.path.endsWith('.tech.md')
    );
  }

  private debouncedNotify(file: TFile, project: DiscoveredProject): void {
    const existing = this.debounceTimers.get(file.path);
    if (existing) {
      clearTimeout(existing);
    }

    const timer = setTimeout(() => {
      this.debounceTimers.delete(file.path);
      for (const cb of this.callbacks) {
        cb(file, project);
      }
    }, VaultWatcher.DEBOUNCE_MS);

    this.debounceTimers.set(file.path, timer);
  }
}
