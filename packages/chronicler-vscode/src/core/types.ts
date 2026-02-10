// Core types for .tech.md document model.
// No vscode imports — this module is platform-agnostic.

/** Link types recognized in .tech.md files */
export type LinkType = 'agent' | 'wiki' | 'markdown';

export interface ResourceLink {
  type: LinkType;
  /** Original text as found in document */
  raw: string;
  /** Resolved target (component_id or path) */
  target: string;
  /** Optional #heading reference */
  heading?: string;
  /** Line where the link appears */
  lineNumber: number;
  /** Character offset on that line */
  startChar: number;
  /** End character offset */
  endChar: number;
}

export interface Edge {
  /** component_id of dependency */
  target: string;
  /** calls | reads | writes | depends_on */
  type: string;
  /** REST | gRPC | SQL | event */
  protocol?: string;
}

export interface Section {
  title: string;
  /** Heading level (1-6) */
  level: number;
  lineNumber: number;
}

export interface TechDoc {
  /** File path (platform-agnostic, not vscode.Uri) */
  uri: string;
  /** From YAML: component_id */
  componentId: string;
  /** From YAML: version */
  version: string;
  /** From YAML: owner_team */
  ownerTeam: string;
  /** infrastructure | logic | api */
  layer: string;
  /** low | medium | high | critical */
  securityLevel: string;
  /** From YAML: edges */
  edges: Edge[];
  /** From YAML or #hashtags */
  tags: string[];
  /** First H1 or component_id */
  title: string;
  /** Parsed headings */
  sections: Section[];
  /** All outgoing links */
  links: ResourceLink[];
  /** From YAML: satellite_docs */
  satellites: string[];
  /** All YAML frontmatter key-values */
  properties: Record<string, unknown>;
}

export interface Connection {
  sourceUri: string;
  targetUri: string;
  link: ResourceLink;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

export interface GraphNode {
  /** component_id */
  id: string;
  uri: string;
  /** title or component_id */
  label: string;
  layer: string;
  ownerTeam: string;
  securityLevel: string;
  backlinkCount: number;
}

export interface GraphEdge {
  /** Source component_id */
  source: string;
  /** Target component_id */
  target: string;
  /** Edge type */
  type: string;
  protocol?: string;
}
