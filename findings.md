# Findings & Decisions

## Requirements
From PRD/spec review:
- `.tech.md` naming: `<ComponentID>.<SubCategory>.tech.md`
- Storage: `.chronicler/` at project root
- YAML frontmatter: component_id, version, owner_team, layer, security_level, governance required
- Hub-and-Spoke: Hub max ~1500 words, satellites for overflow
- Inter-service URI: `agent://<service-name>/<file-path>.tech.md`

## Priority
Speed - MVP first, iterate

## Research Findings
- PyGithub: mature, sync API, good for simple crawling
- ghapi: FastAI's lib, more Pythonic, supports pagination
- anthropic SDK: clean API, streaming support
- Key files to harvest: package.json, pyproject.toml, Dockerfile, terraform/*.tf, README.md

### MarkItDown Integration (2026-02-02)
**Source:** https://github.com/microsoft/markitdown (Microsoft)

**What it does:** Python utility converting various file formats to Markdown optimized for LLM consumption.

**Supported formats:**
| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, PPTX, XLSX, XLS, EPUB |
| Web | HTML, RSS, Wikipedia |
| Data | CSV, JSON, XML |
| Media | Images (OCR), Audio (transcription) |
| Archives | ZIP (recursive) |

**API:**
```python
from markitdown import MarkItDown
md = MarkItDown()
result = md.convert("file.pdf")  # or URL, stream
print(result.text_content)
```

**Key deps:** beautifulsoup4, pdfminer.six, python-pptx, mammoth, magika

**Integration rationale:** Enterprises have existing tech docs in PDF/DOCX/PPTX that need conversion to markdown for Chronicler to analyze and generate `.tech.md` files.

## Technical Decisions

### LLM Interface
| Decision | Rationale |
|----------|-----------|
| Provider-agnostic LLM | Enterprise picks Claude/GPT-4/Gemini via config |
| Custom LLM interface | Not LiteLLM/LangChain - lean, controlled |
| Cloud-first | Defer local model support (Ollama/vLLM) |
| Streaming support | Long .tech.md docs need incremental output |
| Retry at interface | Exponential backoff, consistent across providers |
| Strict validation | Reject invalid output, retry once, then fail |
| Mermaid validation | Use mmdc CLI for connectivity graph syntax |

### Rate Limiting / Queue
| Decision | Rationale |
|----------|-----------|
| Queue-based architecture | Handles bursts, resilient, enterprise-ready for 500+ repos |
| Cloud queue (SQS/Pub-Sub/Service Bus) | Managed, scalable, fits enterprise infra |
| Provider-agnostic queue | Same pattern as LLM - enterprise picks |
| Dead letter queue | Failed jobs don't block pipeline, require manual review |
| Worker pool | Configurable parallelism based on rate limits |

### Monorepo Handling
| Decision | Rationale |
|----------|-----------|
| One .tech.md per package | Granular documentation, matches enterprise structure |
| Manifest-first detection | Parse lerna/pnpm/nx workspaces, respect repo config |
| Convention fallback | Works without workspace manifest (packages/, apps/, services/) |
| _index.yaml registry | Machine-readable package list for monorepos |
| Root + satellite structure | Root overview links to package docs |

### CLI Interface
| Decision | Rationale |
|----------|-----------|
| `chronicler` command | Matches project name, memorable |
| Subcommand structure | `crawl`, `draft`, `validate`, `config` - discoverable |
| Common flags | `--dry-run`, `--verbose`, `--json`, `--config` |
| Exit codes | 0=success, 1=validation, 2=config, 3=API, 4=queue |
| typer + rich | Modern Python CLI with pretty output |

### Configuration
| Decision | Rationale |
|----------|-----------|
| YAML format | Readable, comments, matches .tech.md style |
| `chronicler.yaml` | Project-local config file |
| Env var expansion | `${VAR_NAME}` syntax for secrets |
| Resolution order | CLI > env > project > user > defaults |
| Pydantic validation | Type-safe config loading |

### Prompt Engineering
| Decision | Rationale |
|----------|-----------|
| System + User separation | Rules in system, context in user |
| Anti-examples | Prevent marketing language, guessing, verbosity |
| Context limits | README 2000 chars, file tree 50 files, Dockerfile 1000 chars |
| Strict output format | YAML frontmatter + Architectural Intent + Mermaid |
| Always `ai_draft` | Never claim human verification |

### General
| Decision | Rationale |
|----------|-----------|
| Python + PyGithub | Mature, well-documented |
| Local-first output | Write to local .chronicler/, no PR automation yet |

### Document Conversion (MarkItDown)
| Decision | Rationale |
|----------|-----------|
| Use Microsoft MarkItDown | Mature, LLM-optimized, handles PDF/DOCX/PPTX/images |
| Merge into VCS Crawler | Built-in from start, not afterthought |
| Optional dependencies | Install pdfminer/mammoth/pptx only when needed |
| OCR for diagrams | Extract text from architecture images |
| Azure DocIntel optional | Enterprise can use for complex PDFs |

### MemVid Integration (2026-02-02)
**Source:** https://github.com/memvid/memvid, https://docs.memvid.com

**What it is:** Single-file AI memory system with hybrid search, entity extraction, time-travel.

**Key features:**
| Feature | Description |
|---------|-------------|
| `.mv2` format | Self-contained: data + indexes + WAL, git-committable |
| Lexical search | BM25 for exact keyword matching |
| Vector search | Semantic similarity via embeddings |
| Hybrid search | Combines both, default mode |
| Memory Cards | SPO triplets for O(1) entity lookups |
| Time-indexed frames | Append-only, query historical states |

**Python SDK:**
```python
from memvid import create, use

# Create new memory file
mem = create("chronicler.mv2")
mem.put(title="auth-service", text="...", label="tech.md")

# Search
results = mem.find("database connection", k=5, mode="hybrid")

# Entity state
mem.state("auth-service")  # Returns all facts about auth-service
```

**Integration rationale:** Replace JSON graph in Chronicler Lite with MemVid. Single .mv2 file provides:
- All three index types (lexical, vector, time)
- Built-in knowledge graph via Memory Cards
- No database server needed
- Portable, version-controllable

**⚠️ IMPLEMENTATION REQUIREMENT:**
Before implementing MemVid integration (Phase 5), agent MUST fetch and analyze:
- https://docs.memvid.com/sdks (SDK reference for Python)
- https://docs.memvid.com/sdks/python (Python-specific API)
- https://docs.memvid.com/introduction/glossary (terminology)
- https://docs.memvid.com/resources/examples (use case examples)
- https://github.com/memvid/memvid (source + README)

### Product Architecture (Lite vs Enterprise)
| Decision | Rationale |
|----------|-----------|
| Shared Core + Plugins | Best balance: low duplication, independent scaling |
| Separate products (Lite/Enterprise) | Different audiences, different dependencies |
| chronicler-core shared | VCS crawler, AI drafter, doc converter, .tech.md generator |
| Lite = local-first | SQLite queue, MemVid storage, no cloud deps |
| Enterprise = plugins | Cloud queue, RBAC, Mnemon/Neo4j, multi-org |
| Easy upgrade path | Lite → Enterprise by installing plugins |
| MemVid replaces JSON graph | `.mv2` = docs + indexes + graph in single file |
| Memory Cards = SPO triplets | Built-in knowledge graph, no Neo4j needed for Lite |
| Enterprise syncs to Neo4j | Complex graph queries + Mnemon 3D viz |
| Git-track .mv2 file | Portable, no rebuild on clone, self-contained |
| .tech.md = source of truth | Human-readable, diffable in PRs |
| .mv2 = search index | Built from .tech.md, contains embeddings |

### IDE Integration (VS Code Extension)
| Decision | Rationale |
|----------|-----------|
| Foam-inspired monolith | Single VS Code extension, proven pattern, covers all AI-IDE forks (Cursor, Windsurf, Antigravity) |
| Hybrid link resolution | Local-first for speed, GraphQL fallback for enterprise cross-repo |
| agent:// + [[wiki-links]] dual syntax | agent:// for cross-repo precision, [[]] for in-repo convenience |
| D3.js graph WebView | Industry standard, matches Foam's approach |
| YAML-driven edges | Leverage existing .tech.md schema, no import parsing needed |
| VS Code provider APIs | DocumentLinkProvider, DefinitionProvider, HoverProvider, CompletionProvider, TreeView, WebView |

### Obsidian Integration (Sync + Plugin)
| Decision | Rationale |
|----------|-----------|
| Phase A: sync daemon, Phase B: community plugin | Sync delivers value immediately, plugin builds on synced files |
| Transform pipeline (not raw copy) | Need link rewriting, frontmatter flattening, Dataview field injection |
| Filesystem + REST API sync modes | Filesystem simplest; REST API for real-time without watchers |
| Dataview field injection | Turns .tech.md into queryable database — Obsidian's killer feature |
| _index.md auto-generation | Instant overview with embedded Dataview queries |
| Aliases from component_id | [[auth-service]] resolves even if filename differs |
| CSS class tagging | Visual distinction between Chronicler docs and personal notes |

### Cartographer + Merkle Tree
| Decision | Rationale |
|----------|-----------|
| Cartographer as auto-dependency | Chronicler calls enhanced Cartographer plugin to map codebase before AI drafting |
| Separate Merkle trees | Cartographer: source file hashes for re-exploration. Chronicler: source+doc pair hashes for drift detection |
| Merkle Lite: drift detection | O(1) root hash comparison, O(log n) localization of stale docs |
| Merkle Enterprise: blast radius | Graph-aware change propagation via edges + wiki-links, N-hop impact |
| SHA-256 in .merkle.json | Git-trackable, alongside .tech.md files |
| Codebase map → AI Drafter | Pre-digested context = better .tech.md quality with fewer LLM tokens |

### Foam Research (2026-02-05)
**Source:** https://github.com/foambubble/foam

**Architecture:**
- Layered: core (platform-agnostic) → features (VS Code providers) → services (file watching, caching)
- Core uses reversed trie for O(log n) identifier matching
- Graph is WebView-based, receives JSON via postMessage, 500ms debounce on updates
- Features: DocumentLinkProvider, DefinitionProvider, ReferenceProvider, HoverProvider, CompletionProvider, TreeView panels (backlinks, tags, orphans, placeholders)
- Parser: unified + remark-parse + remark-wiki-link + remark-frontmatter

**Key VS Code APIs:** registerDocumentLinkProvider, registerDefinitionProvider, registerReferenceProvider, registerHoverProvider, registerCompletionItemProvider, createTreeView, createWebviewPanel, registerDiagnosticCollection

### Obsidian Research (2026-02-05)
**Key findings:**
- Vault = folder of .md files, no proprietary format
- YAML frontmatter auto-parsed into Properties system
- Wiki-links resolve by filename (case-insensitive, normalizes spaces/hyphens)
- Dataview plugin: SQL-like queries over YAML frontmatter, inline fields [key:: value]
- Local REST API plugin: HTTPS REST for programmatic CRUD, token auth
- Advanced URI plugin: obsidian://adv-uri?file=... for deep linking
- MCP Server available for AI agent integration
- .tech.md files work immediately in Obsidian with zero conversion

## Visual/Browser Findings
<!-- Update after every 2 view/browser operations -->
- Foam repo cloned and analyzed: architecture, features, VS Code API usage (2026-02-05)
- Obsidian docs researched: vault structure, plugin API, Dataview, import mechanisms (2026-02-05)
