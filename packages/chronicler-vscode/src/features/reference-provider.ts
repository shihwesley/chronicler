// Find All References (backlinks) for .tech.md components.
// Shows every document that links to the current file's component.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

export class TechDocReferenceProvider implements vscode.ReferenceProvider {
  private workspace: Workspace;

  constructor(workspace: Workspace) {
    this.workspace = workspace;
  }

  async provideReferences(
    doc: vscode.TextDocument,
    _pos: vscode.Position,
    _context: vscode.ReferenceContext,
    _token: vscode.CancellationToken
  ): Promise<vscode.Location[] | null> {
    if (!doc.uri.fsPath.endsWith('.tech.md')) {
      return null;
    }

    const techDoc = this.workspace.getDoc(doc.uri.fsPath);
    if (!techDoc || !techDoc.componentId) {
      return null;
    }

    const resolver = this.workspace.getLinkResolver();
    const backlinks = resolver.getBacklinks(techDoc.componentId);

    if (backlinks.length === 0) {
      return null;
    }

    const locations: vscode.Location[] = [];
    for (const connection of backlinks) {
      const uri = vscode.Uri.file(connection.sourceUri);
      const range = new vscode.Range(
        connection.link.lineNumber,
        connection.link.startChar,
        connection.link.lineNumber,
        connection.link.endChar
      );
      locations.push(new vscode.Location(uri, range));
    }

    return locations;
  }
}
