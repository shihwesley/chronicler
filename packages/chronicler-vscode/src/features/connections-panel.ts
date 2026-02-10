import * as vscode from 'vscode';
import * as path from 'path';
import { Workspace } from '../core/workspace';
import type { Connection } from '../core/types';

// Tree item variants for the connections panel hierarchy:
// SectionItem > FileItem > LinkDetailItem

export type ConnectionItem = SectionItem | FileItem | LinkDetailItem;

export class SectionItem extends vscode.TreeItem {
  readonly section: 'backlinks' | 'forwardLinks';
  readonly connections: Connection[];

  constructor(
    section: 'backlinks' | 'forwardLinks',
    connections: Connection[],
  ) {
    const label = section === 'backlinks' ? 'BACKLINKS' : 'FORWARD LINKS';
    super(`${label} (${connections.length})`, vscode.TreeItemCollapsibleState.Expanded);
    this.section = section;
    this.connections = connections;
    this.contextValue = 'section';
  }
}

export class FileItem extends vscode.TreeItem {
  readonly details: LinkDetailItem[];

  constructor(filePath: string, details: LinkDetailItem[]) {
    super(path.basename(filePath), vscode.TreeItemCollapsibleState.Collapsed);
    this.details = details;
    this.iconPath = new vscode.ThemeIcon('file');
    this.resourceUri = vscode.Uri.file(filePath);
    this.command = {
      command: 'vscode.open',
      arguments: [vscode.Uri.file(filePath)],
      title: 'Open',
    };
  }
}

export class LinkDetailItem extends vscode.TreeItem {
  constructor(connection: Connection) {
    // Display 1-indexed line number with the raw link text
    const label = `[line ${connection.link.lineNumber + 1}] ${connection.link.raw}`;
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('link');
    // Click navigates to the exact position of the link in the source file
    this.command = {
      command: 'vscode.open',
      arguments: [
        vscode.Uri.file(connection.sourceUri),
        {
          selection: new vscode.Range(
            connection.link.lineNumber,
            connection.link.startChar,
            connection.link.lineNumber,
            connection.link.endChar,
          ),
        },
      ],
      title: 'Go to Link',
    };
  }
}

export class ConnectionsProvider implements vscode.TreeDataProvider<ConnectionItem> {
  private _onDidChange = new vscode.EventEmitter<ConnectionItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  private workspace: Workspace;
  private currentDoc: { componentId: string; uri: string } | undefined;
  private disposables: vscode.Disposable[] = [];

  constructor(workspace: Workspace) {
    this.workspace = workspace;

    // Track the active editor so we always show links for the open .tech.md
    this.disposables.push(
      vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor && editor.document.fileName.endsWith('.tech.md')) {
          const doc = workspace.getDoc(editor.document.uri.fsPath);
          if (doc) {
            this.currentDoc = { componentId: doc.componentId, uri: doc.uri };
            this._onDidChange.fire();
          }
        }
      }),
    );

    // Seed from whatever is open right now
    const active = vscode.window.activeTextEditor;
    if (active && active.document.fileName.endsWith('.tech.md')) {
      const doc = workspace.getDoc(active.document.uri.fsPath);
      if (doc) {
        this.currentDoc = { componentId: doc.componentId, uri: doc.uri };
      }
    }
  }

  refresh(): void {
    this._onDidChange.fire();
  }

  dispose(): void {
    for (const d of this.disposables) {
      d.dispose();
    }
    this._onDidChange.dispose();
  }

  getTreeItem(element: ConnectionItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: ConnectionItem): ConnectionItem[] {
    if (!this.currentDoc) {
      return [];
    }

    const resolver = this.workspace.getLinkResolver();

    // Root level: two section headers
    if (!element) {
      const backlinks = resolver.getBacklinks(this.currentDoc.componentId);
      const forwardLinks = resolver.getForwardLinks(this.currentDoc.componentId);
      return [
        new SectionItem('backlinks', backlinks),
        new SectionItem('forwardLinks', forwardLinks),
      ];
    }

    // Section level: group connections by the "other" file
    if (element instanceof SectionItem) {
      const grouped = new Map<string, Connection[]>();
      for (const conn of element.connections) {
        const key = element.section === 'backlinks' ? conn.sourceUri : conn.targetUri;
        if (!grouped.has(key)) {
          grouped.set(key, []);
        }
        grouped.get(key)!.push(conn);
      }

      return Array.from(grouped.entries()).map(([filePath, conns]) => {
        const details = conns.map((c) => new LinkDetailItem(c));
        return new FileItem(filePath, details);
      });
    }

    // File level: show individual link details
    if (element instanceof FileItem) {
      return element.details;
    }

    return [];
  }
}
