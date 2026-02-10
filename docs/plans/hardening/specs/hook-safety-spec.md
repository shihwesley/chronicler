---
name: hook-safety-spec
phase: 1
sprint: 1
parent: null
depends_on: []
status: pending
created: 2026-02-10
severity: P0
finding_count: 2
---

# Hook Safety Spec

## Overview

All three Chronicler hooks can crash with unhandled exceptions, which breaks Claude Code's session. Hooks MUST exit 0 under all conditions. When errors occur, they should log warnings (for debugging) but never propagate exceptions.

This is the #1 launch blocker. A hook that crashes on malformed JSON or a missing import makes the entire product worse than useless — it actively harms the user's workflow.

## Requirements

- REQ-1: Every hook's `main()` function has a top-level `try/except Exception` that catches all errors and calls `sys.exit(0)`
- REQ-2: Every catch-and-return site logs a warning with the error message before returning
- REQ-3: Hooks that import `chronicler_core` do so inside the try block, not at module level
- REQ-4: All existing hook tests still pass
- REQ-5: New tests verify hooks exit 0 when given malformed input, missing dependencies, and I/O errors

## Acceptance Criteria

- [ ] `post_write.py` has top-level try/except in `main()`, exits 0 on any error
- [ ] `pre_read_techmd.py` has top-level try/except in `main()`, exits 0 on any error
- [ ] `session_start.py` has top-level try/except in `main()`, exits 0 on any error
- [ ] JSON parse failures at `post_write.py:22` and `pre_read_techmd.py:20` log `logger.warning()` before returning
- [ ] All 41 existing hook tests pass
- [ ] New tests: hook given `{}` as input exits 0
- [ ] New tests: hook given invalid JSON exits 0
- [ ] New tests: hook given non-existent file path exits 0

## Files to Modify

| File | Change |
|------|--------|
| `packages/chronicler-lite/src/chronicler_lite/hooks/post_write.py` | Add top-level try/except, add warning logs |
| `packages/chronicler-lite/src/chronicler_lite/hooks/pre_read_techmd.py` | Add top-level try/except, add warning logs, move import inside try |
| `packages/chronicler-lite/src/chronicler_lite/hooks/session_start.py` | Add top-level try/except, move import inside try |
| `tests/test_hooks_skill.py` | Add error-path tests |

## Technical Approach

Pattern for each hook:

```python
import logging
import sys

logger = logging.getLogger("chronicler.hooks")

def main():
    try:
        # ... existing logic ...
    except Exception as e:
        logger.warning("chronicler %s hook failed: %s", __name__, e)
        sys.exit(0)
```

For silent-return sites (JSON parse, I/O):

```python
except (json.JSONDecodeError, OSError) as e:
    logger.warning("chronicler hook: skipping — %s", e)
    return
```

## Tasks

1. Add top-level exception guards to all 3 hooks
2. Add `logger.warning()` to all silent catch-and-return sites
3. Move `chronicler_core` imports inside try blocks (pre_read_techmd, session_start)
4. Write error-path tests (malformed input, missing deps, I/O errors)
5. Run full test suite, confirm 0 regressions

## Dependencies

- Upstream: none (this spec is independent)
- Downstream: type-invariants-spec (can start after this)
