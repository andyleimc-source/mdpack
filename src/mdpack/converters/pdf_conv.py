"""PDF → Markdown via Docling (non-OCR mode)."""

from __future__ import annotations

from pathlib import Path

from ..utils import strip_base64_images
from .base import ConversionError, ConvertResult


class PdfConverter:
    name = "pdf"
    extensions = (".pdf",)

    def convert(self, src: Path) -> ConvertResult:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise ConversionError(
                src,
                "docling is not installed — PDF support is optional.\n"
                "  Install with:  pip install 'mdpack[pdf]'\n"
                "  (pulls torch + transformers, ~1GB download on first run.)",
            ) from e

        try:
            converter = DocumentConverter()
            result = converter.convert(str(src))
            markdown = result.document.export_to_markdown()
        except Exception as e:
            raise ConversionError(src, f"docling failed: {type(e).__name__}: {e}") from e

        body, stripped = strip_base64_images(markdown)
        warnings: list[str] = []
        if stripped:
            warnings.append(f"stripped {stripped} inline base64 image(s)")

        return ConvertResult(body=body, title=src.stem, warnings=warnings)
