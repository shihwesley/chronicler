// Autocomplete for [[wiki-links]] and agent:// URIs in .tech.md files.
// Trigger character: '[' (registered in extension.ts).

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

export class WikiLinkCompletionProvider implements vscode.CompletionItemProvider {
  private workspace: Workspace;

  constructor(workspace: Workspace) {
    this.workspace = workspace;
  }

  provideCompletionItems(
    doc: vscode.TextDocument,
    pos: vscode.Position,
    _token: vscode.CancellationToken,
    _context: vscode.CompletionContext
  ): vscode.CompletionItem[] | null {
    if (!doc.uri.fsPath.endsWith('.tech.md')) {
      return null;
    }

    const lineText = doc.lineAt(pos).text.substring(0, pos.character);

    // Wiki-link context: cursor right after `[[`
    const isWikiLink = lineText.endsWith('[[') || /\[\[[^\]]*$/.test(lineText);

    // Agent URI context: cursor after `agent://`
    const isAgentUri = /agent:\/\/[^\s)>\]]*$/.test(lineText);

    if (!isWikiLink && !isAgentUri) {
      return null;
    }

    const allDocs = this.workspace.getAllDocs();
    const items: vscode.CompletionItem[] = [];

    for (const techDoc of allDocs) {
      if (!techDoc.componentId) continue;

      const item = new vscode.CompletionItem(
        techDoc.componentId,
        vscode.CompletionItemKind.Reference
      );

      // Metadata shown in the completion detail pane
      const detailParts: string[] = [];
      if (techDoc.layer) detailParts.push(techDoc.layer);
      if (techDoc.version) detailParts.push(`v${techDoc.version}`);
      item.detail = detailParts.join(' | ') || undefined;

      // Documentation popup
      const docParts: string[] = [];
      if (techDoc.ownerTeam) docParts.push(`Owner: ${techDoc.ownerTeam}`);
      if (techDoc.tags.length > 0) docParts.push(`Tags: ${techDoc.tags.join(', ')}`);
      if (docParts.length > 0) {
        item.documentation = new vscode.MarkdownString(docParts.join('  \n'));
      }

      if (isWikiLink) {
        // Insert the component ID and close the brackets
        item.insertText = `${techDoc.componentId}]]`;
      } else {
        // For agent:// context, insert the full URI path
        item.insertText = `${techDoc.componentId}/${techDoc.componentId}.tech.md`;
      }

      items.push(item);
    }

    return items;
  }
}
