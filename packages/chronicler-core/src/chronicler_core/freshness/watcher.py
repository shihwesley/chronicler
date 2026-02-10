"""File watcher with debounce for tracking source freshness."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# Directories and patterns to ignore when watching
_IGNORE_PARTS = {".git", "node_modules", "__pycache__", ".chronicler"}


def _should_ignore(path: str) -> bool:
    """Return True if the path contains any ignored directory component."""
    parts = Path(path).parts
    return any(part in _IGNORE_PARTS for part in parts)


class _DebouncedHandler(FileSystemEventHandler):
    """Buffers rapid filesystem events and fires the callback after quiet period."""

    def __init__(
        self,
        debounce_seconds: float,
        stale_paths: set[str],
        lock: threading.Lock,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__()
        self._debounce = debounce_seconds
        self._stale_paths = stale_paths
        self._lock = lock
        self._callback = callback
        self._last_event: dict[str, float] = {}

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = event.src_path
        if _should_ignore(src):
            return

        now = time.time()
        last = self._last_event.get(src, 0)
        if now - last < self._debounce:
            return
        self._last_event[src] = now

        with self._lock:
            self._stale_paths.add(src)

        if self._callback is not None:
            try:
                self._callback(event.event_type, src)
            except Exception:
                logger.exception("Watcher callback failed for %s", src)


class FreshnessWatcher:
    """Watches a project directory for file changes, tracking stale paths.

    Uses watchdog with a debounce window to avoid duplicate events from
    editor save patterns (temp file + rename). Ignores .git, node_modules,
    __pycache__, and .chronicler directories.
    """

    def __init__(
        self,
        project_path: Path,
        debounce_seconds: float = 2.0,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._project_path = Path(project_path).resolve()
        self._debounce_seconds = debounce_seconds
        self._callback = callback
        self._lock = threading.Lock()
        self._stale: set[str] = set()
        self._observer: Observer | None = None
        self._handler = _DebouncedHandler(
            debounce_seconds=debounce_seconds,
            stale_paths=self._stale,
            lock=self._lock,
            callback=callback,
        )

    @property
    def stale_paths(self) -> set[str]:
        """Current set of absolute paths detected as changed."""
        with self._lock:
            return set(self._stale)

    def start(self) -> None:
        """Begin watching the project directory recursively."""
        if self._observer is not None:
            return
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self._project_path),
            recursive=True,
        )
        self._observer.start()
        logger.info("Watching %s for changes", self._project_path)

    def stop(self) -> None:
        """Stop watching and clean up."""
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        logger.info("Stopped watching %s", self._project_path)

    def clear(self) -> None:
        """Reset the stale paths set."""
        with self._lock:
            self._stale.clear()
