# D3.js Force-Directed Graph Cheat Sheet

## Core Setup

```javascript
const width = 960, height = 600;

const svg = d3.select("#graph").append("svg")
    .attr("width", width)
    .attr("height", height);
```

## Force Simulation

```javascript
const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide().radius(20))
    .on("tick", ticked);
```

### Key Forces
| Force | Purpose | Key param |
|-------|---------|-----------|
| `forceLink(links)` | Pull connected nodes together | `.distance(100)`, `.id(d => d.id)` |
| `forceManyBody()` | Repel/attract all nodes | `.strength(-300)` (negative = repel) |
| `forceCenter(x, y)` | Center gravity | width/2, height/2 |
| `forceCollide()` | Prevent overlap | `.radius(20)` |

### Simulation Control
- `simulation.restart()` — reheat and restart timer
- `simulation.stop()` — pause
- `simulation.alpha(0.3)` — set heat level (0-1)
- `simulation.alphaTarget(0.3)` — target heat (for drag)
- `simulation.find(x, y, radius)` — find closest node

## Drawing Links + Nodes

```javascript
const link = svg.selectAll(".link")
    .data(links)
  .join("line")
    .attr("class", "link")
    .attr("stroke", "#999")
    .attr("stroke-width", d => d.value || 1);

const node = svg.selectAll(".node")
    .data(nodes)
  .join("circle")
    .attr("class", "node")
    .attr("r", d => d.radius || 10)
    .attr("fill", d => colorScale(d.group));
```

## Tick Handler (updates positions each frame)

```javascript
function ticked() {
  link
    .attr("x1", d => d.source.x)
    .attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x)
    .attr("y2", d => d.target.y);
  node
    .attr("cx", d => d.x)
    .attr("cy", d => d.y);
}
```

## Drag Behavior

```javascript
node.call(d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended));

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
  d.fx = null;  // release fixed position
  d.fy = null;
}
```

## Node Labels

```javascript
const label = svg.selectAll(".label")
    .data(nodes)
  .join("text")
    .attr("class", "label")
    .attr("text-anchor", "middle")
    .attr("dy", -15)
    .text(d => d.label);

// In ticked():
label.attr("x", d => d.x).attr("y", d => d.y);
```

## Color Scales

```javascript
const colorScale = d3.scaleOrdinal()
    .domain(["infrastructure", "logic", "api"])
    .range(["#4CAF50", "#2196F3", "#FF9800"]);
```

## Zoom + Pan

```javascript
const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on("zoom", (event) => {
      svg.selectAll("g").attr("transform", event.transform);
    });
svg.call(zoom);
```

## VS Code WebView Integration

In a VS Code WebView, D3 runs inside an iframe-like sandbox:

```typescript
// Extension side — send graph data to webview
panel.webview.postMessage({ type: 'graphData', nodes, links });

// Extension side — receive click events from webview
panel.webview.onDidReceiveMessage(msg => {
  if (msg.type === 'nodeClicked') {
    vscode.window.showTextDocument(vscode.Uri.file(msg.filePath));
  }
});
```

```html
<!-- Webview HTML -->
<script>
  const vscode = acquireVsCodeApi();
  window.addEventListener('message', e => {
    if (e.data.type === 'graphData') {
      renderGraph(e.data.nodes, e.data.links);
    }
  });
  function onNodeClick(nodeId, filePath) {
    vscode.postMessage({ type: 'nodeClicked', nodeId, filePath });
  }
</script>
```

Load D3 via webview URI:
```typescript
const d3Uri = panel.webview.asWebviewUri(
  vscode.Uri.joinPath(context.extensionUri, 'node_modules', 'd3', 'dist', 'd3.min.js')
);
```
