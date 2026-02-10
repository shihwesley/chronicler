#!/bin/bash
# Run from: /Users/quartershots/Source/Chronicler
# Verifies and commits phases 5c + 5d
set -euo pipefail
cd /Users/quartershots/Source/Chronicler
export PATH="$HOME/.local/bin:$PATH"

echo "=== Cleanup stale worktrees ==="
git worktree prune
git branch -d orchestrate/phase-5b-plugin-interfaces 2>/dev/null || true
git branch -d orchestrate/phase-5c-memvid-storage 2>/dev/null || true
git branch -d orchestrate/phase-5d-sqlite-queue 2>/dev/null || true

echo "=== Sync dependencies ==="
uv sync --extra dev

echo "=== Run 5c tests (MemVid storage) ==="
uv run pytest tests/test_memvid_storage.py -v

echo "=== Run 5d tests (SQLite queue) ==="
uv run pytest tests/test_sqlite_queue.py -v

echo "=== Run ALL tests ==="
uv run pytest tests/ -v

echo "=== Commit 5c + 5d ==="
git add packages/chronicler-lite/ tests/test_memvid_storage.py tests/test_sqlite_queue.py pyproject.toml uv.lock .claude/
git commit -m "orchestrate(5c+5d): add MemVid storage and SQLite queue

Phase 5c: MemVidStorage implementing StoragePlugin Protocol.
  - store/search/get/state with MemVid SDK v2 API
  - frontmatter-to-SPO enrichment and rebuild from .tech.md
  - 19 tests (mocked SDK)

Phase 5d: SQLiteQueue implementing QueuePlugin Protocol.
  - WAL mode, atomic dequeue via BEGIN IMMEDIATE
  - Retry logic (max 3 attempts before dead letter)
  - 13 tests including concurrent safety

Both housed in packages/chronicler-lite/ (new workspace member).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo "=== Done ==="
git log --oneline -3
