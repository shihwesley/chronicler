# beautiful-mermaid Cheat Sheet

## Installation

```bash
npm install beautiful-mermaid
# or
pnpm add beautiful-mermaid
# or
bun add beautiful-mermaid
```

Browser (CDN):
```html
<script src="https://unpkg.com/beautiful-mermaid/dist/beautiful-mermaid.browser.global.js"></script>
<!-- Exposes global: beautifulMermaid.renderMermaid, .renderMermaidAscii, .THEMES, .DEFAULTS, .fromShikiTheme -->
```

## Core API

### renderMermaid(text, options?): Promise<string>

Async. Takes a Mermaid diagram string, returns an SVG string. Zero DOM dependencies -- works in Node, Bun, Deno, and browsers.

```typescript
import { renderMermaid } from 'beautiful-mermaid'

const svg: string = await renderMermaid(diagramSource, options?)
```

**Options (SVG):**

| Option | Type | Default | Purpose |
|---|---|---|---|
| `bg` | `string` | `"#FFFFFF"` | Background color |
| `fg` | `string` | `"#27272A"` | Foreground / text color |
| `line` | `string?` | -- | Edge / connector color |
| `accent` | `string?` | -- | Arrowheads, highlights |
| `muted` | `string?` | -- | Secondary text, labels |
| `surface` | `string?` | -- | Node fill tint |
| `border` | `string?` | -- | Node stroke |
| `font` | `string` | `"Inter"` | Font family |
| `transparent` | `boolean` | `false` | Transparent background |

### renderMermaidAscii(text, options?): string

Synchronous. Returns ASCII/Unicode art. Good for CLI tools and terminal output.

```typescript
import { renderMermaidAscii } from 'beautiful-mermaid'

const ascii: string = renderMermaidAscii(diagramSource, options?)
```

**Options (ASCII):**

| Option | Type | Default | Purpose |
|---|---|---|---|
| `useAscii` | `boolean` | `false` | ASCII-only (no Unicode box-drawing) |
| `paddingX` | `number` | `5` | Horizontal spacing |
| `paddingY` | `number` | `5` | Vertical spacing |
| `boxBorderPadding` | `number` | `1` | Internal node padding |

### THEMES

15 built-in color themes. Each is an object with `bg`, `fg`, and other color keys matching the SVG options.

```typescript
import { THEMES } from 'beautiful-mermaid'
```

Available themes:

| Theme | Style |
|---|---|
| `zinc-light` | Light neutral |
| `zinc-dark` | Dark neutral |
| `tokyo-night` | Dark blue |
| `tokyo-night-storm` | Dark blue (muted) |
| `tokyo-night-light` | Light blue |
| `catppuccin-mocha` | Dark warm |
| `catppuccin-latte` | Light warm |
| `nord` | Dark cold |
| `nord-light` | Light cold |
| `dracula` | Dark purple |
| `github-light` | GitHub's light theme |
| `github-dark` | GitHub's dark theme |
| `solarized-light` | Solarized light |
| `solarized-dark` | Solarized dark |
| `one-dark` | Atom One Dark |

### fromShikiTheme(theme): ColorOptions

Converts any VS Code / Shiki theme into beautiful-mermaid color options. Lets you match your code highlighting to your diagrams.

```typescript
import { fromShikiTheme } from 'beautiful-mermaid'
import { getSingletonHighlighter } from 'shiki'

const hl = await getSingletonHighlighter({ themes: ['vitesse-dark'] })
const colors = fromShikiTheme(hl.getTheme('vitesse-dark'))
const svg = await renderMermaid(diagram, colors)
```

### Supported Diagram Types

Flowcharts (all directions: TD, LR, BT, RL), State diagrams, Sequence diagrams, Class diagrams, ER diagrams.

## Usage Patterns

### 1. Basic SVG render

```typescript
import { renderMermaid } from 'beautiful-mermaid'

const svg = await renderMermaid(`
  graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Do it]
    B -->|No| D[Skip]
    C --> E[Done]
    D --> E
`)
// svg is a complete <svg> string, write to file or embed in HTML
```

### 2. Using a built-in theme

```typescript
import { renderMermaid, THEMES } from 'beautiful-mermaid'

const svg = await renderMermaid(diagram, THEMES['dracula'])
```

### 3. Mono mode (two-color diagrams)

Pass just `bg` and `fg`. The library derives all other colors via `color-mix()`.

```typescript
const svg = await renderMermaid(diagram, {
  bg: '#1a1b26',
  fg: '#a9b1d6',
})
```

### 4. ASCII output for CLI

```typescript
import { renderMermaidAscii } from 'beautiful-mermaid'

const text = renderMermaidAscii(`
  graph TD
    A --> B
    B --> C
`, { useAscii: true, paddingX: 3 })

console.log(text)
```

### 5. Write SVG to file (Node/Bun)

```typescript
import { renderMermaid, THEMES } from 'beautiful-mermaid'
import { writeFile } from 'fs/promises'

const diagram = `
  stateDiagram-v2
    [*] --> Idle
    Idle --> Running: start
    Running --> Idle: stop
    Running --> Error: fail
    Error --> Idle: reset
`

const svg = await renderMermaid(diagram, {
  ...THEMES['github-dark'],
  font: 'JetBrains Mono',
  transparent: true,
})

await writeFile('diagram.svg', svg)
```

## Common Pitfalls

- **`renderMermaid` is async, `renderMermaidAscii` is sync.** Don't forget to `await` the SVG version. You'll get a Promise object instead of a string if you skip it.
- **Font availability.** The `font` option sets the font family in the SVG, but the font must be available where the SVG is rendered (browser, Inkscape, etc.). The SVG doesn't embed the font file.
- **Diagram type support is limited to 5.** Pie charts, Gantt charts, Git graphs, and other Mermaid diagram types are not supported. Stick to flowchart, state, sequence, class, and ER.
- **No Mermaid config passthrough.** This isn't a wrapper around mermaid-js. It's a standalone renderer. Mermaid directives (`%%{init: ...}%%`) won't work.
- **Browser global name.** When using the CDN script tag, everything is under `beautifulMermaid` (not `beautiful-mermaid` or `beautifulMermaid` -- watch the casing). Access `beautifulMermaid.renderMermaid`, etc.
- **SVG output only.** There's no built-in PNG/PDF export. Use a tool like `sharp`, `resvg`, or a headless browser to convert if needed.

## Sources

- [GitHub](https://github.com/lukilabs/beautiful-mermaid)
- [npm](https://www.npmjs.com/package/beautiful-mermaid)
