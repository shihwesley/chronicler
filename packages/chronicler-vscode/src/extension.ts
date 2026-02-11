import * as vscode from 'vscode';
import { Workspace } from './core/workspace';
import { TechDocLinkProvider } from './features/link-provider';
import { TechDocDefinitionProvider } from './features/definition-provider';
import { TechDocReferenceProvider } from './features/reference-provider';
import { FileWatcherService } from './services/file-watcher';
import { getConfig } from './services/config';
import { GraphQLClient } from './services/graphql-client';
import { PythonBridge } from './services/python-bridge';

import { ConnectionsProvider } from './features/connections-panel';
import { TagsProvider } from './features/tags-panel';

import { TechDocHoverProvider } from './features/hover-provider';
import { WikiLinkCompletionProvider } from './features/completion-provider';
import { DiagnosticsManager } from './features/diagnostics';
import { GraphPanel } from './features/graph-panel';

const MARKDOWN_SELECTOR: vscode.DocumentFilter = {
  language: 'markdown',
  scheme: 'file',
};

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const config = getConfig();

  // Initialize workspace index
  const workspace = new Workspace(config.techMdGlob);

  const fileUris = await vscode.workspace.findFiles(config.techMdGlob);
  const files: Array<{ path: string; content: string }> = [];
  for (const uri of fileUris) {
    try {
      const doc = await vscode.workspace.openTextDocument(uri);
      files.push({ path: uri.fsPath, content: doc.getText() });
    } catch {
      // skip unreadable files
    }
  }
  await workspace.loadDocuments(files);

  // -- GraphQL fallback for cross-repo links --

  const graphqlClient = new GraphQLClient();
  if (graphqlClient.isConfigured()) {
    workspace.getLinkResolver().setGraphQLClient(graphqlClient);
  }

  // -- Core providers (ready now) --

  const linkProvider = new TechDocLinkProvider(
    workspace,
    graphqlClient.isConfigured() ? graphqlClient : undefined
  );
  context.subscriptions.push(
    vscode.languages.registerDocumentLinkProvider(MARKDOWN_SELECTOR, linkProvider)
  );

  const definitionProvider = new TechDocDefinitionProvider(workspace);
  context.subscriptions.push(
    vscode.languages.registerDefinitionProvider(MARKDOWN_SELECTOR, definitionProvider)
  );

  const referenceProvider = new TechDocReferenceProvider(workspace);
  context.subscriptions.push(
    vscode.languages.registerReferenceProvider(MARKDOWN_SELECTOR, referenceProvider)
  );

  const hoverProvider = new TechDocHoverProvider(workspace, config.hoverMaxLines);
  context.subscriptions.push(
    vscode.languages.registerHoverProvider(MARKDOWN_SELECTOR, hoverProvider)
  );

  const completionProvider = new WikiLinkCompletionProvider(workspace);
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(MARKDOWN_SELECTOR, completionProvider, '[')
  );

  const diagnosticCollection = vscode.languages.createDiagnosticCollection('chronicler');
  const diagnosticsManager = new DiagnosticsManager(workspace, diagnosticCollection);
  context.subscriptions.push(diagnosticCollection, diagnosticsManager);

  // -- Commands --

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.showGraph', () => {
      GraphPanel.createOrShow(context, workspace);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.refreshGraph', () => {
      GraphPanel.currentPanel?.refresh();
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.createTechMd', async () => {
      const wsFolder = vscode.workspace.workspaceFolders?.[0];
      if (!wsFolder) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
      }

      const name = await vscode.window.showInputBox({
        prompt: 'Component name (e.g. auth-service)',
        placeHolder: 'my-component',
        validateInput: (v) => v.trim() ? null : 'Name is required',
      });
      if (!name) return;

      const layer = await vscode.window.showQuickPick(
        ['api', 'service', 'model', 'util', 'ui', 'config', 'test', 'other'],
        { placeHolder: 'Select component layer' },
      );
      if (!layer) return;

      const chroniclerDir = vscode.Uri.joinPath(wsFolder.uri, '.chronicler');
      const filePath = vscode.Uri.joinPath(chroniclerDir, `${name}.tech.md`);

      const template = [
        '---',
        `title: "${name}"`,
        `layer: ${layer}`,
        'owner_team: ""',
        'status: draft',
        '---',
        '',
        `# ${name}`,
        '',
        '## Purpose',
        '',
        '## Dependencies',
        '',
        '## API Surface',
        '',
        '## Invariants',
        '',
      ].join('\n');

      await vscode.workspace.fs.createDirectory(chroniclerDir);
      await vscode.workspace.fs.writeFile(filePath, Buffer.from(template, 'utf-8'));
      const doc = await vscode.workspace.openTextDocument(filePath);
      await vscode.window.showTextDocument(doc);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.showExternalComponent', async (componentId: string) => {
      if (!graphqlClient.isConfigured()) {
        vscode.window.showWarningMessage(`No GraphQL endpoint configured for external component lookup.`);
        return;
      }
      const component = await graphqlClient.resolveComponent(componentId);
      if (component) {
        vscode.window.showInformationMessage(
          `External component: ${component.label} (${component.type}) [${component.id}]`
        );
      } else {
        vscode.window.showWarningMessage(`Component "${componentId}" not found in the Chronicler graph.`);
      }
    })
  );

  // -- Python bridge + CLI commands --

  const pythonBridge = new PythonBridge(config.pythonPath, context.secrets);
  const outputChannel = vscode.window.createOutputChannel('Chronicler');
  context.subscriptions.push(outputChannel);

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.init', async () => {
      const wsPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!wsPath) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
      }
      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Chronicler: Initializing...' },
        async () => {
          try {
            const result = await pythonBridge.init(wsPath);
            outputChannel.appendLine(result);
            vscode.window.showInformationMessage('Chronicler initialized.');
            // Re-scan workspace after init creates new .tech.md files
            const fileUris = await vscode.workspace.findFiles(config.techMdGlob);
            const newFiles: Array<{ path: string; content: string }> = [];
            for (const uri of fileUris) {
              try {
                const doc = await vscode.workspace.openTextDocument(uri);
                newFiles.push({ path: uri.fsPath, content: doc.getText() });
              } catch { /* skip */ }
            }
            await workspace.loadDocuments(newFiles);
            await updateStatusBar();
          } catch {
            // PythonBridge already showed the error message
          }
        },
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.regenerate', async () => {
      const wsPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!wsPath) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
      }
      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Chronicler: Regenerating stale docs...' },
        async () => {
          try {
            const result = await pythonBridge.regenerate(wsPath);
            outputChannel.appendLine(result);
            vscode.window.showInformationMessage('Chronicler: Regeneration complete.');
            await updateStatusBar();
          } catch {
            // PythonBridge already showed the error message
          }
        },
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.status', async () => {
      const wsPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!wsPath) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
      }
      try {
        const status = await pythonBridge.status(wsPath);
        outputChannel.appendLine(`Stale: ${status.staleCount} / Total: ${status.totalCount}`);
        outputChannel.show(true);
      } catch {
        // PythonBridge already showed the error message
      }
    })
  );

  // -- LLM Provider setup --

  context.subscriptions.push(
    vscode.commands.registerCommand('chronicler.setupProvider', async () => {
      const provider = await vscode.window.showQuickPick(
        [
          { label: 'Anthropic', value: 'anthropic' },
          { label: 'OpenAI', value: 'openai' },
          { label: 'Google', value: 'google' },
          { label: 'Ollama (Local)', value: 'ollama' },
        ],
        { placeHolder: 'Select LLM provider' },
      );
      if (!provider) return;

      await vscode.workspace.getConfiguration('chronicler').update('llm.provider', provider.value, true);

      if (provider.value !== 'ollama') {
        const apiKey = await vscode.window.showInputBox({
          prompt: `Enter ${provider.label} API key`,
          password: true,
          placeHolder: 'sk-...',
          validateInput: (v) => v.trim() ? null : 'API key is required',
        });
        if (!apiKey) return;

        await context.secrets.store('chronicler.llm.apiKey', apiKey);
      }

      vscode.window.showInformationMessage(`Chronicler: ${provider.label} configured.`);
    })
  );

  // -- Status bar --

  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = 'chronicler.regenerate';
  statusBar.text = '$(file-text) Chronicler';
  statusBar.show();
  context.subscriptions.push(statusBar);

  let disposed = false;
  async function updateStatusBar(): Promise<void> {
    if (disposed) return;
    const wsPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!wsPath) return;
    try {
      const result = await pythonBridge.status(wsPath);
      statusBar.text = `$(file-text) Chronicler: ${result.staleCount} stale`;
      statusBar.tooltip = `${result.staleCount} of ${result.totalCount} docs need regeneration`;
    } catch {
      statusBar.text = '$(file-text) Chronicler';
      statusBar.tooltip = undefined;
    }
  }

  // Initial status bar update
  updateStatusBar();

  // -- File watcher --

  const fileWatcher = new FileWatcherService(workspace, config.techMdGlob);
  context.subscriptions.push(fileWatcher);

  // Refresh status bar when files change
  const statusWatcher = vscode.workspace.createFileSystemWatcher(config.techMdGlob);
  let statusDebounce: NodeJS.Timeout | undefined;
  const debouncedStatusUpdate = () => {
    clearTimeout(statusDebounce);
    statusDebounce = setTimeout(() => updateStatusBar(), 2000);
  };
  statusWatcher.onDidChange(debouncedStatusUpdate);
  statusWatcher.onDidCreate(debouncedStatusUpdate);
  statusWatcher.onDidDelete(debouncedStatusUpdate);
  context.subscriptions.push(statusWatcher, { dispose: () => { clearTimeout(statusDebounce); disposed = true; } });

  // Watch source files for staleness changes (longer debounce to avoid thrashing)
  const sourceGlob = config.sourceWatchGlob;
  const sourceWatcher = vscode.workspace.createFileSystemWatcher(sourceGlob);
  let sourceDebounce: NodeJS.Timeout | undefined;
  const debouncedSourceUpdate = () => {
    clearTimeout(sourceDebounce);
    sourceDebounce = setTimeout(() => updateStatusBar(), 5000);
  };
  sourceWatcher.onDidChange(debouncedSourceUpdate);
  sourceWatcher.onDidCreate(debouncedSourceUpdate);
  sourceWatcher.onDidDelete(debouncedSourceUpdate);
  context.subscriptions.push(sourceWatcher, { dispose: () => clearTimeout(sourceDebounce) });

  // -- Context flag for menu visibility --

  const hasTechMd = workspace.getAllDocs().length > 0;
  await vscode.commands.executeCommand('setContext', 'chronicler.hasWorkspace', hasTechMd);

  // -- Sidebar tree views --

  const connectionsProvider = new ConnectionsProvider(workspace);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('chroniclerConnections', connectionsProvider),
    { dispose: () => connectionsProvider.dispose() },
  );

  const tagsProvider = new TagsProvider(workspace);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('chroniclerTags', tagsProvider),
    { dispose: () => tagsProvider.dispose() },
  );
}

export function deactivate(): void {
  // nothing to clean up yet
}
