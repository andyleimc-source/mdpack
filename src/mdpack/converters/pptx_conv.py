"""PPTX → Markdown via pandoc."""

from __future__ import annotations

from pathlib import Path

from .base import ConvertResult
from ._pandoc import run_pandoc


class PptxConverter:
    name = "pptx"
    extensions = (".pptx",)

    def convert(self, src: Path) -> ConvertResult:
        return run_pandoc(src, from_fmt="pptx")
