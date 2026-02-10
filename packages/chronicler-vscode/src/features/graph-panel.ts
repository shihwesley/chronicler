import * as vscode from 'vscode';
import { Workspace } from '../core/workspace';
import type { GraphData } from '../core/types';

/** Manages a WebView panel that renders a D3.js force-directed graph of .tech.md documents. */
export class GraphPanel {
  public static currentPanel: GraphPanel | undefined;
  private static readonly viewType = 'chroniclerGraph';

  private readonly panel: vscode.WebviewPanel;
  private readonly workspace: Workspace;
  private readonly extensionUri: vscode.Uri;
  private readonly disposables: vscode.Disposable[] = [];

  public static createOrShow(
    context: vscode.ExtensionContext,
    workspace: Workspace,
  ): GraphPanel {
    const column = vscode.ViewColumn.Beside;

    if (GraphPanel.currentPanel) {
      GraphPanel.currentPanel.panel.reveal(column);
      GraphPanel.currentPanel.refresh();
      return GraphPanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel(
      GraphPanel.viewType,
      'Tech Doc Graph',
      column,
      {
        enableScripts: true,
        localResourceRoots: [
          vscode.Uri.joinPath(context.extensionUri, 'node_modules'),
          vscode.Uri.joinPath(context.extensionUri, 'media'),
        ],
        retainContextWhenHidden: true,
      },
    );

    GraphPanel.currentPanel = new GraphPanel(panel, context.extensionUri, workspace);
    return GraphPanel.currentPanel;
  }

  private constructor(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    workspace: Workspace,
  ) {
    this.panel = panel;
    this.extensionUri = extensionUri;
    this.workspace = workspace;

    this.panel.webview.html = this.getHtmlContent();

    // Handle messages from the webview (node clicks)
    this.panel.webview.onDidReceiveMessage(
      (msg) => {
        if (msg.type === 'nodeClicked') {
          const doc = this.workspace.getDocByComponentId(msg.nodeId);
          if (doc) {
            vscode.window.showTextDocument(vscode.Uri.file(doc.uri));
          }
        }
      },
      null,
      this.disposables,
    );

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    // Push initial graph data once the webview is ready
    this.refresh();
  }

  /** Re-fetch graph data from the workspace and push it to the webview. */
  public refresh(): void {
    const graphData: GraphData = this.workspace.getGraphData();
    this.panel.webview.postMessage({ type: 'graphData', ...graphData });
  }

  private dispose(): void {
    GraphPanel.currentPanel = undefined;
    this.panel.dispose();
    for (const d of this.disposables) {
      d.dispose();
    }
  }

  private getHtmlContent(): string {
    const webview = this.panel.webview;

    const d3Uri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'node_modules', 'd3', 'dist', 'd3.min.js'),
    );

