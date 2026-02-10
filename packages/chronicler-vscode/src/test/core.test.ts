import { describe, it, expect, beforeEach } from 'vitest';
import { parseTechDoc } from '../core/parser';
import { LinkResolver } from '../core/link-resolver';
import { Workspace } from '../core/workspace';
import type { TechDoc } from '../core/types';

// -- Fixtures --

const FULL_DOC = `---
component_id: auth-service
version: "1.2.0"
owner_team: platform
layer: api
security_level: high
edges:
  - target: user-store
    type: reads
    protocol: SQL
  - target: token-service
    type: calls
    protocol: gRPC
tags:
  - authentication
  - security
---

# Auth Service

Handles user authentication and token management.

See also [[user-store]] and agent://token-service for related docs.

Check [Token Docs](./token-service.tech.md) for details.
`;

const MINIMAL_DOC = `---
component_id: simple
---

# Simple Component

Nothing special here.
`;

const NO_FRONTMATTER = `# Orphan Doc

Just a markdown file with no YAML block.

Links to [[something]] and agent://other.
`;

const MALFORMED_YAML = `---
component_id: broken
version: [invalid yaml {{
---

# Broken YAML

Body is still here.
`;

const TOKEN_SERVICE_DOC = `---
component_id: token-service
version: "0.5.0"
owner_team: platform
layer: api
security_level: high
edges:
  - target: auth-service
    type: calls
    protocol: gRPC
tags:
  - tokens
---

# Token Service

Issues and validates JWT tokens.

See [[auth-service]] for the consumer.
`;

const USER_STORE_DOC = `---
component_id: user-store
version: "2.0.0"
owner_team: data
layer: infrastructure
security_level: medium
edges: []
tags:
  - storage
---

# User Store

Persists user records.
`;

// -- Parser Tests --

