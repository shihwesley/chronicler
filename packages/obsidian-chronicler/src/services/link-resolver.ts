import { App, TFile, TAbstractFile, CachedMetadata, FrontMatterCache } from 'obsidian';

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
 */
export class LinkResolver {
  private app: App;
  private chroniclerFolder: string;

  constructor(app: App, chroniclerFolder: string) {
    this.app = app;
    this.chroniclerFolder = chroniclerFolder;
  }

  /**
   * Parse an agent:// URI into its component parts.
   * Returns null if the URI is not a valid agent URI.
   */
  parseUri(uri: string): ParsedAgentUri | null {
    const stripped = uri.replace(/^agent:\/\//, '');
    if (!stripped || stripped === uri) {
      // Didn't start with agent:// or was empty after stripping
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
   * Convert an agent:// URI to a vault-relative file path.
   * e.g. "agent://auth-service" -> "chronicler/auth-service.md"
   */
  resolveUri(uri: string): string | null {
    const parsed = this.parseUri(uri);
    if (!parsed) return null;

    const fileName = parsed.componentId.replace(/\//g, '-');
    const path = `${this.chroniclerFolder}/${fileName}.md`;
    return path;
  }

  /**
   * Resolve an agent:// URI to an actual TFile in the vault.
   * Returns null if the file doesn't exist.
   */
  resolveToFile(uri: string): TFile | null {
    const path = this.resolveUri(uri);
    if (!path) return null;

    const abstract: TAbstractFile | null = this.app.vault.getAbstractFileByPath(path);
    if (abstract instanceof TFile) {
      return abstract;
    }
    return null;
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
   * Return all .md files inside the chronicler folder.
   */
  getAllComponents(): TFile[] {
    const allFiles = this.app.vault.getMarkdownFiles();
    const folder = this.chroniclerFolder + '/';
    return allFiles.filter((f) => f.path.startsWith(folder));
  }
}
