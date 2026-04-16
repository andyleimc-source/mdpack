"""PDF → Markdown via Docling (non-OCR mode).

Docling's `DocumentConverter` loads ~1GB of torch + transformers on first use.
We cache one instance at module level so converting N PDFs touches the model
once, not N times. The cache is thread-safe; a failed instantiation leaves the
slot empty so the next call can retry.

Files larger than ``PDF_HARD_CAP_BYTES`` are refused defensively in case the
caller bypassed the Scanner-level cap (e.g. watch mode passing a single file
straight to ``convert``).
"""

from __future__ import annotations

import threading
from pathlib import Path

from ..utils import strip_base64_images
from .base import ConversionError, ConvertResult

PDF_HARD_CAP_BYTES: int = 50 * 1024 * 1024

_converter_singleton: object | None = None
_converter_lock = threading.Lock()


def _get_docling_converter():
    global _converter_singleton
    if _converter_singleton is None:
        with _converter_lock:
            if _converter_singleton is None:
                from docling.document_converter import DocumentConverter
                _converter_singleton = DocumentConverter()
    return _converter_singleton


def _reset_singleton_for_tests() -> None:
    """Test-only hook to clear the cached converter."""
    global _converter_singleton
    _converter_singleton = None


class PdfConverter:
    name = "pdf"
    extensions = (".pdf",)

    def convert(self, src: Path) -> ConvertResult:
        try:
            size = src.stat().st_size
        except OSError as e:
            raise ConversionError(src, f"cannot stat: {e}") from e
        if size > PDF_HARD_CAP_BYTES:
            mb = size / (1024 * 1024)
            raise ConversionError(
                src,
                f"skipped: {mb:.1f} MB exceeds the {PDF_HARD_CAP_BYTES // (1024*1024)} MB "
                f"PDF cap (raise --pdf-max-size to override)",
            )

        try:
            converter = _get_docling_converter()
        except ImportError as e:
            raise ConversionError(
                src,
                "docling is not installed — PDF support is optional.\n"
                "  Install with:  pip install 'mdpack[pdf]'\n"
                "  (pulls torch + transformers, ~1GB download on first run.)",
            ) from e

        try:
            result = converter.convert(str(src))
            markdown = result.document.export_to_markdown()
        except Exception as e:
            raise ConversionError(src, f"docling failed: {type(e).__name__}: {e}") from e

        body, stripped = strip_base64_images(markdown)
        warnings: list[str] = []
        if stripped:
            warnings.append(f"stripped {stripped} inline base64 image(s)")

        return ConvertResult(body=body, title=src.stem, warnings=warnings)
