// Reports broken links, missing YAML fields, and [FLAG:OUTDATED] markers as VS Code diagnostics.

import * as vscode from 'vscode';
import type { Workspace } from '../core/workspace';

const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/g;
const AGENT_URI_RE = /agent:\/\/[^\s)>\]]+/g;
const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---/;
const FLAG_OUTDATED_RE = /\[FLAG:OUTDATED\]/g;

const REQUIRED_FIELDS = ['component_id', 'version', 'owner_team', 'layer'];

// Debounce delay for re-validation on document change
const DEBOUNCE_MS = 500;

export class DiagnosticsManager implements vscode.Disposable {
  private workspace: Workspace;
  private collection: vscode.DiagnosticCollection;
  private disposables: vscode.Disposable[] = [];
  private debounceTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();

  constructor(workspace: Workspace, collection: vscode.DiagnosticCollection) {
    this.workspace = workspace;
    this.collection = collection;

    // Validate when a .tech.md document is opened
    this.disposables.push(
      vscode.workspace.onDidOpenTextDocument((doc) => {
        if (doc.uri.fsPath.endsWith('.tech.md')) {
          this.validateDocument(doc);
        }
      })
    );

    // Re-validate on change (debounced)
    this.disposables.push(
      vscode.workspace.onDidChangeTextDocument((e) => {
        if (e.document.uri.fsPath.endsWith('.tech.md')) {
          this.scheduleValidation(e.document);
        }
      })
    );

    // Clear diagnostics and pending timers when document is closed
    this.disposables.push(
      vscode.workspace.onDidCloseTextDocument((doc) => {
        this.collection.delete(doc.uri);
        const key = doc.uri.toString();
        const timer = this.debounceTimers.get(key);
        if (timer) {
          clearTimeout(timer);
          this.debounceTimers.delete(key);
        }
      })
    );

    // Validate all currently open .tech.md files
    this.validateAll();
  }

  validateAll(): void {
    for (const doc of vscode.workspace.textDocuments) {
      if (doc.uri.fsPath.endsWith('.tech.md')) {
        this.validateDocument(doc);
      }
    }
  }

  validateDocument(doc: vscode.TextDocument): void {
    const diagnostics: vscode.Diagnostic[] = [];
    const text = doc.getText();
    const resolver = this.workspace.getLinkResolver();

    // -- Broken link checks --

    this.scanBrokenLinks(text, doc, resolver, diagnostics);

    // -- Missing required YAML fields --

    this.scanMissingFields(text, doc, diagnostics);

    // -- [FLAG:OUTDATED] markers --

    this.scanOutdatedFlags(text, doc, diagnostics);

    this.collection.set(doc.uri, diagnostics);
  }

  private scanBrokenLinks(
    text: string,
    doc: vscode.TextDocument,
    resolver: ReturnType<Workspace['getLinkResolver']>,
    diagnostics: vscode.Diagnostic[]
  ): void {
    const lines = text.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Wiki-links
      WIKI_LINK_RE.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = WIKI_LINK_RE.exec(line)) !== null) {
        const componentId = match[1].split('#')[0];
        const resolved = resolver.resolveWikiLink(componentId);
        if (!resolved) {
          const range = new vscode.Range(i, match.index, i, match.index + match[0].length);
          diagnostics.push(
            new vscode.Diagnostic(range, `Broken link: ${componentId}`, vscode.DiagnosticSeverity.Warning)
          );
        }
      }

      // Agent URIs
      AGENT_URI_RE.lastIndex = 0;
      while ((match = AGENT_URI_RE.exec(line)) !== null) {
        const idMatch = match[0].match(/^agent:\/\/([^/\s]+)/);
        const target = idMatch?.[1] ?? match[0];
        const resolved = resolver.resolveAgentUri(match[0]);
        if (!resolved) {
          const range = new vscode.Range(i, match.index, i, match.index + match[0].length);
          diagnostics.push(
            new vscode.Diagnostic(range, `Broken link: ${target}`, vscode.DiagnosticSeverity.Warning)
          );
        }
      }
    }
  }

  private scanMissingFields(
    text: string,
    doc: vscode.TextDocument,
    diagnostics: vscode.Diagnostic[]
  ): void {
    const fmMatch = text.match(FRONTMATTER_RE);
    if (!fmMatch) {
      // No frontmatter at all -- warn at line 0 for each required field
      for (const field of REQUIRED_FIELDS) {
        diagnostics.push(
          new vscode.Diagnostic(
            new vscode.Range(0, 0, 0, 0),
            `Missing required field: ${field}`,
            vscode.DiagnosticSeverity.Warning
          )
        );
      }
      return;
    }

    const fmText = fmMatch[1];
    for (const field of REQUIRED_FIELDS) {
      // Simple check: the field key should appear at the start of a line in the frontmatter
      const fieldRe = new RegExp(`^${field}\\s*:`, 'm');
      if (!fieldRe.test(fmText)) {
        // Place the diagnostic on the opening --- line
        diagnostics.push(
          new vscode.Diagnostic(
            new vscode.Range(0, 0, 0, 3),
            `Missing required field: ${field}`,
            vscode.DiagnosticSeverity.Warning
          )
        );
      }
    }
  }

  private scanOutdatedFlags(
    text: string,
    doc: vscode.TextDocument,
    diagnostics: vscode.Diagnostic[]
  ): void {
    const lines = text.split('\n');
    for (let i = 0; i < lines.length; i++) {
      FLAG_OUTDATED_RE.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = FLAG_OUTDATED_RE.exec(lines[i])) !== null) {
        const range = new vscode.Range(i, match.index, i, match.index + match[0].length);
        diagnostics.push(
          new vscode.Diagnostic(range, 'Flagged as outdated', vscode.DiagnosticSeverity.Information)
        );
      }
    }
  }

  private scheduleValidation(doc: vscode.TextDocument): void {
    const key = doc.uri.toString();
    const existing = this.debounceTimers.get(key);
    if (existing) clearTimeout(existing);

    this.debounceTimers.set(
      key,
      setTimeout(() => {
        this.debounceTimers.delete(key);
        this.validateDocument(doc);
      }, DEBOUNCE_MS)
    );
  }

  dispose(): void {
    for (const timer of this.debounceTimers.values()) {
      clearTimeout(timer);
    }
    this.debounceTimers.clear();

    for (const d of this.disposables) {
      d.dispose();
    }
    this.disposables = [];
  }
}