describe('parseTechDoc', () => {
  it('parses full YAML frontmatter correctly', () => {
    const doc = parseTechDoc('/docs/auth-service.tech.md', FULL_DOC);

    expect(doc.componentId).toBe('auth-service');
    expect(doc.version).toBe('1.2.0');
    expect(doc.ownerTeam).toBe('platform');
    expect(doc.layer).toBe('api');
    expect(doc.securityLevel).toBe('high');
    expect(doc.tags).toEqual(['authentication', 'security']);
    expect(doc.edges).toHaveLength(2);
    expect(doc.edges[0]).toEqual({
      target: 'user-store',
      type: 'reads',
      protocol: 'SQL',
    });
    expect(doc.edges[1]).toEqual({
      target: 'token-service',
      type: 'calls',
      protocol: 'gRPC',
    });
  });

  it('returns empty properties when frontmatter is missing', () => {
    const doc = parseTechDoc('/docs/orphan.md', NO_FRONTMATTER);

    expect(doc.componentId).toBe('');
    expect(doc.version).toBe('');
    expect(doc.ownerTeam).toBe('');
    expect(doc.edges).toEqual([]);
    expect(doc.tags).toEqual([]);
  });

  it('handles malformed YAML without crashing', () => {
    const doc = parseTechDoc('/docs/broken.tech.md', MALFORMED_YAML);

    // Malformed YAML -> parseFrontmatter catches error, returns {}
    expect(doc.componentId).toBe('');
    expect(doc.edges).toEqual([]);
    expect(doc.tags).toEqual([]);
    // Body should still be parsed
    expect(doc.sections.length).toBeGreaterThan(0);
    expect(doc.sections[0].title).toBe('Broken YAML');
  });

  it('finds agent:// URIs in body text', () => {
    const doc = parseTechDoc('/docs/auth-service.tech.md', FULL_DOC);
    const agentLinks = doc.links.filter((l) => l.type === 'agent');

    expect(agentLinks).toHaveLength(1);
    expect(agentLinks[0].target).toBe('token-service');
    expect(agentLinks[0].raw).toBe('agent://token-service');
  });

  it('finds [[wiki-links]] in body text', () => {
    const doc = parseTechDoc('/docs/auth-service.tech.md', FULL_DOC);
    const wikiLinks = doc.links.filter((l) => l.type === 'wiki');

    expect(wikiLinks).toHaveLength(1);
    expect(wikiLinks[0].target).toBe('user-store');
    expect(wikiLinks[0].raw).toBe('[[user-store]]');
  });

  it('finds markdown links to .tech.md files', () => {
    const doc = parseTechDoc('/docs/auth-service.tech.md', FULL_DOC);
    const mdLinks = doc.links.filter((l) => l.type === 'markdown');

    expect(mdLinks).toHaveLength(1);
    expect(mdLinks[0].target).toBe('./token-service.tech.md');
    expect(mdLinks[0].raw).toBe('[Token Docs](./token-service.tech.md)');
  });

  it('parses all three link types from a single line', () => {
    const mixed = `---
component_id: mix
---

See [[a]], agent://b, and [C](./c.tech.md) together.
`;
    const doc = parseTechDoc('/docs/mix.tech.md', mixed);
    const types = doc.links.map((l) => l.type).sort();
    expect(types).toEqual(['agent', 'markdown', 'wiki']);
  });

  it('parses headings at all levels with correct line numbers', () => {
    const headings = `---
component_id: headings
---

# H1 Title
## H2 Section
### H3 Sub
#### H4 Deep
##### H5 Deeper
###### H6 Deepest
`;
    const doc = parseTechDoc('/docs/headings.tech.md', headings);

    expect(doc.sections).toHaveLength(6);
    expect(doc.sections.map((s) => s.level)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(doc.sections.map((s) => s.title)).toEqual([
      'H1 Title',
      'H2 Section',
      'H3 Sub',
      'H4 Deep',
      'H5 Deeper',
      'H6 Deepest',
    ]);
    // Line numbers should be monotonically increasing
    for (let i = 1; i < doc.sections.length; i++) {
      expect(doc.sections[i].lineNumber).toBeGreaterThan(
        doc.sections[i - 1].lineNumber
      );
    }
  });

  it('handles empty file', () => {
    const doc = parseTechDoc('/docs/empty.tech.md', '');

    expect(doc.componentId).toBe('');
    expect(doc.sections).toEqual([]);
    expect(doc.links).toEqual([]);
    expect(doc.edges).toEqual([]);
    expect(doc.title).toBe('');
  });

  it('uses H1 as title, falls back to component_id', () => {
    const doc = parseTechDoc('/docs/auth.tech.md', FULL_DOC);
    expect(doc.title).toBe('Auth Service');

    const noH1 = `---
component_id: fallback-title
---

## Only an H2 here
`;
    const doc2 = parseTechDoc('/docs/fallback.tech.md', noH1);
    expect(doc2.title).toBe('fallback-title');
  });

  it('sets uri from filePath argument', () => {
    const doc = parseTechDoc('/custom/path.tech.md', MINIMAL_DOC);
    expect(doc.uri).toBe('/custom/path.tech.md');
  });

  it('parses agent:// with heading fragment', () => {
    const withFragment = `---
component_id: linker
---

See agent://auth-service/authentication-flow for details.
`;
    const doc = parseTechDoc('/docs/linker.tech.md', withFragment);
    const agentLink = doc.links.find((l) => l.type === 'agent')!;

    expect(agentLink.target).toBe('auth-service');
    expect(agentLink.heading).toBe('authentication-flow');
  });

  it('parses wiki-links with heading fragment', () => {
    const withFragment = `---
component_id: linker
---

See [[auth-service#setup]] for setup steps.
`;
    const doc = parseTechDoc('/docs/linker.tech.md', withFragment);
    const wikiLink = doc.links.find((l) => l.type === 'wiki')!;

    expect(wikiLink.target).toBe('auth-service');
    expect(wikiLink.heading).toBe('setup');
  });
});

// -- LinkResolver Tests --

describe('LinkResolver', () => {
  let resolver: LinkResolver;
  let authDoc: TechDoc;
  let tokenDoc: TechDoc;
  let userStoreDoc: TechDoc;

  beforeEach(() => {
    resolver = new LinkResolver();
    authDoc = parseTechDoc('/docs/auth-service.tech.md', FULL_DOC);
    tokenDoc = parseTechDoc('/docs/token-service.tech.md', TOKEN_SERVICE_DOC);
    userStoreDoc = parseTechDoc('/docs/user-store.tech.md', USER_STORE_DOC);
    resolver.setDocs([authDoc, tokenDoc, userStoreDoc]);
  });

  it('resolveAgentUri returns file path for known component', () => {
    const result = resolver.resolveAgentUri('agent://auth-service');
    expect(result).toBe('/docs/auth-service.tech.md');
  });

  it('resolveAgentUri returns null for unknown component', () => {
    const result = resolver.resolveAgentUri('agent://nonexistent');
    expect(result).toBeNull();
  });

  it('resolveWikiLink resolves known component_id', () => {
    const result = resolver.resolveWikiLink('token-service');
    expect(result).toBe('/docs/token-service.tech.md');
  });

  it('resolveWikiLink returns null for unknown component', () => {
    const result = resolver.resolveWikiLink('missing-service');
    expect(result).toBeNull();
  });

  it('resolveWikiLink handles fragment syntax', () => {
    const result = resolver.resolveWikiLink('auth-service#setup');
    expect(result).toBe('/docs/auth-service.tech.md');
  });

  it('getBacklinks returns connections pointing to a component', () => {
    // auth-service has a wiki link [[user-store]], so user-store has a backlink from auth
    const backlinks = resolver.getBacklinks('user-store');
    expect(backlinks.length).toBeGreaterThanOrEqual(1);
    expect(backlinks.some((b) => b.sourceUri === '/docs/auth-service.tech.md')).toBe(true);
  });

  it('getForwardLinks returns outgoing connections', () => {
    // auth-service links to token-service (agent://) and user-store ([[]])
    const forward = resolver.getForwardLinks('auth-service');
    const targets = forward.map((f) => f.link.target);
    expect(targets).toContain('token-service');
    expect(targets).toContain('user-store');
  });

  it('getAllComponentIds returns all registered IDs', () => {
    const ids = resolver.getAllComponentIds();
    expect(ids).toContain('auth-service');
    expect(ids).toContain('token-service');
    expect(ids).toContain('user-store');
    expect(ids).toHaveLength(3);
  });

  it('getDocByUri finds doc by file path', () => {
    const doc = resolver.getDocByUri('/docs/token-service.tech.md');
    expect(doc?.componentId).toBe('token-service');
  });

  it('getDocByUri returns undefined for unknown path', () => {
    const doc = resolver.getDocByUri('/not/real.tech.md');
    expect(doc).toBeUndefined();
  });
});

// -- Workspace Tests --

describe('Workspace', () => {
  let workspace: Workspace;

  const files = [
    { path: '/docs/auth-service.tech.md', content: FULL_DOC },
    { path: '/docs/token-service.tech.md', content: TOKEN_SERVICE_DOC },
    { path: '/docs/user-store.tech.md', content: USER_STORE_DOC },
  ];

  beforeEach(async () => {
    workspace = new Workspace('**/.chronicler/**/*.tech.md');
    await workspace.loadDocuments(files);
  });

  it('loadDocuments parses and stores all docs', () => {
    const all = workspace.getAllDocs();
    expect(all).toHaveLength(3);
  });

  it('getDocByComponentId finds doc by ID', () => {
    const doc = workspace.getDocByComponentId('auth-service');
    expect(doc).toBeDefined();
    expect(doc!.uri).toBe('/docs/auth-service.tech.md');
  });

  it('getDocByComponentId returns undefined for unknown ID', () => {
    const doc = workspace.getDocByComponentId('nonexistent');
    expect(doc).toBeUndefined();
  });

  it('onFileChanged updates existing doc', () => {
    const updated = `---
component_id: auth-service
version: "2.0.0"
owner_team: platform
layer: api
security_level: critical
edges: []
tags: []
---

# Auth Service v2

Rewritten from scratch.
`;
    workspace.onFileChanged('/docs/auth-service.tech.md', updated);
    const doc = workspace.getDoc('/docs/auth-service.tech.md');

    expect(doc!.version).toBe('2.0.0');
    expect(doc!.securityLevel).toBe('critical');
    expect(doc!.title).toBe('Auth Service v2');
  });

  it('onFileDeleted removes doc from workspace', () => {
    workspace.onFileDeleted('/docs/user-store.tech.md');

    expect(workspace.getDoc('/docs/user-store.tech.md')).toBeUndefined();
    expect(workspace.getAllDocs()).toHaveLength(2);
  });

  it('getGraphData returns nodes and edges', () => {
    const graph = workspace.getGraphData();

    expect(graph.nodes).toHaveLength(3);
    expect(graph.links.length).toBeGreaterThan(0);

    const nodeIds = graph.nodes.map((n) => n.id);
    expect(nodeIds).toContain('auth-service');
    expect(nodeIds).toContain('token-service');
    expect(nodeIds).toContain('user-store');
  });

  it('getGraphData edges reflect YAML edge declarations', () => {
    const graph = workspace.getGraphData();

    // auth-service declares edges to user-store and token-service
    const authEdges = graph.links.filter((l) => l.source === 'auth-service');
    expect(authEdges).toHaveLength(2);
    expect(authEdges.map((e) => e.target).sort()).toEqual(['token-service', 'user-store']);
  });

  it('getGraphData nodes have backlink counts', () => {
    const graph = workspace.getGraphData();

    // auth-service is linked to by token-service (wiki link [[auth-service]])
    const authNode = graph.nodes.find((n) => n.id === 'auth-service')!;
    expect(authNode.backlinkCount).toBeGreaterThanOrEqual(1);
  });

  it('link resolver stays in sync after mutations', () => {
    const resolver = workspace.getLinkResolver();

    // Before delete, user-store is resolvable
    expect(resolver.resolveWikiLink('user-store')).toBe('/docs/user-store.tech.md');

    workspace.onFileDeleted('/docs/user-store.tech.md');

    // After delete, user-store is gone
    expect(resolver.resolveWikiLink('user-store')).toBeNull();
  });

  it('getTechMdGlob returns configured glob', () => {
    expect(workspace.getTechMdGlob()).toBe('**/.chronicler/**/*.tech.md');
  });
});
