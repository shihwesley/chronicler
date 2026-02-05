# MemVid Integration Design

## Overview

Replace Chronicler's storage/search layer with MemVid's `.mv2` format, gaining:
- Hybrid search (lexical + vector + time)
- Built-in knowledge graph via Memory Cards (SPO triplets)
- Single portable file, no database server
- Time-travel for documentation history

## Why MemVid for Chronicler

| Current Plan | With MemVid |
|--------------|-------------|
| JSON graph (Lite) | `.mv2` with Memory Cards |
| Neo4j (Enterprise) | Can still use Neo4j, or `.mv2` for smaller deployments |
| Separate search index | Built into `.mv2` |
| Manual versioning | Time-indexed frames automatic |

## Architecture

```mermaid
flowchart TB
    subgraph Chronicler["Chronicler Pipeline"]
        VCS[VCS Crawler] --> DOC[Document Converter]
        DOC --> AI[AI Drafter]
        AI --> GEN[.tech.md Generator]
    end

    subgraph MemVid["MemVid Storage"]
        MV2[chronicler.mv2]
        LEX[Lexical Index<br/>BM25]
        VEC[Vector Index<br/>HNSW]
        TIME[Time Index<br/>Frames]
        SPO[Memory Cards<br/>SPO Triplets]

        MV2 --> LEX
        MV2 --> VEC
        MV2 --> TIME
        MV2 --> SPO
    end

    GEN --> |put()| MV2

    subgraph Query["Query Layer"]
        SEARCH[find()<br/>hybrid search]
        STATE[state()<br/>entity lookup]
        TIMELINE[timeline()<br/>history]
    end

    MV2 --> SEARCH
    MV2 --> STATE
    MV2 --> TIMELINE
```

## .tech.md → MemVid Mapping

### Document Storage

```python
from memvid import create

# Create Chronicler memory file
mem = create("chronicler.mv2", embedding="bge_small")

# Store a .tech.md document
mem.put(
    title="auth-service.api.tech.md",
    text=tech_md_content,
    label="tech.md",
    meta={
        "component_id": "auth-service",
        "layer": "api",
        "owner_team": "platform",
        "version": "1.2.0",
        "repo": "myorg/auth-service"
    }
)
```

### Memory Cards (SPO Triplets)

Extract relationships from `.tech.md` YAML frontmatter → Memory Cards:

```python
# .tech.md edges become SPO triplets
edges = [
    {"target": "postgres", "relationship": "DEPENDS_ON"},
    {"target": "redis", "relationship": "CONSUMES"},
    {"target": "user-service", "relationship": "TRIGGERS"}
]

# Enrich with entity facts
mem.enrich(
    doc_id="auth-service.api.tech.md",
    cards=[
        {"subject": "auth-service", "predicate": "DEPENDS_ON", "object": "postgres"},
        {"subject": "auth-service", "predicate": "CONSUMES", "object": "redis"},
        {"subject": "auth-service", "predicate": "TRIGGERS", "object": "user-service"},
        {"subject": "auth-service", "predicate": "OWNED_BY", "object": "platform"},
        {"subject": "auth-service", "predicate": "LAYER", "object": "api"},
    ]
)
```

### Querying

```python
from memvid import use

mem = use("chronicler.mv2")

# Hybrid search (lexical + vector)
results = mem.find("authentication flow", k=10, mode="hybrid")

# Entity state lookup (O(1) via SlotIndex)
auth_state = mem.state("auth-service")
# Returns: {"DEPENDS_ON": ["postgres"], "CONSUMES": ["redis"], ...}

# What depends on postgres?
deps = mem.find("DEPENDS_ON postgres", mode="lexical")

# Timeline: what changed in last 7 days?
changes = mem.timeline(since="7d")
```

## MemVid + Knowledge Graph Synergy

### Option A: MemVid as Primary (Lite)

For Chronicler Lite, use MemVid's Memory Cards as the knowledge graph:

