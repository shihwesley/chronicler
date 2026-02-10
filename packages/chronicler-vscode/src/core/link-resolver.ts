// Resolves links found in .tech.md files to file paths and component IDs.
// No vscode imports — platform-agnostic.

import type { TechDoc, ResourceLink, Connection } from './types';
import type { GraphQLClient } from '../services/graphql-client';

/** Marker protocol for components resolved via GraphQL (not local). */
export const GRAPHQL_SCHEME = 'graphql://';

export class LinkResolver {
  private docs: Map<string, TechDoc>;
  private graphqlClient: GraphQLClient | null = null;

  constructor() {
    this.docs = new Map();
  }

  /** Attach a GraphQL client for cross-repo fallback resolution. */
  setGraphQLClient(client: GraphQLClient): void {
    this.graphqlClient = client;
  }

  /** Replace the full document set used for resolution. */
  setDocs(docs: TechDoc[]): void {
    this.docs.clear();
    for (const doc of docs) {
      if (doc.componentId) {
        this.docs.set(doc.componentId, doc);
      }
    }
  }

  /** Resolve an agent:// URI to a file path. */
  resolveAgentUri(uri: string): string | null {
    const match = uri.match(/^agent:\/\/([^/\s]+)/);
    if (!match) return null;
    const doc = this.docs.get(match[1]);
    return doc?.uri ?? null;
  }

  /** Resolve a [[wiki-link]] to a file path. */
  resolveWikiLink(link: string): string | null {
    const parts = link.split('#');
    const componentId = parts[0];
    const doc = this.docs.get(componentId);
    return doc?.uri ?? null;
  }

  /**
   * Async version of resolveAgentUri — tries local first, then GraphQL fallback.
   * Returns `graphql://{componentId}` for externally-resolved components.
   */
  async resolveAgentUriAsync(uri: string): Promise<string | null> {
    const local = this.resolveAgentUri(uri);
    if (local) return local;

    if (!this.graphqlClient) return null;
    const match = uri.match(/^agent:\/\/([^/\s]+)/);
    if (!match) return null;
    const component = await this.graphqlClient.resolveComponent(match[1]);
    return component ? `${GRAPHQL_SCHEME}${component.id}` : null;
  }

  /**
   * Async version of resolveWikiLink — tries local first, then GraphQL fallback.
   * Returns `graphql://{componentId}` for externally-resolved components.
   */
  async resolveWikiLinkAsync(link: string): Promise<string | null> {
    const local = this.resolveWikiLink(link);
    if (local) return local;

    if (!this.graphqlClient) return null;
    const componentId = link.split('#')[0];
    const component = await this.graphqlClient.resolveComponent(componentId);
    return component ? `${GRAPHQL_SCHEME}${component.id}` : null;
  }

  /** Get all backlinks pointing to a given component. */
  getBacklinks(componentId: string): Connection[] {
    const backlinks: Connection[] = [];
    const targetDoc = this.docs.get(componentId);
    const targetUri = targetDoc?.uri ?? '';

    for (const doc of this.docs.values()) {
      for (const link of doc.links) {
        if (this.resolveTargetId(link) === componentId) {
          backlinks.push({
            sourceUri: doc.uri,
            targetUri,
            link,
          });
        }
      }
    }
    return backlinks;
  }

  /** Get forward links from a given component. */
  getForwardLinks(componentId: string): Connection[] {
    const doc = this.docs.get(componentId);
    if (!doc) return [];

    const forwardLinks: Connection[] = [];
    for (const link of doc.links) {
      const targetId = this.resolveTargetId(link);
      if (targetId) {
        const targetDoc = this.docs.get(targetId);
        forwardLinks.push({
          sourceUri: doc.uri,
          targetUri: targetDoc?.uri ?? '',
          link,
        });
      }
    }
    return forwardLinks;
  }

  /** Extract target component_id from a ResourceLink. */
  private resolveTargetId(link: ResourceLink): string | null {
    switch (link.type) {
      case 'agent': {
        // agent://component-id/... -> component-id
        const match = link.raw.match(/^agent:\/\/([^/\s]+)/);
        return match?.[1] ?? null;
      }
      case 'wiki': {
        // target is already the component_id (set during parsing)
        return link.target || null;
      }
      case 'markdown': {
        // For markdown links, target is a file path — try to find a doc whose uri matches
        for (const doc of this.docs.values()) {
          if (doc.uri === link.target || doc.uri.endsWith(link.target)) {
            return doc.componentId || null;
          }
        }
        return null;
      }
      default:
        return null;
    }
  }

  /** Get all known component IDs. */
  getAllComponentIds(): string[] {
    return Array.from(this.docs.keys());
  }

  /** Find doc by file path. */
  getDocByUri(uri: string): TechDoc | undefined {
    for (const doc of this.docs.values()) {
      if (doc.uri === uri) return doc;
    }
    return undefined;
  }
}
