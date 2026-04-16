"""Extension → converter mapping."""

from __future__ import annotations

from .converters import Converter
from .converters.csv_conv import CsvConverter
from .converters.docx_conv import DocxConverter
from .converters.pdf_conv import PdfConverter
from .converters.pptx_conv import PptxConverter
from .converters.xlsx_conv import XlsxConverter

CONVERTERS: tuple[Converter, ...] = (
    CsvConverter(),
    XlsxConverter(),
    DocxConverter(),
    PptxConverter(),
    PdfConverter(),
)


def find_converter(ext: str) -> Converter | None:
    ext = ext.lower()
    for conv in CONVERTERS:
        if ext in conv.extensions:
            return conv
    return None


def supported_extensions() -> tuple[str, ...]:
    exts: list[str] = []
    for conv in CONVERTERS:
        exts.extend(conv.extensions)
    return tuple(exts)
