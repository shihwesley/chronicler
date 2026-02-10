import * as vscode from 'vscode';
import * as path from 'path';
import { Workspace } from '../core/workspace';
import type { TechDoc } from '../core/types';

// Tree item variants: TagItem (root) > TagDocItem (leaf)

export type TagTreeItem = TagItem | TagDocItem;

export class TagItem extends vscode.TreeItem {
  readonly tag: string;
  readonly docs: TechDoc[];

  constructor(tag: string, docs: TechDoc[]) {
    super(`${tag} (${docs.length})`, vscode.TreeItemCollapsibleState.Collapsed);
    this.tag = tag;
    this.docs = docs;
    this.contextValue = 'tag';
    this.iconPath = new vscode.ThemeIcon('tag');
  }
}

export class TagDocItem extends vscode.TreeItem {
  constructor(doc: TechDoc) {
    super(path.basename(doc.uri), vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon('file');
    this.resourceUri = vscode.Uri.file(doc.uri);
    this.command = {
      command: 'vscode.open',
      arguments: [vscode.Uri.file(doc.uri)],
      title: 'Open',
    };
  }
}

export class TagsProvider implements vscode.TreeDataProvider<TagTreeItem> {
  private _onDidChange = new vscode.EventEmitter<TagTreeItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  private workspace: Workspace;

  constructor(workspace: Workspace) {
    this.workspace = workspace;
  }

  refresh(): void {
    this._onDidChange.fire();
  }

  dispose(): void {
    this._onDidChange.dispose();
  }

  getTreeItem(element: TagTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: TagTreeItem): TagTreeItem[] {
    // Root: build a tag -> docs[] map from every loaded document
    if (!element) {
      const tagMap = new Map<string, TechDoc[]>();

      for (const doc of this.workspace.getAllDocs()) {
        for (const tag of doc.tags) {
          if (!tagMap.has(tag)) {
            tagMap.set(tag, []);
          }
          tagMap.get(tag)!.push(doc);
        }
      }

      // Sort tags alphabetically
      const sorted = Array.from(tagMap.entries()).sort((a, b) =>
        a[0].localeCompare(b[0]),
      );

      return sorted.map(([tag, docs]) => new TagItem(tag, docs));
    }

    // Tag children: return a file item for each doc
    if (element instanceof TagItem) {
      return element.docs.map((doc) => new TagDocItem(doc));
    }

    return [];
  }
}
