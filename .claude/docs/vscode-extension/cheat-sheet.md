# VS Code Extension API Cheat Sheet

## Extension Scaffold (package.json)

```json
{
  "name": "chronicler-vscode",
  "displayName": "Chronicler",
  "publisher": "chronicler",
  "engines": { "vscode": "^1.85.0" },
  "activationEvents": ["onLanguage:markdown", "workspaceContains:**/.tech.md"],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [{ "command": "chronicler.showGraph", "title": "Chronicler: Show Graph" }],
    "configuration": { "title": "Chronicler", "properties": {} },
    "views": { "explorer": [{ "id": "chroniclerConnections", "name": "Connections" }] }
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./",
    "test": "node ./out/test/runTest.js"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "@types/node": "^18.0.0",
    "typescript": "^5.0.0",
    "@vscode/test-electron": "^2.3.0"
  }
}
```

## DocumentLinkProvider

```typescript
class TechDocLinkProvider implements vscode.DocumentLinkProvider {
  provideDocumentLinks(doc: vscode.TextDocument): vscode.DocumentLink[] {
    const links: vscode.DocumentLink[] = [];
    const text = doc.getText();
    // Match [[wiki-links]] and agent:// URIs
    const patterns = [/\[\[([^\]]+)\]\]/g, /agent:\/\/[^\s)]+/g];
    for (const pattern of patterns) {
      let match;
      while ((match = pattern.exec(text))) {
        const start = doc.positionAt(match.index);
        const end = doc.positionAt(match.index + match[0].length);
        links.push(new vscode.DocumentLink(new vscode.Range(start, end)));
      }
    }
    return links;
  }
  resolveDocumentLink(link: vscode.DocumentLink): vscode.DocumentLink {
    return link; // resolve target lazily
  }
}
// Register: vscode.languages.registerDocumentLinkProvider('markdown', new TechDocLinkProvider())
```

## DefinitionProvider

```typescript
class TechDocDefinitionProvider implements vscode.DefinitionProvider {
  async provideDefinition(doc: vscode.TextDocument, pos: vscode.Position): Promise<vscode.DefinitionLink[]> {
    const wordRange = doc.getWordRangeAtPosition(pos, /\[\[([^\]]+)\]\]/);
    if (!wordRange) return [];
    const word = doc.getText(wordRange).slice(2, -2); // strip [[ ]]
    // Find .tech.md file matching the word
    const files = await vscode.workspace.findFiles(`**/${word}.tech.md`);
    if (!files.length) return [];
    return [{ targetUri: files[0], targetRange: new vscode.Range(0, 0, 0, 0) }];
  }
}
// Register: vscode.languages.registerDefinitionProvider('markdown', provider)
```

## HoverProvider

```typescript
class TechDocHoverProvider implements vscode.HoverProvider {
  async provideHover(doc: vscode.TextDocument, pos: vscode.Position): Promise<vscode.Hover | null> {
    const wordRange = doc.getWordRangeAtPosition(pos, /\[\[([^\]]+)\]\]/);
    if (!wordRange) return null;
    const target = doc.getText(wordRange).slice(2, -2);
    // Read first N lines of target .tech.md
    const files = await vscode.workspace.findFiles(`**/${target}.tech.md`);
    if (!files.length) return null;
    const content = await vscode.workspace.openTextDocument(files[0]);
    const preview = content.getText().split('\n').slice(0, 10).join('\n');
    return new vscode.Hover(new vscode.MarkdownString(preview), wordRange);
  }
}
```

## CompletionItemProvider

```typescript
class WikiLinkCompletionProvider implements vscode.CompletionItemProvider {
  async provideCompletionItems(doc: vscode.TextDocument, pos: vscode.Position): Promise<vscode.CompletionItem[]> {
    const linePrefix = doc.lineAt(pos).text.substring(0, pos.character);
    if (!linePrefix.endsWith('[[')) return [];
    const techDocs = await vscode.workspace.findFiles('**/*.tech.md');
    return techDocs.map(uri => {
      const name = uri.path.split('/').pop()!.replace('.tech.md', '');
      const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Reference);
      item.insertText = name + ']]';
      return item;
    });
  }
}
// Register with trigger characters: vscode.languages.registerCompletionItemProvider('markdown', provider, '[')
```

