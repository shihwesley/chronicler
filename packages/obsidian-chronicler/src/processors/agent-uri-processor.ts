import { MarkdownPostProcessorContext, Plugin } from 'obsidian';
import { LinkResolver } from '../services/link-resolver';
import type { DiscoveryService } from '../services/discovery';

// Matches agent:// URIs in text content
// Non-global for .test(), create new RegExp('...', 'g') for iterative .exec()
const AGENT_URI_PATTERN = /agent:\/\/[\w-]+(?:\/[\w-]+)*/;

/**
 * Minimal interface for the host plugin. Avoids importing
 * ChroniclerPlugin directly (which would create a circular dep).
 */
interface ChroniclerPluginLike extends Plugin {
  discovery: DiscoveryService;
}

/**
 * Post-processor that converts agent:// URIs in rendered markdown
 * into clickable links that open the corresponding tech doc.
 */
export class AgentUriProcessor {
  private resolver: LinkResolver | null = null;
  private plugin: ChroniclerPluginLike | null = null;

  register(plugin: Plugin): void {
    this.plugin = plugin as ChroniclerPluginLike;
    this.resolver = new LinkResolver(
      plugin.app,
      this.plugin.discovery,
    );

    // Register the markdown post-processor
    plugin.registerMarkdownPostProcessor(
      (el: HTMLElement, ctx: MarkdownPostProcessorContext) => {
        this.processElement(el, ctx);
      },
    );

    // Register obsidian://agent protocol handler
    // Allows external links like obsidian://agent?id=auth-service
    plugin.registerObsidianProtocolHandler('agent', async (params) => {
      const id = params.id;
      if (!id) return;

      const uri = `agent://${id}`;
      this.navigateToUri(uri);
    });
  }

  /**
   * Walk the rendered HTML element tree and replace agent:// URIs
   * with clickable links.
   */
  private processElement(
    el: HTMLElement,
    _ctx: MarkdownPostProcessorContext,
  ): void {
    // Handle anchor elements that already have agent:// hrefs
    // (from markdown like [text](agent://component))
    this.processAnchors(el);

    // Handle agent:// URIs in plain text nodes and code elements
    this.processTextNodes(el);
  }

  /**
   * Find <a> tags whose href starts with agent:// and rewire them.
   */
  private processAnchors(el: HTMLElement): void {
    const anchors = el.querySelectorAll('a[href^="agent://"]');
    for (let i = 0; i < anchors.length; i++) {
      const anchor = anchors[i] as HTMLAnchorElement;
      const uri = anchor.getAttribute('href');
      if (!uri) continue;

      this.convertToAgentLink(anchor, uri, anchor.textContent || uri);
    }
  }

  /**
   * Walk all text nodes in the element looking for agent:// patterns.
   * When found, split the text node and insert a clickable span.
   */
  private processTextNodes(el: HTMLElement): void {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const nodesToProcess: Text[] = [];

    let node: Text | null;
    while ((node = walker.nextNode() as Text | null)) {
      if (node.textContent && AGENT_URI_PATTERN.test(node.textContent)) {
        nodesToProcess.push(node);
      }
      // Non-global regex, no lastIndex reset needed
    }

    for (const textNode of nodesToProcess) {
      this.replaceTextNodeWithLinks(textNode);
    }
  }

  /**
   * Replace a text node containing one or more agent:// URIs
   * with a mix of text and clickable span elements.
   */
  private replaceTextNodeWithLinks(textNode: Text): void {
    const text = textNode.textContent;
    if (!text) return;

    const parent = textNode.parentNode;
    if (!parent) return;

    // Skip if inside an existing agent-link (avoid double-processing)
    if (
      parent instanceof HTMLElement &&
      parent.classList.contains('agent-link')
    ) {
      return;
    }

    const fragment = document.createDocumentFragment();
    let lastIndex = 0;

    // Fresh global regex per call — avoids stale lastIndex state
    const globalPattern = new RegExp(AGENT_URI_PATTERN.source, 'g');
    let match: RegExpExecArray | null;

    while ((match = globalPattern.exec(text)) !== null) {
      // Text before the match
      if (match.index > lastIndex) {
        fragment.appendChild(
          document.createTextNode(text.slice(lastIndex, match.index)),
        );
      }

      const uri = match[0];
      const linkEl = this.createAgentLinkElement(uri, uri);
      fragment.appendChild(linkEl);

      lastIndex = match.index + uri.length;
    }

    // Remaining text after last match
    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    parent.replaceChild(fragment, textNode);
  }

  /**
   * Turn an existing anchor element into a working agent link.
   */
  private convertToAgentLink(
    anchor: HTMLAnchorElement,
    uri: string,
    displayText: string,
  ): void {
    anchor.removeAttribute('href');
    anchor.classList.add('agent-link');
    anchor.textContent = displayText;
    anchor.setAttribute('aria-label', this.buildTooltip(uri));

    anchor.addEventListener('click', (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      this.navigateToUri(uri);
    });
  }

  /**
   * Create a clickable span element for an agent:// URI.
   */
  private createAgentLinkElement(uri: string, displayText: string): HTMLElement {
    const span = document.createElement('span');
    span.classList.add('agent-link');
    span.textContent = displayText;
    span.setAttribute('aria-label', this.buildTooltip(uri));
    span.setAttribute('role', 'link');
    span.tabIndex = 0;

    span.addEventListener('click', (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      this.navigateToUri(uri);
    });

    span.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.navigateToUri(uri);
      }
    });

    return span;
  }

  /**
   * Build tooltip text from frontmatter metadata if available.
   */
  private buildTooltip(uri: string): string {
    if (!this.resolver) return uri;

    const meta = this.resolver.getComponentMetadata(uri);
    if (!meta) return uri;

    const parts: string[] = [];
    if (meta.title) parts.push(meta.title);
    if (meta.type) parts.push(`Type: ${meta.type}`);
    if (meta.layer) parts.push(`Layer: ${meta.layer}`);
    if (meta.status) parts.push(`Status: ${meta.status}`);

    return parts.length > 0 ? parts.join(' | ') : uri;
  }

  /**
   * Open the vault note that corresponds to an agent:// URI.
   * If the URI has a heading segment, scroll to that heading.
   */
  private navigateToUri(uri: string): void {
    if (!this.resolver || !this.plugin) return;

    const parsed = this.resolver.parseUri(uri);
    if (!parsed) return;

    // Pass active file path for same-project preference
    const activeFile = this.plugin.app.workspace.getActiveFile();
    const contextPath = activeFile?.path;

    const filePath = this.resolver.resolveUri(uri, contextPath);
    if (!filePath) return;

    let linkText = filePath;
    if (parsed.heading) {
      linkText = `${filePath}#${parsed.heading}`;
    }

    this.plugin.app.workspace.openLinkText(linkText, '', false);
  }
}