```
.mv2 file contains:
├── Documents (all .tech.md content)
├── Lexical Index (BM25 for keyword search)
├── Vector Index (semantic similarity)
├── Time Index (version history)
└── Memory Cards (SPO triplets = knowledge graph)
```

**Query examples:**
```python
# "What's the blast radius if I change postgres?"
affected = mem.find("DEPENDS_ON postgres OR CONSUMES postgres", mode="lexical")

# "Show me all P0 critical services"
critical = mem.find("business_impact P0", mode="lexical")

# Semantic: "services that handle user data"
user_data = mem.find("user authentication login session", mode="vector")
```

### Option B: MemVid + Neo4j (Enterprise)

For Enterprise, sync Memory Cards to Neo4j for advanced graph queries:

```python
# MemVid → Neo4j sync
def sync_to_neo4j(mem, neo4j_driver):
    for card in mem.list_cards():
        neo4j_driver.execute(
            "MERGE (s:Component {id: $subject}) "
            "MERGE (o:Component {id: $object}) "
            "MERGE (s)-[r:$predicate]->(o)",
            subject=card.subject,
            predicate=card.predicate,
            object=card.object
        )
```

**Benefits:**
- MemVid = fast local search, portable
- Neo4j = complex graph traversals, visualization
- Sync keeps both in sync

## Storage Layout

### Two-Layer Architecture

| Layer | Files | Purpose | Git-tracked |
|-------|-------|---------|-------------|
| Source | `.tech.md` | Human-readable, diffable | ✅ Yes |
| Index | `.mv2` | Search, embeddings, graph | ✅ Yes |

**Why both:**
- `.tech.md` = diffable in PRs, human review
- `.mv2` = fast search (sub-5ms), portable index
- `.mv2` can be rebuilt from `.tech.md` if needed

### Chronicler Lite

```
project/
├── .chronicler/
│   ├── chronicler.mv2              # Search index (git-tracked)
│   ├── auth-service.api.tech.md    # Source files (git-tracked)
│   ├── user-service.api.tech.md
│   └── config.yaml
└── src/
    └── ...
```

### Chronicler Enterprise

```
organization/
├── chronicler-global.mv2       # Org-wide searchable index
├── projects/
│   ├── auth-service/
│   │   └── .chronicler/
│   │       └── chronicler.mv2  # Project-local memory
│   └── user-service/
│       └── .chronicler/
│           └── chronicler.mv2
└── neo4j/                      # Graph DB for complex queries
```

## API Design

### ChroniclerMemory class

```python
from memvid import create, use

class ChroniclerMemory:
    """Wrapper around MemVid for .tech.md storage."""

    def __init__(self, path: str = ".chronicler/chronicler.mv2"):
        self.path = path
        self.mem = use(path) if Path(path).exists() else create(path)

    def store_tech_doc(self, doc: TechDoc) -> None:
        """Store a .tech.md document."""
        self.mem.put(
            title=doc.filename,
            text=doc.content,
            label="tech.md",
            meta=doc.frontmatter
        )
        # Extract edges as Memory Cards
        self._enrich_edges(doc)

    def _enrich_edges(self, doc: TechDoc) -> None:
        """Convert edges to SPO triplets."""
        cards = []
        for edge in doc.frontmatter.get("edges", []):
            cards.append({
                "subject": doc.component_id,
                "predicate": edge["relationship"],
                "object": edge["target"]
            })
        if cards:
            self.mem.enrich(doc_id=doc.filename, cards=cards)

    def search(self, query: str, k: int = 10, mode: str = "hybrid") -> list[TechDoc]:
        """Search documents."""
        results = self.mem.find(query, k=k, mode=mode)
        return [TechDoc.from_result(r) for r in results]

    def get_dependencies(self, component_id: str) -> dict:
        """Get all relationships for a component."""
        return self.mem.state(component_id)

    def get_affected_by(self, component_id: str) -> list[str]:
        """Find what depends on this component (blast radius)."""
        results = self.mem.find(f"DEPENDS_ON {component_id}", mode="lexical")
        return [r.meta["component_id"] for r in results]

    def history(self, component_id: str, since: str = "30d") -> list[dict]:
        """Get change history for a component."""
        return self.mem.timeline(filter=component_id, since=since)
```