## DiagnosticCollection

```typescript
const diagnostics = vscode.languages.createDiagnosticCollection('chronicler');
function validateDocument(doc: vscode.TextDocument) {
  const problems: vscode.Diagnostic[] = [];
  const text = doc.getText();
  const linkPattern = /\[\[([^\]]+)\]\]/g;
  let match;
  while ((match = linkPattern.exec(text))) {
    // Check if link target exists
    const target = match[1];
    // If broken: push diagnostic with Warning severity
    const start = doc.positionAt(match.index);
    const end = doc.positionAt(match.index + match[0].length);
    problems.push(new vscode.Diagnostic(
      new vscode.Range(start, end),
      `Broken link: ${target}`,
      vscode.DiagnosticSeverity.Warning
    ));
  }
  diagnostics.set(doc.uri, problems);
}
```

## WebviewPanel (for D3.js Graph)

```typescript
function showGraphPanel(context: vscode.ExtensionContext) {
  const panel = vscode.window.createWebviewPanel(
    'chroniclerGraph', 'Tech Doc Graph', vscode.ViewColumn.Beside,
    { enableScripts: true, localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')] }
  );
  const d3Uri = panel.webview.asWebviewUri(
    vscode.Uri.joinPath(context.extensionUri, 'node_modules', 'd3', 'dist', 'd3.min.js')
  );
  panel.webview.html = `<!DOCTYPE html>
<html><head><script src="${d3Uri}"></script></head>
<body><div id="graph"></div>
<script>
  const vscode = acquireVsCodeApi();
  window.addEventListener('message', e => {
    if (e.data.type === 'graphData') renderGraph(e.data.nodes, e.data.links);
  });
  function onNodeClick(id) { vscode.postMessage({ type: 'nodeClicked', nodeId: id }); }
</script></body></html>`;
  // Send data: panel.webview.postMessage({ type: 'graphData', nodes, links })
  // Receive: panel.webview.onDidReceiveMessage(msg => { ... })
}
```

## TreeDataProvider (Connections Panel)

```typescript
class ConnectionsProvider implements vscode.TreeDataProvider<ConnectionItem> {
  private _onDidChange = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this._onDidChange.event;
  refresh() { this._onDidChange.fire(); }
  getTreeItem(el: ConnectionItem): vscode.TreeItem { return el; }
  async getChildren(el?: ConnectionItem): Promise<ConnectionItem[]> {
    if (!el) { /* return root items (backlinks + forward links sections) */ }
    else { /* return children for the section */ }
    return [];
  }
}
class ConnectionItem extends vscode.TreeItem {
  constructor(label: string, state: vscode.TreeItemCollapsibleState) {
    super(label, state);
    this.iconPath = new vscode.ThemeIcon('link');
  }
}
// Register in package.json contributes.views + vscode.window.createTreeView('id', { treeDataProvider })
```

## FileSystemWatcher

```typescript
const watcher = vscode.workspace.createFileSystemWatcher('**/*.tech.md');
watcher.onDidCreate(uri => { /* new .tech.md file */ });
watcher.onDidChange(uri => { /* .tech.md modified — rebuild graph data */ });
watcher.onDidDelete(uri => { /* .tech.md removed */ });
context.subscriptions.push(watcher);
```

## Testing (@vscode/test-electron)

```typescript
// src/test/runTest.ts
import { runTests } from '@vscode/test-electron';
async function main() {
  await runTests({
    extensionDevelopmentPath: path.resolve(__dirname, '../../'),
    extensionTestsPath: path.resolve(__dirname, './suite/index'),
  });
}
// src/test/suite/extension.test.ts
suite('Chronicler Extension', () => {
  test('hover provider returns preview', async () => {
    const doc = await vscode.workspace.openTextDocument({ language: 'markdown', content: '[[auth-service]]' });
    const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
      'vscode.executeHoverProvider', doc.uri, new vscode.Position(0, 5)
    );
    assert.ok(hovers);
  });
});
```
