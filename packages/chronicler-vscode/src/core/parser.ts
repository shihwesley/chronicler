// Parses .tech.md files into TechDoc objects.
// A .tech.md file has YAML frontmatter between --- delimiters, followed by markdown.

import { parse as parseYaml } from 'yaml';
import type { TechDoc, Edge, Section, ResourceLink } from './types';

const FRONTMATTER_RE = /^---\r?\n([\s\S]{0,50000}?)\r?\n---/;
const HEADING_RE = /^(#{1,6})\s+(.+)$/;
const AGENT_URI_RE = /agent:\/\/[^\s)>\]]+/g;
const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/g;
const MD_LINK_RE = /\[([^\]]*)\]\(([^)]+\.tech\.md[^)]*)\)/g;

/**
 * Parse a .tech.md file into a TechDoc.
 * Handles missing frontmatter, missing fields, and malformed YAML gracefully.
 */
export function parseTechDoc(filePath: string, content: string): TechDoc {
  const { frontmatter, body, bodyStartLine } = extractFrontmatter(content);
  const properties = parseFrontmatter(frontmatter);

  const componentId = asString(properties.component_id, '');
  const edges = parseEdges(properties.edges);
  const tags = parseStringArray(properties.tags);
  const satellites = parseStringArray(properties.satellite_docs);

  const bodyLines = body.split(/\r?\n/);
  const sections = parseSections(bodyLines, bodyStartLine);
  const title = findTitle(sections, componentId);
  const links = parseLinks(bodyLines, bodyStartLine);

  return {
    uri: filePath,
    componentId,
    version: asString(properties.version, ''),
    ownerTeam: asString(properties.owner_team, ''),
    layer: asString(properties.layer, ''),
    securityLevel: asString(properties.security_level, ''),
    edges,
    tags,
    title,
    sections,
    links,
    satellites,
    properties,
  };
}

// --- Frontmatter extraction ---

function extractFrontmatter(content: string): {
  frontmatter: string;
  body: string;
  bodyStartLine: number;
} {
  const match = content.match(FRONTMATTER_RE);
  if (!match) {
    return { frontmatter: '', body: content, bodyStartLine: 0 };
  }

  const fmText = match[1];
  // Count lines consumed by frontmatter block (opening ---, content, closing ---)
  const fmLineCount = fmText.split(/\r?\n/).length + 2;
  const body = content.slice(match[0].length).replace(/^\r?\n/, '');
  return { frontmatter: fmText, body, bodyStartLine: fmLineCount };
}

function parseFrontmatter(raw: string): Record<string, unknown> {
  if (!raw.trim()) return {};
  try {
    const parsed = parseYaml(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return {};
  } catch {
    return {};
  }
}

// --- YAML field helpers ---

function asString(val: unknown, fallback: string): string {
  if (typeof val === 'string') return val;
  if (typeof val === 'number') return String(val);
  return fallback;
}

function parseStringArray(val: unknown): string[] {
  if (!Array.isArray(val)) return [];
  return val.filter((v) => typeof v === 'string' || typeof v === 'number').map(String);
}

function parseEdges(val: unknown): Edge[] {
  if (!Array.isArray(val)) return [];
  return val
    .filter((e) => e && typeof e === 'object')
    .map((e: Record<string, unknown>) => ({
      target: asString(e.target, ''),
      type: asString(e.type, ''),
      protocol: typeof e.protocol === 'string' ? e.protocol : undefined,
    }));
}

// --- Markdown parsing ---

function parseSections(lines: string[], startLine: number): Section[] {
  const sections: Section[] = [];
  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(HEADING_RE);
    if (match) {
      sections.push({
        title: match[2].trim(),
        level: match[1].length,
        lineNumber: startLine + i,
      });
    }
  }
  return sections;
}

function findTitle(sections: Section[], componentId: string): string {
  const h1 = sections.find((s) => s.level === 1);
  return h1?.title ?? componentId;
}

function parseLinks(lines: string[], startLine: number): ResourceLink[] {
  const links: ResourceLink[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNumber = startLine + i;

    // agent:// URIs
    let match: RegExpExecArray | null;
    AGENT_URI_RE.lastIndex = 0;
    while ((match = AGENT_URI_RE.exec(line)) !== null) {
      const raw = match[0];
      const { target, heading } = parseAgentTarget(raw);
      links.push({
        type: 'agent',
        raw,
        target,
        heading,
        lineNumber,
        startChar: match.index,
        endChar: match.index + raw.length,
      });
    }

    // [[wiki-links]]
    WIKI_LINK_RE.lastIndex = 0;
    while ((match = WIKI_LINK_RE.exec(line)) !== null) {
      const raw = match[0];
      const inner = match[1];
      const parts = inner.split('#');
      links.push({
        type: 'wiki',
        raw,
        target: parts[0],
        heading: parts[1],
        lineNumber,
        startChar: match.index,
        endChar: match.index + raw.length,
      });
    }

    // Standard markdown links to .tech.md files
    MD_LINK_RE.lastIndex = 0;
    while ((match = MD_LINK_RE.exec(line)) !== null) {
      const raw = match[0];
      const href = match[2];
      const parts = href.split('#');
      links.push({
        type: 'markdown',
        raw,
        target: parts[0],
        heading: parts[1],
        lineNumber,
        startChar: match.index,
        endChar: match.index + raw.length,
      });
    }
  }

  return links;
}

function parseAgentTarget(uri: string): { target: string; heading?: string } {
  // agent://component-id or agent://component-id/heading
  const withoutScheme = uri.replace(/^agent:\/\//, '');
  const slashIdx = withoutScheme.indexOf('/');
  if (slashIdx === -1) {
    return { target: withoutScheme };
  }
  return {
    target: withoutScheme.slice(0, slashIdx),
    heading: withoutScheme.slice(slashIdx + 1),
  };
}
