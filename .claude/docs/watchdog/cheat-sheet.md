# Python watchdog Cheat Sheet

## Installation

```bash
pip install watchdog
# or
pip install watchdog[watchmedo]  # includes CLI utility
```

Requires Python 3.9+. Uses native OS APIs: FSEvents on macOS, inotify on Linux, Windows API on Windows. Falls back to polling if native isn't available.

## Core API

### Observer

The thread that watches the filesystem and dispatches events.

```python
from watchdog.observers import Observer

observer = Observer()                              # platform-native watcher
watch = observer.schedule(handler, path, recursive=False)  # returns ObservedWatch
observer.start()                                   # begins watching (non-blocking thread)
observer.stop()                                    # signals thread to stop
observer.join()                                    # waits for thread to finish
observer.unschedule(watch)                         # stop watching a specific path
observer.unschedule_all()                          # stop all watches
```

For explicit polling (cross-platform, slower):
```python
from watchdog.observers.polling import PollingObserver
observer = PollingObserver(timeout=1)  # poll interval in seconds
```

### Event Handlers

All handlers extend `FileSystemEventHandler`. Override the methods you need.

```python
from watchdog.events import FileSystemEventHandler

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):    ...  # file or dir created
    def on_modified(self, event):   ...  # file or dir modified
    def on_deleted(self, event):    ...  # file or dir deleted
    def on_moved(self, event):      ...  # file or dir moved/renamed
    def on_closed(self, event):     ...  # file closed (Linux only)
    def on_any_event(self, event):  ...  # catch-all, fires for every event
```

Each `event` has:
- `event.src_path` -- absolute path of the affected file/dir
- `event.event_type` -- string: `"created"`, `"modified"`, `"deleted"`, `"moved"`, `"closed"`
- `event.is_directory` -- bool
- `event.dest_path` -- only on moved events

### Event Classes

| Class | Trigger |
|---|---|
| `FileCreatedEvent` | New file |
| `FileModifiedEvent` | File content/metadata changed |
| `FileDeletedEvent` | File removed |
| `FileMovedEvent` | File renamed/moved (has `dest_path`) |
| `FileClosedEvent` | File handle closed (Linux) |
| `DirCreatedEvent` | New directory |
| `DirModifiedEvent` | Directory metadata changed |
| `DirDeletedEvent` | Directory removed |
| `DirMovedEvent` | Directory renamed/moved |

### PatternMatchingEventHandler

Filters events by filename glob patterns.

```python
from watchdog.events import PatternMatchingEventHandler

handler = PatternMatchingEventHandler(
    patterns=["*.md", "*.txt"],      # only these globs (None = all)
    ignore_patterns=["*.tmp", "~*"], # skip these
    ignore_directories=False,        # if True, skip dir events entirely
    case_sensitive=False
)
```

### RegexMatchingEventHandler

Same idea, regex instead of globs.

```python
from watchdog.events import RegexMatchingEventHandler

handler = RegexMatchingEventHandler(
    regexes=[r".*\.md$"],
    ignore_regexes=[r".*__pycache__.*"],
    ignore_directories=True,
    case_sensitive=False
)
```

## Usage Patterns

### 1. Basic directory watcher

```python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        print(f"{event.event_type}: {event.src_path}")

observer = Observer()
observer.schedule(LogHandler(), "/path/to/watch", recursive=True)
observer.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
```

### 2. Watch only Markdown files

```python
from watchdog.events import PatternMatchingEventHandler

class MarkdownHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(patterns=["*.md"], ignore_directories=True)

    def on_modified(self, event):
        print(f"Changed: {event.src_path}")

    def on_created(self, event):
        print(f"New file: {event.src_path}")
```

### 3. Watch multiple directories

```python
observer = Observer()
observer.schedule(handler, "/path/one", recursive=True)
observer.schedule(handler, "/path/two", recursive=False)
observer.start()
```

### 4. Debounce rapid file saves

Editors often trigger multiple modified events per save. Handle this yourself.

```python
import time
from watchdog.events import FileSystemEventHandler

class DebouncedHandler(FileSystemEventHandler):
    def __init__(self, delay=0.5):
        self._delay = delay
        self._last_event = {}

    def on_modified(self, event):
        now = time.time()
        last = self._last_event.get(event.src_path, 0)
        if now - last < self._delay:
            return
        self._last_event[event.src_path] = now
        self._handle(event)

    def _handle(self, event):
        print(f"Settled: {event.src_path}")
```

### 5. Graceful shutdown with context manager pattern

```python
from contextlib import contextmanager

@contextmanager
def watched(path, handler, recursive=True):
    observer = Observer()
    observer.schedule(handler, path, recursive=recursive)
    observer.start()
    try:
        yield observer
    finally:
        observer.stop()
        observer.join()

# Usage:
with watched("/my/dir", MyHandler()) as obs:
    while True:
        time.sleep(1)
```

## Common Pitfalls

- **Duplicate `on_modified` events.** Most editors save files in multiple steps (write temp, rename). You'll get 2-3 modified events per save. Debounce or deduplicate.
- **`recursive=False` is the default.** If you forget `recursive=True` in `observer.schedule()`, subdirectories won't be watched.
- **Large directories and polling.** `PollingObserver` gets slow with thousands of files. Use the default `Observer` (native) when possible.
- **Events fire on metadata changes too.** `on_modified` triggers for permission changes, not just content. Check file content hash if you need to distinguish.
- **macOS FSEvents latency.** Events can be delayed up to ~1 second on macOS due to the FSEvents API. Not suitable for sub-second reaction times.
- **Moved events across filesystems.** A move across mount points shows up as delete + create, not a single moved event.
- **Thread safety.** Handler callbacks run in the observer thread. If you do slow work, use a queue to hand off to another thread.

## Sources

- [PyPI](https://pypi.org/project/watchdog/)
- [GitHub](https://github.com/gorakhargosh/watchdog)
- [API Docs](https://python-watchdog.readthedocs.io/en/stable/api.html)
