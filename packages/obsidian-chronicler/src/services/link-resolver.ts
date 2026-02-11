import { App, TFile, CachedMetadata, FrontMatterCache } from 'obsidian';
import type { DiscoveryService } from './discovery';

/**
 * Parsed representation of an agent:// URI.
 */
export interface ParsedAgentUri {
  /** The component ID (first path segment) */
  componentId: string;
  /** Optional heading reference (second path segment) */
  heading: string | null;
}

/**
 * Resolves agent:// URIs to vault file paths and metadata.
 * Uses DiscoveryService for multi-project resolution.
 */
export class LinkResolver {
  private app: App;
  private discovery: DiscoveryService;

  constructor(app: App, discovery: DiscoveryService) {
    this.app = app;
    this.discovery = discovery;
  }

  /**
   * Parse an agent:// URI into its component parts.
   * Returns null if the URI is not a valid agent URI.
   */
  parseUri(uri: string): ParsedAgentUri | null {
    const stripped = uri.replace(/^agent:\/\//, '');
    if (!stripped || stripped === uri) {
      return null;
    }

    const segments = stripped.split('/').filter(Boolean);
    if (segments.length === 0) {
      return null;
    }

    return {
      componentId: segments[0],
      heading: segments.length > 1 ? segments.slice(1).join('/') : null,
    };
  }

  /**
   * Resolve an agent:// URI to a vault-relative file path.
   * Searches all discovered projects, preferring the project that
   * contains contextPath (the file currently being viewed).
   */
  resolveUri(uri: string, contextPath?: string): string | null {
    const parsed = this.parseUri(uri);
    if (!parsed) return null;

    const files = this.discovery.resolveComponent(parsed.componentId, contextPath);
    return files.length > 0 ? files[0].path : null;
  }

  /**
   * Resolve an agent:// URI to a TFile.
   */
  resolveToFile(uri: string, contextPath?: string): TFile | null {
    const parsed = this.parseUri(uri);
    if (!parsed) return null;

    const files = this.discovery.resolveComponent(parsed.componentId, contextPath);
    return files.length > 0 ? files[0] : null;
  }

  /**
   * Read frontmatter from MetadataCache for the file the URI points to.
   */
  getComponentMetadata(uri: string): FrontMatterCache | null {
    const file = this.resolveToFile(uri);
    if (!file) return null;

    const cache: CachedMetadata | null = this.app.metadataCache.getFileCache(file);
    if (!cache || !cache.frontmatter) return null;

    return cache.frontmatter;
  }

  /**
   * Return all .tech.md files across all discovered projects.
   */
  getAllComponents(): TFile[] {
    const byProject = this.discovery.getAllTechFiles();
    const all: TFile[] = [];
    for (const files of byProject.values()) {
      all.push(...files);
    }
    return all;
  }
}
