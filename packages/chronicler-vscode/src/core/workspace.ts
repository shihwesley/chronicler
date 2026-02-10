// Manages the collection of .tech.md documents in a workspace.
// No vscode imports — receives file paths and contents from the VS Code layer.

import type { TechDoc, GraphData, GraphNode, GraphEdge } from './types';
import { parseTechDoc } from './parser';
import { LinkResolver } from './link-resolver';

export class Workspace {
  private docs: Map<string, TechDoc>;
  private linkResolver: LinkResolver;
  private techMdGlob: string;

  constructor(techMdGlob: string) {
    this.docs = new Map();
    this.linkResolver = new LinkResolver();
    this.techMdGlob = techMdGlob;
  }

  /** Parse and store all provided .tech.md files, then rebuild the link index. */
  async loadDocuments(files: Array<{ path: string; content: string }>): Promise<void> {
    this.docs.clear();
    for (const file of files) {
      const doc = parseTechDoc(file.path, file.content);
      this.docs.set(file.path, doc);
    }
    this.rebuildLinkResolver();
  }

  /** Re-parse a single changed file and update indexes. */
  onFileChanged(filePath: string, content: string): void {
    const doc = parseTechDoc(filePath, content);
    this.docs.set(filePath, doc);
    this.rebuildLinkResolver();
  }

  /** Remove a deleted file from the index. */
  onFileDeleted(filePath: string): void {
    this.docs.delete(filePath);
    this.rebuildLinkResolver();
  }

  getDoc(filePath: string): TechDoc | undefined {
    return this.docs.get(filePath);
  }

  getDocByComponentId(componentId: string): TechDoc | undefined {
    for (const doc of this.docs.values()) {
      if (doc.componentId === componentId) return doc;
    }
    return undefined;
  }

  getAllDocs(): TechDoc[] {
    return Array.from(this.docs.values());
  }

  getLinkResolver(): LinkResolver {
    return this.linkResolver;
  }

  getTechMdGlob(): string {
    return this.techMdGlob;
  }

  /** Build the full graph representation from all loaded docs. */
  getGraphData(): GraphData {
    return buildGraphData(this.getAllDocs(), this.linkResolver);
  }

  private rebuildLinkResolver(): void {
    this.linkResolver.setDocs(this.getAllDocs());
  }
}

/** Compute graph nodes and edges from the document set. */
function buildGraphData(docs: TechDoc[], resolver: LinkResolver): GraphData {
  const nodes: GraphNode[] = [];
  const links: GraphEdge[] = [];

  // Build edges from each doc's declared edges[]
  for (const doc of docs) {
    for (const edge of doc.edges) {
      if (edge.target) {
        links.push({
          source: doc.componentId,
          target: edge.target,
          type: edge.type,
          protocol: edge.protocol,
        });
      }
    }
  }

  // Build nodes with backlink counts
  for (const doc of docs) {
    const backlinkCount = doc.componentId
      ? resolver.getBacklinks(doc.componentId).length
      : 0;

    nodes.push({
      id: doc.componentId,
      uri: doc.uri,
      label: doc.title || doc.componentId,
      layer: doc.layer,
      ownerTeam: doc.ownerTeam,
      securityLevel: doc.securityLevel,
      backlinkCount,
    });
  }

  return { nodes, links };
}
