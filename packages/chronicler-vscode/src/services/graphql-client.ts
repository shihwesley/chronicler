// GraphQL client for the Chronicler enterprise backend.
// Falls back to this when local link resolution fails (cross-repo links).

import { getConfig } from './config';

export interface ComponentResult {
  id: string;
  type: string;
  label: string;
}

export class GraphQLClient {
  private endpoint: string;
  private apiKey: string;

  constructor() {
    const config = getConfig();
    this.endpoint = config.graphqlEndpoint;
    this.apiKey = config.graphqlApiKey;
  }

  /** True if a GraphQL endpoint is configured. */
  isConfigured(): boolean {
    return this.endpoint.length > 0;
  }

  /** Resolve a component ID to its metadata. Returns null if not found or not configured. */
  async resolveComponent(componentId: string): Promise<ComponentResult | null> {
    if (!this.isConfigured()) return null;
    try {
      const result = await this.query(
        `query ($id: String!) { component(id: $id) { id type label } }`,
        { id: componentId }
      );
      return result?.data?.component ?? null;
    } catch {
      return null;
    }
  }

  /** List all known components (useful for cross-repo autocomplete). */
  async listComponents(): Promise<ComponentResult[]> {
    if (!this.isConfigured()) return [];
    try {
      const result = await this.query(`{ components { id type label } }`);
      return result?.data?.components ?? [];
    } catch {
      return [];
    }
  }

  /** Get edges from a given component (cross-repo graph data). */
  async getEdges(sourceId: string): Promise<Array<{ source: string; target: string; relation: string }>> {
    if (!this.isConfigured()) return [];
    try {
      const result = await this.query(
        `query ($source: String!) { edges(source: $source) { source target relation } }`,
        { source: sourceId }
      );
      return result?.data?.edges ?? [];
    } catch {
      return [];
    }
  }

  /** Low-level GraphQL POST. Uses Node's built-in fetch (available in VS Code's Electron). */
  private async query(query: string, variables?: Record<string, unknown>): Promise<Record<string, any>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }
    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify({ query, variables }),
    });
    if (!response.ok) {
      throw new Error(`GraphQL request failed: ${response.status}`);
    }
    return response.json() as Promise<Record<string, any>>;
  }
}
