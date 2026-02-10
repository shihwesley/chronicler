# VS Code Extension API — Cheat Sheet

## Activation

```typescript
// package.json: "activationEvents": ["workspaceContains:**/*.tech.md"]
export function activate(context: vscode.ExtensionContext) {
  // Register all providers and push to context.subscriptions
  context.subscriptions.push(disposable);
}
export function deactivate() {}
```

## Command Registration

```typescript
vscode.commands.registerCommand('chronicler.showGraph', () => { ... });
```

## DocumentLinkProvider

```typescript
class MyLinkProvider implements vscode.DocumentLinkProvider {
  provideDocumentLinks(doc: vscode.TextDocument): vscode.DocumentLink[] {
    // Return array of DocumentLink(range, uri)
  }
}
vscode.languages.registerDocumentLinkProvider({ language: 'markdown' }, provider);
```

## HoverProvider

```typescript
vscode.languages.registerHoverProvider(
  { pattern: '**/*.tech.md' },
  { provideHover(doc, pos) { return new vscode.Hover('content'); } }
);
```

## CompletionProvider

```typescript
vscode.languages.registerCompletionItemProvider(
  selector,
  provider,
  '[', '['  // trigger characters
);
// provider.provideCompletionItems(doc, pos) → CompletionItem[]
```

## TreeDataProvider

```typescript
class MyTreeProvider implements vscode.TreeDataProvider<MyItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<MyItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  refresh(): void { this._onDidChangeTreeData.fire(); }
  getTreeItem(element: MyItem): vscode.TreeItem { return element; }
  getChildren(element?: MyItem): Thenable<MyItem[]> { ... }
}
vscode.window.registerTreeDataProvider('viewId', provider);
```

## WebviewPanel

```typescript
const panel = vscode.window.createWebviewPanel(
  'chroniclerGraph', 'Dependency Graph', vscode.ViewColumn.Beside,
  { enableScripts: true, localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')] }
);
panel.webview.html = getHtmlContent(panel.webview, extensionUri);

// Extension → Webview
panel.webview.postMessage({ command: 'updateGraph', data: graphData });

// Webview → Extension
panel.webview.onDidReceiveMessage(message => { ... }, null, disposables);

// In webview JS: acquireVsCodeApi().postMessage({ command: 'clicked', nodeId: '...' });
```

## Content Security Policy (webviews)

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'nonce-${nonce}'; style-src ${webview.cspSource};">
```

## DiagnosticCollection

```typescript
const diagnostics = vscode.languages.createDiagnosticCollection('chronicler');
diagnostics.set(uri, [new vscode.Diagnostic(range, 'Broken link', vscode.DiagnosticSeverity.Warning)]);
```

## FileSystemWatcher

```typescript
const watcher = vscode.workspace.createFileSystemWatcher('**/*.tech.md');
watcher.onDidChange(uri => { ... });
watcher.onDidCreate(uri => { ... });
watcher.onDidDelete(uri => { ... });
```

## Configuration

```typescript
const config = vscode.workspace.getConfiguration('chronicler');
const glob = config.get<string>('techMdGlob', '**/.chronicler/**/*.tech.md');
```

## Status Bar

```typescript
const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
statusBar.text = '$(file-text) Chronicler: 3 stale';
statusBar.command = 'chronicler.regenerateStale';
statusBar.show();
```

## Key Patterns

- Push all disposables to `context.subscriptions` for cleanup
- Use `vscode.Uri.joinPath(extensionUri, 'media', 'file.js')` for webview resources
- Use `webview.asWebviewUri(uri)` to convert URIs for webview use
- Nonce-based CSP for webview scripts
- `onDidChangeTreeData` event for tree view refresh
