# MemVid SDK v2 — Agent Cheat Sheet

## Install
```
pip install memvid-sdk>=2.0.0
```
Package: `memvid-sdk` on PyPI (v2.0.156, Rust core + PyO3 bindings)

## Core API

```python
from memvid_sdk import Memvid

# Create new .mv2 file
mem = Memvid.create(path="file.mv2", kind="basic")

# Open existing .mv2 file
mem = Memvid.use(kind="basic", path="file.mv2")

# Alternative module-level convenience functions:
# from memvid_sdk import create, use
# mem = create("file.mv2")
# mem = use("basic", "file.mv2")
```

## Write Operations

```python
# Add content
frame_id = mem.put(text="content here", title="doc-id", label="tech.md", metadata={"key": "val"})

# Add with logic mesh (auto-extract entities/relationships)
mem.put(text="John works at Acme Corp.", logic_mesh=True)

# Manual SPO triplets
mem.add_memory_cards([
    {"entity": "Alice", "slot": "employer", "value": "Anthropic"},
    {"entity": "Alice", "slot": "role", "value": "Engineer"},
])

# Auto-extract SPO from existing content
mem.enrich()             # default engine
mem.enrich(engine="groq")  # or specific engine
mem.enrich("rules")      # rules-based extraction

# Persist changes (REQUIRED after writes)
mem.commit()
```

## Read Operations

```python
# Hybrid search (default)
results = mem.find("query text", k=10, mode="auto")

# Lexical-only search
results = mem.find("exact_function_name", k=5, mode="lex")

# Vector-only search
results = mem.find("conceptual query", mode="vec")

# Graph-filtered search
results = mem.find("quarterly report", graph_pattern="?:works_at:Acme Corp")

# Entity state — O(1) SPO lookup
state = mem.state("Alice")
# Returns: {"employer": "Anthropic", "role": "Engineer", ...}

# Get entity facts with history
facts = mem.get_facts(entity="Alice")
facts = mem.get_facts(entity="Alice", predicate="job_title")

# List all entities
entities = mem.get_entities()

# Graph traversal
graph = mem.traverse(start="Alice", link="works_at", hops=2, direction="outgoing")
```

## Search Modes
| Mode | When to use |
|------|-------------|
| `"auto"` | Default hybrid (lexical + vector). Best general-purpose. |
| `"lex"` | Exact keyword/identifier matching. No embeddings needed. |
| `"vec"` | Semantic similarity. Requires embedding model. |

## Embedding Models
Local (zero API cost): `bge-small`, `bge-base`, `nomic`, `gte-large`
Cloud: `openai-small`, `openai-large`
Default: fastembed for local embeddings

## Key Differences from Legacy API
- Class methods: `Memvid.create()` / `Memvid.use()` (not bare `create()` / `use()`)
- `mode="auto"` not `mode="hybrid"`
- `mode="lex"` not `mode="lexical"`
- Must call `mem.commit()` after writes
