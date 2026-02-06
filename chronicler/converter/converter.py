"""Document-to-markdown converter wrapping MarkItDown with caching."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import IO, Any

from chronicler.config.models import DocumentConversionConfig
from chronicler.converter.models import ConversionResult

logger = logging.getLogger(__name__)

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None  # type: ignore[assignment,misc]
    logger.warning("markitdown not installed — document conversion disabled")


DOCUMENT_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdfminer.six",
    ".docx": "mammoth",
    ".pptx": "python-pptx",
    ".xlsx": "openpyxl",
    ".xls": "xlrd",
    ".html": "beautifulsoup4",
}

IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

_FORMAT_FLAG_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
}


def should_convert(file_path: str | Path, config: DocumentConversionConfig) -> bool:
    """Check whether a file should be converted based on config."""
    if not config.enabled:
        return False

    ext = Path(file_path).suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return config.formats.images and config.ocr.enabled

    flag = _FORMAT_FLAG_MAP.get(ext)
    if flag and getattr(config.formats, flag, False):
        return True

    # HTML always enabled if extension is in DOCUMENT_EXTENSIONS
    if ext == ".html":
        return True

    return False


class DocumentConverter:
    """Wraps MarkItDown with file-based caching and error resilience."""

    def __init__(
        self,
        config: DocumentConversionConfig,
        llm_client: Any = None,
    ) -> None:
        self._config = config
        self._llm_client = llm_client

    @cached_property
    def _md(self) -> MarkItDown | None:
        if MarkItDown is None:
            return None

        kwargs: dict[str, Any] = {"enable_plugins": True}
        if self._config.ocr.use_llm and self._llm_client is not None:
            kwargs["llm_client"] = self._llm_client
        return MarkItDown(**kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, file_path: str | Path) -> ConversionResult | None:
        """Convert a document file to markdown. Returns None on any error."""
        if self._md is None:
            logger.warning("markitdown unavailable — skipping %s", file_path)
            return None

        path = Path(file_path).resolve()
        ext = path.suffix.lower()

        if not path.is_file():
            logger.warning("File not found: %s", path)
            return None

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self._config.max_file_size_mb:
            logger.warning("File too large (%.1f MB): %s", size_mb, path)
            return None

        fmt = ext.lstrip(".")
        cache_key = self._cache_key(path)

        # Check cache
        cached = self._read_cache(cache_key)
        if cached is not None:
            return ConversionResult(
                source_path=str(path),
                markdown=cached,
                format=fmt,
                cached=True,
            )

        try:
            result = self._md.convert(str(path))
            markdown = result.markdown
        except Exception:
            logger.warning("Conversion failed for %s", path, exc_info=True)
            return None

        self._write_cache(cache_key, markdown, path, fmt)
        return ConversionResult(
            source_path=str(path),
            markdown=markdown,
            format=fmt,
        )

    def convert_stream(
        self, stream: IO[bytes], filename: str
    ) -> ConversionResult | None:
        """Convert a binary stream to markdown."""
        if self._md is None:
            logger.warning("markitdown unavailable — skipping stream %s", filename)
            return None

        ext = Path(filename).suffix.lower()
        fmt = ext.lstrip(".")

        try:
            result = self._md.convert_stream(stream, file_extension=ext)
            markdown = result.markdown
        except Exception:
            logger.warning("Stream conversion failed for %s", filename, exc_info=True)
            return None

        return ConversionResult(
            source_path=filename,
            markdown=markdown,
            format=fmt,
        )

    # ------------------------------------------------------------------
    # Cache internals
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(path: Path) -> str:
        stat = path.stat()
        content = f"{path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _cache_dir(self) -> Path:
        return Path(self._config.cache.directory)

    def _manifest_path(self) -> Path:
        return self._cache_dir() / "manifest.json"

    def _load_manifest(self) -> dict:
        mp = self._manifest_path()
        if mp.is_file():
            try:
                return json.loads(mp.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt cache manifest — rebuilding")
        return {"version": 1, "entries": {}}

    def _save_manifest(self, manifest: dict) -> None:
        mp = self._manifest_path()
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(manifest, indent=2))

    def _read_cache(self, key: str) -> str | None:
        if not self._config.cache.enabled:
            return None

        manifest = self._load_manifest()
        entry = manifest.get("entries", {}).get(key)
        if entry is None:
            return None

        # TTL check
        converted_at = datetime.fromisoformat(entry["converted_at"])
        age_days = (datetime.now(timezone.utc) - converted_at).days
        if age_days > self._config.cache.ttl_days:
            return None

        cached_file = self._cache_dir() / f"{key}.md"
        if not cached_file.is_file():
            return None

        return cached_file.read_text()

    def _write_cache(
        self, key: str, markdown: str, source: Path, fmt: str
    ) -> None:
        if not self._config.cache.enabled:
            return

        try:
            cache_dir = self._cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)

            (cache_dir / f"{key}.md").write_text(markdown)

            manifest = self._load_manifest()
            manifest["entries"][key] = {
                "source": str(source),
                "converted_at": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(markdown.encode()),
                "format": fmt,
            }
            self._save_manifest(manifest)
        except OSError:
            logger.warning("Failed to write cache for %s", source, exc_info=True)
