# D3.js Force Simulation — Cheat Sheet

## Setup

```javascript
const simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-300))
    .force("link", d3.forceLink(links).id(d => d.id).distance(100))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(30));
```

## Node Data Shape

```javascript
// Input nodes get mutated with simulation properties
{ id: "auth-service", label: "Auth Service", layer: "api", x: 0, y: 0, vx: 0, vy: 0 }
```

## Link Data Shape

```javascript
// source/target can be string IDs (resolved by .id() accessor)
{ source: "auth-service", target: "user-service", type: "depends_on" }
```

## Forces

| Force | Purpose |
|-------|---------|
| `forceManyBody()` | Repulsion between all nodes (negative strength) |
| `forceLink(links)` | Spring between connected nodes |
| `forceCenter(x, y)` | Gravity toward center point |
| `forceCollide(r)` | Prevents node overlap |
| `forceX(x)` / `forceY(y)` | Pull toward position |

## Tick Handler (SVG rendering)

```javascript
simulation.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("cx", d => d.x).attr("cy", d => d.y);
});
```

## Drag Behavior

```javascript
d3.drag()
  .on("start", (event, d) => {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
  })
  .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
  .on("end", (event, d) => {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
  });
```

## Control

```javascript
simulation.alpha(1).restart();  // reheat
simulation.stop();              // pause
simulation.force("charge", null); // remove a force
```

## Webview Integration Notes

- D3 runs in the webview (browser context), not Node
- Load d3.min.js as a local resource via webview.asWebviewUri()
- Send graph data from extension to webview via postMessage
- Send click events from webview back to extension via acquireVsCodeApi().postMessage()
