// Typed config reader for the chronicler.* settings namespace.

import * as vscode from 'vscode';

export function getConfig() {
  const config = vscode.workspace.getConfiguration('chronicler');
  return {
    techMdGlob: config.get<string>('techMdGlob', '**/.chronicler/**/*.tech.md'),
    linkResolution: config.get<string>('linkResolution', 'hybrid'),
    graphqlEndpoint: config.get<string>('graphql.endpoint', ''),
    graphqlApiKey: config.get<string>('graphql.apiKey', ''),
    graphLayout: config.get<string>('graph.layout', 'force-directed'),
    graphColorBy: config.get<string>('graph.colorBy', 'layer'),
    graphGroupBy: config.get<string>('graph.groupBy', 'owner_team'),
    hoverMaxLines: config.get<number>('hover.maxLines', 10),
    diagnosticsEnabled: config.get<boolean>('diagnostics.enable', true),
    wikiLinksEnabled: config.get<boolean>('wikiLinks.enable', true),
    agentUriEnabled: config.get<boolean>('agentUri.enable', true),
    pythonPath: config.get<string>('pythonPath', 'python3'),
    sourceWatchGlob: config.get<string>('watch.sourceGlob', '**/*.{ts,js,py,rs,go,java}'),
  };
}
