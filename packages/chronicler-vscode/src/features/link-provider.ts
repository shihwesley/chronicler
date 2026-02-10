// Makes agent:// URIs and [[wiki-links]] clickable in .tech.md files.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';
import type { GraphQLClient } from '../services/graphql-client';
import { GRAPHQL_SCHEME } from '../core/link-resolver';

const AGENT_URI_RE = /agent:\/\/[^\s)>\]]+/g;
const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/g;

/** Command URI that shows external component info via notification. */
function externalComponentCommand(componentId: string): vscode.Uri {
  const args = encodeURIComponent(JSON.stringify([componentId]));
  return vscode.Uri.parse(`command:chronicler.showExternalComponent?${args}`);
}

export class TechDocLinkProvider implements vscode.DocumentLinkProvider {
  private workspace: Workspace;
  private graphqlClient: GraphQLClient | null;

  constructor(workspace: Workspace, graphqlClient?: GraphQLClient) {
    this.workspace = workspace;
    this.graphqlClient = graphqlClient ?? null;
  }

  provideDocumentLinks(
    doc: vscode.TextDocument,
    _token: vscode.CancellationToken
  ): vscode.ProviderResult<vscode.DocumentLink[]> {
    if (!doc.uri.fsPath.endsWith('.tech.md')) {
      return [];
    }

    const resolver = this.workspace.getLinkResolver();
    const text = doc.getText();
    const lines = text.split('\n');

    // Collect unresolved entries so we can try GraphQL in batch
    const links: vscode.DocumentLink[] = [];
    const unresolvedAgent: Array<{ range: vscode.Range; raw: string }> = [];
    const unresolvedWiki: Array<{ range: vscode.Range; componentId: string }> = [];

    for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
      const line = lines[lineIdx];

      // agent:// URIs
      AGENT_URI_RE.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = AGENT_URI_RE.exec(line)) !== null) {
        const range = new vscode.Range(
          lineIdx, match.index,
          lineIdx, match.index + match[0].length
        );

        const resolved = resolver.resolveAgentUri(match[0]);
        if (resolved) {
          const link = new vscode.DocumentLink(range, vscode.Uri.file(resolved));
          link.tooltip = `Open ${resolved}`;
          links.push(link);
        } else {
          unresolvedAgent.push({ range, raw: match[0] });
        }
      }

      // [[wiki-links]]
      WIKI_LINK_RE.lastIndex = 0;
      while ((match = WIKI_LINK_RE.exec(line)) !== null) {
        const range = new vscode.Range(
          lineIdx, match.index,
          lineIdx, match.index + match[0].length
        );

        const inner = match[1];
        const [componentId] = inner.split('#');
        const resolved = resolver.resolveWikiLink(componentId);
        if (resolved) {
          const link = new vscode.DocumentLink(range, vscode.Uri.file(resolved));
          link.tooltip = `Open ${resolved}`;
          links.push(link);
        } else {
          unresolvedWiki.push({ range, componentId });
        }
      }
    }

    // If nothing unresolved or no GraphQL configured, return sync result
    const hasGraphQL = this.graphqlClient?.isConfigured() ?? false;
    if ((unresolvedAgent.length === 0 && unresolvedWiki.length === 0) || !hasGraphQL) {
      // Fall back to "create" links for unresolved entries
      for (const entry of unresolvedAgent) {
        const link = new vscode.DocumentLink(entry.range, vscode.Uri.parse('command:chronicler.createTechMd'));
        link.tooltip = 'Create missing .tech.md';
        links.push(link);
      }
      for (const entry of unresolvedWiki) {
        const link = new vscode.DocumentLink(entry.range, vscode.Uri.parse('command:chronicler.createTechMd'));
        link.tooltip = `Create ${entry.componentId}.tech.md`;
        links.push(link);
      }
      return links;
    }

    // GraphQL fallback (async path)
    return this.resolveWithGraphQL(links, unresolvedAgent, unresolvedWiki);
  }

  private async resolveWithGraphQL(
    links: vscode.DocumentLink[],
    unresolvedAgent: Array<{ range: vscode.Range; raw: string }>,
    unresolvedWiki: Array<{ range: vscode.Range; componentId: string }>,
  ): Promise<vscode.DocumentLink[]> {
    const resolver = this.workspace.getLinkResolver();

    for (const entry of unresolvedAgent) {
      const resolved = await resolver.resolveAgentUriAsync(entry.raw);
      if (resolved?.startsWith(GRAPHQL_SCHEME)) {
        const componentId = resolved.slice(GRAPHQL_SCHEME.length);
        const link = new vscode.DocumentLink(entry.range, externalComponentCommand(componentId));
        link.tooltip = `External: ${componentId}`;
        links.push(link);
      } else {
        const link = new vscode.DocumentLink(entry.range, vscode.Uri.parse('command:chronicler.createTechMd'));
        link.tooltip = 'Create missing .tech.md';
        links.push(link);
      }
    }

    for (const entry of unresolvedWiki) {
      const resolved = await resolver.resolveWikiLinkAsync(entry.componentId);
      if (resolved?.startsWith(GRAPHQL_SCHEME)) {
        const componentId = resolved.slice(GRAPHQL_SCHEME.length);
        const link = new vscode.DocumentLink(entry.range, externalComponentCommand(componentId));
        link.tooltip = `External: ${componentId}`;
        links.push(link);
      } else {
        const link = new vscode.DocumentLink(entry.range, vscode.Uri.parse('command:chronicler.createTechMd'));
        link.tooltip = `Create ${entry.componentId}.tech.md`;
        links.push(link);
      }
    }

    return links;
  }

  resolveDocumentLink(
    link: vscode.DocumentLink,
    _token: vscode.CancellationToken
  ): vscode.DocumentLink {
    // All targets resolved eagerly in provideDocumentLinks
    return link;
  }
}
