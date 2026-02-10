---
name: architecture-cleanup-spec
phase: 2
sprint: 1
parent: null
depends_on: [error-handling-spec, type-invariants-spec]
status: pending
created: 2026-02-10
severity: P2
finding_count: 12
---

# Architecture Cleanup Spec

## Overview

12 findings about SOLID violations and architecture smells. The two biggest offenders are `ContextBuilder` (200+ lines, 10+ responsibilities) and `MerkleTree` (257 lines, 7 responsibilities). There's also dead code (RendererPlugin with zero implementations), an ISP violation (QueuePlugin protocol too broad), and several OCP violations (hardcoded parsers, sequential provider detection).

These don't affect correctness or security. They affect maintainability — how easy it is to add a new manifest format, swap a component, or test in isolation. Since Chronicler is heading toward public release, cleaning these up now prevents tech debt from compounding.

## Requirements

- REQ-1: `ContextBuilder` split into focused components (SRP)
- REQ-2: `MerkleTree` responsibilities separated (builder, differ, serializer)
- REQ-3: `QueuePlugin` protocol split into basic + dead letter (ISP)
- REQ-4: `RendererPlugin` removed (YAGNI — no implementations exist)
- REQ-5: Dependency parsing made extensible (OCP)
- REQ-6: Drafter data clumps resolved (pass CrawlResult instead of unpacked fields)
- REQ-7: All refactors are behavior-preserving — existing tests must pass without changes to test logic

## Acceptance Criteria

- [ ] `drafter/context.py` under 100 lines, delegates to extracted classes
- [ ] New files: `drafter/dependency_parser.py`, `drafter/file_tree.py`, `drafter/key_files.py`
- [ ] `merkle/tree.py` under 150 lines for the core class
- [ ] New files: `merkle/builder.py`, `merkle/differ.py` (serializer can stay in tree.py)
- [ ] `interfaces/renderer.py` deleted
- [ ] `interfaces/queue.py` has `BasicQueue` and `DeadLetterQueue` protocols
- [ ] `drafter/drafter.py` passes `CrawlResult` to frontmatter/graph instead of unpacked fields
- [ ] Adding a new manifest parser (e.g., Cargo.toml) requires only adding a file, not editing existing code
- [ ] All 496+ existing tests pass without test-logic changes

## Files to Modify

| File | Change | Finding # |
|------|--------|-----------|
| `chronicler_core/drafter/context.py` | Extract 3 classes, keep as thin orchestrator | #14 |
| `chronicler_core/drafter/dependency_parser.py` (new) | DependencyParser protocol + implementations per manifest | #14, #21 |
| `chronicler_core/drafter/file_tree.py` (new) | FileTreeFormatter extracted from ContextBuilder | #14 |
| `chronicler_core/drafter/key_files.py` (new) | KeyFileLocator extracted from ContextBuilder | #14 |
| `chronicler_core/drafter/drafter.py` | Pass CrawlResult instead of unpacked tuple | #29 |
| `chronicler_core/drafter/frontmatter.py` | Accept CrawlResult parameter | #29 |
| `chronicler_core/drafter/graph.py` | Accept CrawlResult parameter | #29 |
| `chronicler_core/merkle/tree.py` | Extract builder and differ logic | #19, #20 |
| `chronicler_core/merkle/builder.py` (new) | MerkleTreeBuilder with build() method | #19, #20 |
| `chronicler_core/merkle/differ.py` (new) | MerkleTreeDiffer with diff()/drift() | #19 |
| `chronicler_core/interfaces/queue.py` | Split QueuePlugin → BasicQueue + DeadLetterQueue | #22 |
| `chronicler_core/interfaces/renderer.py` | DELETE this file | #23 |
| `chronicler_core/interfaces/__init__.py` | Remove RendererPlugin export | #23 |

## Technical Approach

### ContextBuilder decomposition

```python
# drafter/dependency_parser.py
class DependencyParser(Protocol):
    file_pattern: str
    def parse(self, content: str) -> list[str]: ...

class RequirementsTxtParser:
    file_pattern = "requirements*.txt"
    def parse(self, content: str) -> list[str]: ...

class PyprojectTomlParser:
    file_pattern = "pyproject.toml"
    def parse(self, content: str) -> list[str]: ...

# Registry pattern for OCP
PARSERS: list[DependencyParser] = [RequirementsTxtParser(), PyprojectTomlParser()]
```

```python
# drafter/context.py (after refactor — thin orchestrator)
class ContextBuilder:
    def __init__(self, parsers=None):
        self._parsers = parsers or PARSERS
        self._tree_formatter = FileTreeFormatter()
        self._key_locator = KeyFileLocator()

    def build(self, crawl_result: CrawlResult) -> str:
        sections = [
            self._tree_formatter.format(crawl_result.tree),
            self._key_locator.summarize(crawl_result.key_files),
            self._build_dependencies(crawl_result.key_files),
        ]
        return "\n\n".join(s for s in sections if s)
```

### QueuePlugin split

```python
@runtime_checkable
class BasicQueue(Protocol):
    async def enqueue(self, payload: dict, priority: int = 0) -> str: ...
    async def dequeue(self) -> Job | None: ...
    async def ack(self, job_id: str) -> None: ...
    async def nack(self, job_id: str) -> None: ...

@runtime_checkable
class DeadLetterQueue(Protocol):
    async def dead_letters(self, limit: int = 100) -> list[Job]: ...

# Existing implementations that support dead letters implement both
# Simple implementations only need BasicQueue
```

### MerkleTree decomposition

Keep `MerkleTree` as the data holder (nodes dict, root hash, load/save). Extract:
- `MerkleTreeBuilder.build(root, config)` → returns `MerkleTree`
- `MerkleTreeDiffer.diff(old, new)` → returns `MerkleDiff`
- `MerkleTreeDiffer.drift(tree)` → returns list of stale nodes

## Tasks

1. Extract `DependencyParser` protocol + concrete parsers from ContextBuilder (findings #14, #21)
2. Extract `FileTreeFormatter` from ContextBuilder (finding #14)
3. Extract `KeyFileLocator` from ContextBuilder (finding #14)
4. Slim down ContextBuilder to orchestrator (finding #14)
5. Refactor drafter to pass CrawlResult instead of unpacked fields (finding #29)
6. Extract `MerkleTreeBuilder` from MerkleTree (findings #19, #20)
7. Extract `MerkleTreeDiffer` from MerkleTree (finding #19)
8. Split QueuePlugin protocol (finding #22)
9. Delete RendererPlugin (finding #23)
10. Run full test suite, fix any import path changes

## Lower-Priority Items (P3, fix if touching the file)

- `llm/auto_detect.py`: sequential if/elif for providers → registry pattern (finding #30)
- `converter/converter.py`: 43-line convert() → split validation/conversion/cache (finding #31)
- `drafter/graph.py`: feature envy in `_detect_infrastructure()` → move to utility (finding #32)

## Dependencies

- Upstream: error-handling-spec (new LLMError informs adapter refactors), type-invariants-spec (frozen models used in tree refactor)
- Downstream: none (this is the final spec)
