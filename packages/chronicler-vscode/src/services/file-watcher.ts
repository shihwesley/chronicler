// Bridges VS Code's FileSystemWatcher with the core Workspace index.
// Debounces rapid file changes to avoid thrashing the parser.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

export class FileWatcherService implements vscode.Disposable {
  private watcher: vscode.FileSystemWatcher;
  private workspace: Workspace;
  private debounceTimer: NodeJS.Timeout | undefined;

  constructor(workspace: Workspace, glob: string) {
    this.workspace = workspace;
    this.watcher = vscode.workspace.createFileSystemWatcher(glob);

    this.watcher.onDidCreate(uri => this.onFileEvent(uri));
    this.watcher.onDidChange(uri => this.onFileEvent(uri));
    this.watcher.onDidDelete(uri => this.onDelete(uri));
  }

  private onFileEvent(uri: vscode.Uri): void {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(async () => {
      try {
        const doc = await vscode.workspace.openTextDocument(uri);
        this.workspace.onFileChanged(uri.fsPath, doc.getText());
      } catch {
        // File might have been deleted between event and read
      }
    }, 500);
  }

  private onDelete(uri: vscode.Uri): void {
    this.workspace.onFileDeleted(uri.fsPath);
  }

  dispose(): void {
    this.watcher.dispose();
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
  }
}
