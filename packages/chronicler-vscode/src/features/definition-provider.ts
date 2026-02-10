// F12 / Go to Definition for agent:// URIs and [[wiki-links]] in .tech.md files.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

const AGENT_URI_PATTERN = /agent:\/\/[^\s)>\]]+/;
const WIKI_LINK_PATTERN = /\[\[([^\]]+)\]\]/;

export class TechDocDefinitionProvider implements vscode.DefinitionProvider {
  private workspace: Workspace;

  constructor(workspace: Workspace) {
    this.workspace = workspace;
  }

  async provideDefinition(
    doc: vscode.TextDocument,
    pos: vscode.Position,
    _token: vscode.CancellationToken
  ): Promise<vscode.DefinitionLink[] | null> {
    if (!doc.uri.fsPath.endsWith('.tech.md')) {
      return null;
    }

    const resolver = this.workspace.getLinkResolver();

    // Check for [[wiki-link]] under cursor
    const wikiRange = doc.getWordRangeAtPosition(pos, WIKI_LINK_PATTERN);
    if (wikiRange) {
      const linkText = doc.getText(wikiRange);
      const inner = linkText.replace(/^\[\[|\]\]$/g, '');
      const [componentId, heading] = inner.split('#');

      const resolved = resolver.resolveWikiLink(componentId);
      if (!resolved) return null;

      const targetUri = vscode.Uri.file(resolved);
      const targetRange = heading
        ? await this.findHeadingRange(targetUri, heading)
        : new vscode.Range(0, 0, 0, 0);

      return [{
        originSelectionRange: wikiRange,
        targetUri,
        targetRange,
      }];
    }

    // Check for agent:// URI under cursor
    const agentRange = doc.getWordRangeAtPosition(pos, AGENT_URI_PATTERN);
    if (agentRange) {
      const uriText = doc.getText(agentRange);
      const resolved = resolver.resolveAgentUri(uriText);
      if (!resolved) return null;

      const targetUri = vscode.Uri.file(resolved);

      // Extract heading from agent://component/heading
      const withoutScheme = uriText.replace(/^agent:\/\//, '');
      const slashIdx = withoutScheme.indexOf('/');
      const heading = slashIdx !== -1 ? withoutScheme.slice(slashIdx + 1) : null;

      const targetRange = heading
        ? await this.findHeadingRange(targetUri, heading)
        : new vscode.Range(0, 0, 0, 0);

      return [{
        originSelectionRange: agentRange,
        targetUri,
        targetRange,
      }];
    }

    return null;
  }

  /**
   * Search a file for a markdown heading and return its range.
   * Falls back to line 0 if the heading isn't found.
   */
  private async findHeadingRange(
    uri: vscode.Uri,
    heading: string
  ): Promise<vscode.Range> {
    try {
      const targetDoc = await vscode.workspace.openTextDocument(uri);
      const normalizedTarget = heading.toLowerCase().replace(/-/g, ' ');

      for (let i = 0; i < targetDoc.lineCount; i++) {
        const line = targetDoc.lineAt(i).text;
        const match = line.match(/^#{1,6}\s+(.+)/);
        if (match) {
          const sectionTitle = match[1].trim().toLowerCase().replace(/-/g, ' ');
          if (sectionTitle === normalizedTarget) {
            return new vscode.Range(i, 0, i, line.length);
          }
        }
      }
    } catch {
      // File might not exist yet
    }

    return new vscode.Range(0, 0, 0, 0);
  }
}
