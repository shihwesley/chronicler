"""ObsidianSync daemon — exports .tech.md files to an Obsidian vault."""

import hashlib
import os
import signal
import time
import logging
from pathlib import Path
from urllib.parse import quote

import yaml
import requests

from chronicler_core.config import ObsidianConfig
from chronicler_obsidian.models import SyncReport, SyncError

logger = logging.getLogger(__name__)


class ObsidianSync:
    def __init__(self, source_dir: str, vault_path: str, config: ObsidianConfig, pipeline):
        """
        Args:
            source_dir: Path to .chronicler/ directory with .tech.md files
            vault_path: Path to Obsidian vault directory
            config: ObsidianConfig with sync settings
            pipeline: TransformPipeline instance (passed in to avoid circular imports)
        """
        self.source_dir = Path(source_dir)
        self.vault_path = Path(vault_path)
        self.config = config
        self.pipeline = pipeline
        self._content_hashes: dict[str, str] = {}

    # -- Public API ----------------------------------------------------------

    def export(self) -> SyncReport:
        """One-shot sync: scan .tech.md files, transform, write to vault."""
        start = time.monotonic()
        report = SyncReport()

        for source_path in self.source_dir.rglob("*.tech.md"):
            rel = str(source_path.relative_to(self.source_dir))
            try:
                content = source_path.read_text()
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                if self._content_hashes.get(rel) == content_hash:
                    report.skipped += 1
                    continue

                metadata, _body = self._parse_frontmatter(content)
                transformed = self.pipeline.apply(content, metadata)

                vault_file = self.vault_path / rel.replace(".tech.md", ".md")
                if not vault_file.resolve().is_relative_to(self.vault_path.resolve()):
                    report.errors.append(SyncError(file=rel, error="Path traversal detected"))
                    continue
                vault_file.parent.mkdir(parents=True, exist_ok=True)
                vault_file.write_text(transformed)

                self._content_hashes[rel] = content_hash
                report.synced += 1
                logger.info(f"Synced: {rel}")
            except Exception as exc:
                report.errors.append(SyncError(file=rel, error=str(exc)))
                logger.error(f"Error syncing {rel}: {exc}")

        report.duration = time.monotonic() - start
        return report

    def watch(self) -> None:
        """File watcher mode: auto-sync on .tech.md changes."""
        from watchdog.observers import Observer
        from watchdog.events import PatternMatchingEventHandler

        sync_ref = self

        class TechMdHandler(PatternMatchingEventHandler):
            def __init__(self):
                super().__init__(patterns=["*.tech.md"], ignore_directories=True)
                self._last_event: dict[str, float] = {}
                self._debounce = 0.5

            def on_modified(self, event):
                self._handle(event)

            def on_created(self, event):
                self._handle(event)

            def on_deleted(self, event):
                rel = os.path.relpath(event.src_path, sync_ref.source_dir)
                vault_file = sync_ref.vault_path / rel.replace(".tech.md", ".md")
                if vault_file.exists():
                    vault_file.unlink()
                    logger.info(f"Deleted: {vault_file}")

            def _handle(self, event):
                now = time.time()
                last = self._last_event.get(event.src_path, 0)
                if now - last < self._debounce:
                    return
                self._last_event[event.src_path] = now
                sync_ref._sync_single_file(Path(event.src_path))

        observer = Observer()
        observer.schedule(TechMdHandler(), str(self.source_dir), recursive=True)
        observer.start()
        logger.info(f"Watching {self.source_dir} for changes... (Ctrl+C to stop)")

        stop = False

        def _signal_handler(sig, frame):
            nonlocal stop
            stop = True

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        try:
            while not stop:
                time.sleep(1)
        finally:
            observer.stop()
            observer.join()
            logger.info("Watcher stopped.")

    def sync_rest(self, api_url: str | None = None, token: str | None = None) -> SyncReport:
        """Sync transformed files to Obsidian via the Local REST API plugin."""
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = (api_url or self.config.rest_api.url).rstrip("/")
        tok = token or os.environ.get(self.config.rest_api.token_env)
        if not tok:
            raise ValueError(
                f"REST API token required: set {self.config.rest_api.token_env} "
                "env var or pass --token"
            )
        headers = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "text/markdown",
        }

        start = time.monotonic()
        report = SyncReport()

        for source_path in self.source_dir.rglob("*.tech.md"):
            rel = str(source_path.relative_to(self.source_dir))
            try:
                content = source_path.read_text()
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                if self._content_hashes.get(rel) == content_hash:
                    report.skipped += 1
                    continue

                metadata, _body = self._parse_frontmatter(content)
                transformed = self.pipeline.apply(content, metadata)

                vault_rel = rel.replace(".tech.md", ".md")
                safe_vault_rel = quote(vault_rel, safe="/")
                resp = requests.put(
                    f"{url}/vault/{safe_vault_rel}",
                    headers=headers,
                    data=transformed.encode("utf-8"),
                    verify=False,
                )
                resp.raise_for_status()

                self._content_hashes[rel] = content_hash
                report.synced += 1
                logger.info(f"PUT {vault_rel} -> {resp.status_code}")
            except Exception as exc:
                report.errors.append(SyncError(file=rel, error=str(exc)))
                logger.error(f"REST sync error for {rel}: {exc}")

        report.duration = time.monotonic() - start
        return report

    # -- Internals -----------------------------------------------------------

    def _sync_single_file(self, source_path: Path) -> bool:
        """Transform and write a single .tech.md file. Returns True on success."""
        try:
            content = source_path.read_text()
            metadata, _body = self._parse_frontmatter(content)
            transformed = self.pipeline.apply(content, metadata)

            rel = source_path.relative_to(self.source_dir)
            vault_file = self.vault_path / str(rel).replace(".tech.md", ".md")
            if not vault_file.resolve().is_relative_to(self.vault_path.resolve()):
                logger.error(f"Path traversal detected: {rel}")
                return False
            vault_file.parent.mkdir(parents=True, exist_ok=True)
            vault_file.write_text(transformed)

            self._content_hashes[str(rel)] = hashlib.sha256(content.encode()).hexdigest()
            logger.info(f"Synced: {rel}")
            return True
        except Exception as exc:
            logger.error(f"Error syncing {source_path}: {exc}")
            return False

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Extract YAML frontmatter and body from markdown content."""
        if not content.startswith("---"):
            return {}, content
        end = content.find("---", 3)
        if end == -1:
            return {}, content
        fm_text = content[3:end].strip()
        body = content[end + 3:].lstrip("\n")
        metadata = yaml.safe_load(fm_text) or {}
        return metadata, body
