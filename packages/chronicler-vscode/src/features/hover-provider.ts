// Shows hover previews for [[wiki-links]] and agent:// URIs in .tech.md files.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/;
const AGENT_URI_RE = /agent:\/\/[^\s)>\]]+/;

export class TechDocHoverProvider implements vscode.HoverProvider {
  private workspace: Workspace;
  private maxLines: number;

  constructor(workspace: Workspace, maxLines: number) {
    this.workspace = workspace;
    this.maxLines = maxLines;
  }

  async provideHover(
    doc: vscode.TextDocument,
    pos: vscode.Position,
    _token: vscode.CancellationToken
  ): Promise<vscode.Hover | null> {
    if (!doc.uri.fsPath.endsWith('.tech.md')) {
      return null;
    }

    const resolver = this.workspace.getLinkResolver();

    // Check wiki-link first
    const wikiRange = doc.getWordRangeAtPosition(pos, WIKI_LINK_RE);
    if (wikiRange) {
      const linkText = doc.getText(wikiRange);
      const match = linkText.match(WIKI_LINK_RE);
      if (!match) return null;

      const componentId = match[1].split('#')[0];
      const resolved = resolver.resolveWikiLink(componentId);
      if (!resolved) {
        return new vscode.Hover(
          new vscode.MarkdownString(`Unknown component: **${componentId}**`),
          wikiRange
        );
      }

      return this.buildHover(componentId, resolved, wikiRange);
    }

    // Check agent:// URI
    const agentRange = doc.getWordRangeAtPosition(pos, AGENT_URI_RE);
    if (agentRange) {
      const uriText = doc.getText(agentRange);
      const idMatch = uriText.match(/^agent:\/\/([^/\s]+)/);
      if (!idMatch) return null;

      const componentId = idMatch[1];
      const resolved = resolver.resolveAgentUri(uriText);
      if (!resolved) {
        return new vscode.Hover(
          new vscode.MarkdownString(`Unknown component: **${componentId}**`),
          agentRange
        );
      }

      return this.buildHover(componentId, resolved, agentRange);
    }

    return null;
  }

  private async buildHover(
    componentId: string,
    filePath: string,
    range: vscode.Range
  ): Promise<vscode.Hover> {
    const resolver = this.workspace.getLinkResolver();
    const techDoc = this.workspace.getDocByComponentId(componentId);

    const md = new vscode.MarkdownString();
    md.isTrusted = true;

    // YAML metadata summary
    if (techDoc) {
      md.appendMarkdown(`**${componentId}**\n\n`);
      md.appendMarkdown(`| Field | Value |\n|---|---|\n`);
      md.appendMarkdown(`| component_id | \`${techDoc.componentId}\` |\n`);
      if (techDoc.version) md.appendMarkdown(`| version | \`${techDoc.version}\` |\n`);
      if (techDoc.layer) md.appendMarkdown(`| layer | \`${techDoc.layer}\` |\n`);
      if (techDoc.ownerTeam) md.appendMarkdown(`| owner_team | \`${techDoc.ownerTeam}\` |\n`);
      if (techDoc.securityLevel) md.appendMarkdown(`| security_level | \`${techDoc.securityLevel}\` |\n`);

      const backlinkCount = resolver.getBacklinks(componentId).length;
      md.appendMarkdown(`| backlinks | ${backlinkCount} |\n`);
      md.appendMarkdown('\n');
    }

    // File preview (first N lines)
    try {
      const targetDoc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
      const lineCount = Math.min(targetDoc.lineCount, this.maxLines);
      const lines: string[] = [];
      for (let i = 0; i < lineCount; i++) {
        lines.push(targetDoc.lineAt(i).text);
      }
      md.appendCodeblock(lines.join('\n'), 'markdown');
    } catch {
      md.appendMarkdown(`*Could not read file: ${filePath}*`);
    }

    return new vscode.Hover(md, range);
  }
}