    const nonce = getNonce();

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; script-src 'nonce-${nonce}'; style-src ${webview.cspSource} 'unsafe-inline';">
  <title>Tech Doc Graph</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: 100%; height: 100%; overflow: hidden; }
    body {
      background: var(--vscode-editor-background, #1e1e1e);
      color: var(--vscode-editor-foreground, #d4d4d4);
      font-family: var(--vscode-font-family, sans-serif);
    }
    svg { display: block; width: 100%; height: 100%; }
    .node-label {
      font-size: 11px;
      fill: var(--vscode-editor-foreground, #d4d4d4);
      pointer-events: none;
      text-anchor: middle;
    }
    .link {
      stroke-opacity: 0.6;
      stroke-width: 1.5;
    }
    .tooltip {
      position: absolute;
      padding: 8px 12px;
      background: var(--vscode-editorWidget-background, #252526);
      border: 1px solid var(--vscode-editorWidget-border, #454545);
      color: var(--vscode-editor-foreground, #d4d4d4);
      font-size: 12px;
      border-radius: 4px;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.15s;
      line-height: 1.5;
      z-index: 10;
      max-width: 280px;
    }
    .tooltip.visible { opacity: 1; }
  </style>
</head>
<body>
  <svg id="graph"></svg>
  <div class="tooltip" id="tooltip"></div>

  <script nonce="${nonce}" src="${d3Uri}"></script>
  <script nonce="${nonce}">
    // Acquire VS Code API handle (can only call once)
    const vscode = acquireVsCodeApi();

    const svg = d3.select('#graph');
    const tooltip = document.getElementById('tooltip');

    // Colors by layer
    const layerColors = {
      infrastructure: '#4CAF50',
      logic: '#2196F3',
      api: '#FF9800',
    };
    const defaultNodeColor = '#9E9E9E';

    // Colors by edge type
    const edgeColors = {
      calls: '#999999',
      reads: '#4CAF50',
      writes: '#F44336',
      depends_on: '#2196F3',
    };
    const defaultEdgeColor = '#666666';

    function nodeColor(layer) {
      return layerColors[layer] || defaultNodeColor;
    }

    function nodeRadius(backlinkCount) {
      // sqrt scale, clamped between 8 and 30
      const r = 8 + Math.sqrt(backlinkCount || 0) * 4;
      return Math.min(30, Math.max(8, r));
    }

    let simulation = null;
    let container = null;

    function renderGraph(nodes, links) {
      svg.selectAll('*').remove();

      const width = document.body.clientWidth;
      const height = document.body.clientHeight;

      svg.attr('viewBox', [0, 0, width, height]);

      // Top-level container for zoom/pan transforms
      container = svg.append('g');

      // Zoom behavior
      const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
          container.attr('transform', event.transform);
        });
      svg.call(zoom);

      // Build simulation
      simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(d => nodeRadius(d.backlinkCount) + 4))
        .on('tick', ticked);

      // Draw edges
      const link = container.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('class', 'link')
        .attr('stroke', d => edgeColors[d.type] || defaultEdgeColor);

      // Draw node groups
      const node = container.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .call(d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended)
        );

      // Circle for each node
      node.append('circle')
        .attr('r', d => nodeRadius(d.backlinkCount))
        .attr('fill', d => nodeColor(d.layer))
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5)
        .style('cursor', 'pointer');

      // Label below the node
      node.append('text')
        .attr('class', 'node-label')
        .attr('dy', d => nodeRadius(d.backlinkCount) + 14)
        .text(d => d.label || d.id);

      // Click handler — open the .tech.md file
      node.on('click', (event, d) => {
        vscode.postMessage({ type: 'nodeClicked', nodeId: d.id });
      });

      // Hover — show tooltip
      node.on('mouseenter', (event, d) => {
        tooltip.innerHTML = [
          '<strong>' + escapeHtml(d.id) + '</strong>',
          'Layer: ' + escapeHtml(d.layer),
          'Owner: ' + escapeHtml(d.ownerTeam),
          'Security: ' + escapeHtml(d.securityLevel),
          'Backlinks: ' + d.backlinkCount,
        ].join('<br>');
        tooltip.classList.add('visible');
      });

      node.on('mousemove', (event) => {
        tooltip.style.left = (event.pageX + 12) + 'px';
        tooltip.style.top = (event.pageY - 12) + 'px';
      });

      node.on('mouseleave', () => {
        tooltip.classList.remove('visible');
      });

      function ticked() {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
      }
    }

    // Drag handlers — reheat simulation while dragging
    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    function escapeHtml(str) {
      const el = document.createElement('span');
      el.textContent = str || '';
      return el.innerHTML;
    }

    // Listen for data messages from the extension host
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'graphData') {
        renderGraph(msg.nodes || [], msg.links || []);
      }
    });
  </script>
</body>
</html>`;
  }
}

/** Generate a random nonce for the CSP script-src directive. */
function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let nonce = '';
  for (let i = 0; i < 32; i++) {
    nonce += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return nonce;
}