## Configuration

### chronicler.yaml

```yaml
storage:
  type: memvid  # or "json" for legacy, "neo4j" for enterprise
  path: .chronicler/chronicler.mv2

  memvid:
    embedding: bge_small  # local, no API key needed
    # Or use cloud embeddings:
    # embedding: openai
    # api_key: ${OPENAI_API_KEY}

  # Enterprise: sync to Neo4j
  neo4j_sync:
    enabled: false
    uri: ${NEO4J_URI}
    user: ${NEO4J_USER}
    password: ${NEO4J_PASSWORD}
```

## Pre-Implementation Research (MANDATORY)

Before coding, the implementing agent MUST fetch and analyze:

| Resource | URL | Purpose |
|----------|-----|---------|
| Python SDK | https://docs.memvid.com/sdks/python | API reference, methods, parameters |
| Glossary | https://docs.memvid.com/introduction/glossary | Terminology (frames, Memory Cards, etc.) |
| Examples | https://docs.memvid.com/resources/examples | Real-world use cases |
| GitHub | https://github.com/memvid/memvid | Source code, README, latest changes |

**Why mandatory:** MemVid API may have evolved since this planning doc was written. Always fetch latest docs before implementing.

## Implementation Phases

### Phase 5.1: MemVid as Chronicler Lite Storage
- Replace JSON graph with MemVid
- Implement `ChroniclerMemory` wrapper
- Store `.tech.md` with embeddings
- Extract edges as Memory Cards

### Phase 5.2: Search Layer
- Expose hybrid search via CLI
- Add `chronicler search "query"` command
- Add `chronicler deps <component>` for blast radius

### Phase 6: Enterprise Sync
- Optional Neo4j sync for complex queries
- Mnemon reads from Neo4j for 3D visualization
- MemVid remains source of truth

## Dependencies

```toml
[project.optional-dependencies]
memvid = [
    "memvid-sdk>=0.1.0",
]
```

## Testing

```python
def test_store_and_search():
    mem = ChroniclerMemory(":memory:")  # In-memory for tests

    doc = TechDoc(
        filename="auth-service.api.tech.md",
        component_id="auth-service",
        content="Authentication service handling OAuth2...",
        frontmatter={
            "edges": [{"target": "postgres", "relationship": "DEPENDS_ON"}]
        }
    )

    mem.store_tech_doc(doc)

    # Search works
    results = mem.search("authentication OAuth", k=5)
    assert len(results) == 1
    assert results[0].component_id == "auth-service"

    # Memory Cards work
    state = mem.get_dependencies("auth-service")
    assert "DEPENDS_ON" in state
    assert "postgres" in state["DEPENDS_ON"]

def test_blast_radius():
    mem = ChroniclerMemory(":memory:")

    # auth depends on postgres
    mem.store_tech_doc(TechDoc(
        component_id="auth-service",
        frontmatter={"edges": [{"target": "postgres", "relationship": "DEPENDS_ON"}]}
    ))

    # user-service depends on postgres
    mem.store_tech_doc(TechDoc(
        component_id="user-service",
        frontmatter={"edges": [{"target": "postgres", "relationship": "DEPENDS_ON"}]}
    ))

    # What's affected if postgres changes?
    affected = mem.get_affected_by("postgres")
    assert "auth-service" in affected
    assert "user-service" in affected
```

## Security Considerations

- MemVid supports encryption for `.mv2` files
- Embeddings can use local models (no data sent to cloud)
- File-level access control via filesystem permissions
