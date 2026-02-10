"""Tests for the converter subsystem: should_convert, DocumentConverter, cache."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from chronicler_core.config.models import (
    DocumentConversionConfig,
    FormatConfig,
    OCRConfig,
    DocCacheConfig,
)
from chronicler_core.converter.converter import should_convert, DocumentConverter
from chronicler_core.converter.models import ConversionResult


# ---------------------------------------------------------------------------
# should_convert
# ---------------------------------------------------------------------------


class TestShouldConvert:
    def _config(self, enabled=True, **fmt_kwargs):
        formats = FormatConfig(**fmt_kwargs) if fmt_kwargs else FormatConfig()
        return DocumentConversionConfig(enabled=enabled, formats=formats)

    def test_disabled_returns_false(self):
        config = self._config(enabled=False)
        assert should_convert("doc.pdf", config) is False

    def test_pdf_enabled(self):
        config = self._config(pdf=True)
        assert should_convert("doc.pdf", config) is True

    def test_pdf_disabled(self):
        config = self._config(pdf=False)
        assert should_convert("doc.pdf", config) is False

    def test_docx_enabled(self):
        config = self._config(docx=True)
        assert should_convert("report.docx", config) is True

    def test_pptx_enabled(self):
        config = self._config(pptx=True)
        assert should_convert("slides.pptx", config) is True

    def test_xlsx_disabled_by_default(self):
        config = self._config()
        assert should_convert("data.xlsx", config) is False

    def test_xlsx_enabled(self):
        config = self._config(xlsx=True)
        assert should_convert("data.xlsx", config) is True

    def test_html_always_converts(self):
        config = self._config()
        assert should_convert("page.html", config) is True

    def test_unknown_extension_returns_false(self):
        config = self._config()
        assert should_convert("file.xyz", config) is False

    def test_image_with_ocr_enabled(self):
        config = DocumentConversionConfig(
            enabled=True,
            formats=FormatConfig(images=True),
            ocr=OCRConfig(enabled=True),
        )
        assert should_convert("photo.png", config) is True

    def test_image_with_ocr_disabled(self):
        config = DocumentConversionConfig(
            enabled=True,
            formats=FormatConfig(images=True),
            ocr=OCRConfig(enabled=False),
        )
        assert should_convert("photo.png", config) is False

    def test_case_insensitive_extension(self):
        config = self._config(pdf=True)
        assert should_convert("DOC.PDF", config) is True


# ---------------------------------------------------------------------------
# DocumentConverter
# ---------------------------------------------------------------------------


class TestDocumentConverter:
    def test_convert_returns_none_without_markitdown(self, tmp_path):
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=False),
        )
        converter = DocumentConverter(config)

        # Force _md to None (markitdown not installed)
        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=None
        ):
            result = converter.convert(tmp_path / "test.pdf")
            assert result is None

    def test_convert_nonexistent_file(self, tmp_path):
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=False),
        )
        converter = DocumentConverter(config)

        mock_md = MagicMock()
        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            result = converter.convert(tmp_path / "nonexistent.pdf")
            assert result is None

    def test_convert_file_too_large(self, tmp_path):
        config = DocumentConversionConfig(
            max_file_size_mb=0,  # 0 MB limit
            cache=DocCacheConfig(enabled=False),
        )
        converter = DocumentConverter(config)

        # Create a small file that exceeds the 0 MB limit
        f = tmp_path / "big.pdf"
        f.write_bytes(b"x" * 100)

        mock_md = MagicMock()
        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            result = converter.convert(f)
            assert result is None

    def test_convert_success(self, tmp_path):
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=False),
        )
        converter = DocumentConverter(config)

        f = tmp_path / "test.pdf"
        f.write_bytes(b"fake pdf content")

        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.markdown = "# Converted content"
        mock_md.convert.return_value = mock_result

        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            result = converter.convert(f)
            assert isinstance(result, ConversionResult)
            assert result.markdown == "# Converted content"
            assert result.format == "pdf"
            assert result.cached is False
            assert result.source_path == str(f.resolve())

    def test_convert_exception_returns_none(self, tmp_path):
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=False),
        )
        converter = DocumentConverter(config)

        f = tmp_path / "bad.pdf"
        f.write_bytes(b"corrupted")

        mock_md = MagicMock()
        mock_md.convert.side_effect = RuntimeError("parse failure")

        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            result = converter.convert(f)
            assert result is None


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


class TestDocumentConverterCache:
    def test_cache_write_and_read(self, tmp_path):
        cache_dir = tmp_path / "cache"
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=True, directory=str(cache_dir), ttl_days=30),
        )
        converter = DocumentConverter(config)

        f = tmp_path / "test.pdf"
        f.write_bytes(b"fake pdf")

        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.markdown = "# Cached content"
        mock_md.convert.return_value = mock_result

        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            # First call: writes to cache
            result1 = converter.convert(f)
            assert result1.cached is False

            # Second call: reads from cache
            result2 = converter.convert(f)
            assert result2.cached is True
            assert result2.markdown == "# Cached content"

            # MarkItDown only called once (second read from cache)
            assert mock_md.convert.call_count == 1

    def test_cache_disabled_no_files(self, tmp_path):
        cache_dir = tmp_path / "cache"
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=False, directory=str(cache_dir)),
        )
        converter = DocumentConverter(config)

        f = tmp_path / "test.pdf"
        f.write_bytes(b"fake pdf")

        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.markdown = "# Content"
        mock_md.convert.return_value = mock_result

        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            converter.convert(f)
            # Cache dir should not be created when cache is disabled
            assert not cache_dir.exists() or not list(cache_dir.iterdir())

    def test_manifest_structure(self, tmp_path):
        cache_dir = tmp_path / "cache"
        config = DocumentConversionConfig(
            cache=DocCacheConfig(enabled=True, directory=str(cache_dir), ttl_days=30),
        )
        converter = DocumentConverter(config)

        f = tmp_path / "doc.pdf"
        f.write_bytes(b"fake")

        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.markdown = "md text"
        mock_md.convert.return_value = mock_result

        with patch.object(
            type(converter), "_md", new_callable=PropertyMock, return_value=mock_md
        ):
            converter.convert(f)

        manifest = json.loads((cache_dir / "manifest.json").read_text())
        assert "version" in manifest
        assert "entries" in manifest
        assert len(manifest["entries"]) == 1

        entry = list(manifest["entries"].values())[0]
        assert "converted_at" in entry
        assert "size_bytes" in entry
        assert "format" in entry
