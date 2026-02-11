---
name: type-invariants-spec
phase: 1
sprint: 2
parent: null
depends_on: [error-handling-spec]
status: completed
created: 2026-02-10
severity: P1-P2
finding_count: 8
---

# Type Invariants Spec

## Overview

8 findings about type design gaps. Models accept values that should be illegal: empty string IDs, negative token counts, bare dicts where structured models belong. One mutable default bug (shared list across instances). Two naming/duplication issues.

These don't crash the system today, but they create a class of bugs where invalid data flows through the pipeline and causes confusing failures downstream. Fixing the types turns runtime crashes into construction-time rejections.

## Requirements

- REQ-1: `VCSConfig.allowed_orgs` uses `Field(default_factory=list)` instead of `= []`
- REQ-2: All `component_id: str` fields reject empty strings (TechDoc, RepoMetadata, Job)
- REQ-3: Numeric config fields have bounds: `max_tokens > 0`, `timeout > 0`, `temperature 0.0-2.0`, etc.
- REQ-4: `MerkleNode.hash` validated as 12-char hex string
- REQ-5: `TechDoc.frontmatter` replaced with typed `FrontmatterModel`
- REQ-6: Two `LLMConfig` classes disambiguated (rename one)
- REQ-7: `MerkleNode`, `MerkleDiff` made immutable (frozen dataclass or Pydantic)
- REQ-8: `RepoMetadata.url` validated when non-empty

## Acceptance Criteria

- [ ] `VCSConfig(allowed_orgs=[])` → two instances don't share the same list object
- [ ] `TechDoc(component_id="")` raises `ValidationError`
- [ ] `RepoMetadata(component_id="")` raises `ValidationError`
- [ ] `Job(id="")` raises `ValidationError`
- [ ] `LLMConfig(max_tokens=-1)` raises `ValidationError`
- [ ] `LLMConfig(temperature=5.0)` raises `ValidationError`
- [ ] `LLMConfig(timeout=0)` raises `ValidationError`
- [ ] `MerkleNode(path="x", hash="nothex")` raises `ValueError` or `ValidationError`
- [ ] `TechDoc.frontmatter` is a `FrontmatterModel` with required `component_id`, `version`, `layer`
- [ ] No two classes named `LLMConfig` — one renamed to `LLMProviderConfig` or similar
- [ ] `MerkleNode.hash = "new"` raises `FrozenInstanceError` (if frozen)
- [ ] All existing tests pass (update any that construct models with invalid data)

## Files to Modify

| File | Change | Finding # |
|------|--------|-----------|
| `chronicler_core/config/models.py` | Fix mutable default, add Field(gt=0) bounds, rename LLMConfig | #3, #16, #27 |
| `chronicler_core/llm/models.py` | Add Field bounds, rename if needed | #16 |
| `chronicler_core/vcs/models.py` | Add component_id validator, url validator | #15, #34 |
| `chronicler_core/drafter/models.py` | Add component_id validator, define FrontmatterModel | #15, #26 |
| `chronicler_core/interfaces/queue.py` | Add Job.id validator, attempts bounds | #15 |
| `chronicler_core/merkle/models.py` | Freeze MerkleNode/MerkleDiff, add hash validator | #25, #33 |
| `chronicler_core/merkle/tree.py` | Update MerkleNode usage for frozen instances | #33 |
| `chronicler_core/merkle/scanner.py` | Update ScanResult/DiffResult for frozen if needed | #33 |
| Various `__init__.py` files | Update re-exports if class renamed | #27 |
| `tests/test_models.py` (new) | Validation tests for all type changes | all |

## Technical Approach

### Pydantic validator pattern

```python
from pydantic import BaseModel, Field, field_validator

class TechDoc(BaseModel):
    component_id: str = Field(min_length=1)
    # ...

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("component_id cannot be empty or whitespace")
        return v
```

### FrontmatterModel

```python
class FrontmatterModel(BaseModel):
    component_id: str = Field(min_length=1)
    version: str = "1.0"
    layer: str = "unknown"
    governance: str = "auto-generated"
    # optional fields
    depends_on: list[str] = Field(default_factory=list)
    depended_by: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
```

### Frozen dataclass for MerkleNode

```python
@dataclass(frozen=True)
class MerkleNode:
    path: str
    hash: str
    children: tuple[str, ...] = ()  # tuple instead of list for immutability
    stale: bool = False

    def __post_init__(self):
        if not re.fullmatch(r'[a-f0-9]{12}', self.hash):
            raise ValueError(f"hash must be 12-char hex, got {self.hash!r}")
```

Note: Making MerkleNode frozen requires updating tree.py to use `dataclasses.replace()` instead of direct mutation.

### LLMConfig rename

Rename `config/models.py:LLMConfig` → `LLMSettings` (this is the user-facing config from YAML).
Keep `llm/models.py:LLMConfig` as-is (this is the runtime provider config).
Update all imports across the codebase.

## Tasks

1. Fix mutable default in VCSConfig (finding #3)
2. Add `Field(min_length=1)` to all component_id/id fields (finding #15)
3. Add numeric bounds to all config/LLM model fields (finding #16)
4. Validate MerkleNode.hash format (finding #25)
5. Define FrontmatterModel, replace bare dict in TechDoc (finding #26)
6. Rename duplicate LLMConfig (finding #27)
7. Freeze MerkleNode/MerkleDiff, update tree.py to use replace() (finding #33)
8. Add URL validation to RepoMetadata (finding #34)
9. Update existing tests that construct models with now-invalid data
10. Write new validation tests

## Dependencies

- Upstream: error-handling-spec (error patterns like LLMError inform how validation errors surface)
- Downstream: architecture-cleanup-spec (refactors should use the new validated types)
