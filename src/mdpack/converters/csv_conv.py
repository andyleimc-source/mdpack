"""CSV → Markdown table."""

from __future__ import annotations

import csv
from pathlib import Path

from ..utils import md_escape_cell
from .base import ConversionError, ConvertResult


class CsvConverter:
    name = "csv"
    extensions = (".csv",)

    def convert(self, src: Path) -> ConvertResult:
        try:
            with src.open("r", encoding="utf-8-sig", newline="") as f:
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                rows = list(csv.reader(f, dialect))
        except (OSError, UnicodeDecodeError) as e:
            raise ConversionError(src, f"failed to read: {e}") from e

        rows = [r for r in rows if any(cell.strip() for cell in r)]
        if not rows:
            return ConvertResult(body="", title=src.stem, warnings=["empty CSV"])

        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        header, data = rows[0], rows[1:]

        lines: list[str] = [f"# {src.stem}\n"]
        lines.append("| " + " | ".join(md_escape_cell(c) for c in header) + " |")
        lines.append("|" + "|".join(["---"] * width) + "|")
        for row in data:
            lines.append("| " + " | ".join(md_escape_cell(c) for c in row) + " |")

        warnings: list[str] = []
        if not data:
            warnings.append("CSV has header but no data rows")

        return ConvertResult(body="\n".join(lines) + "\n", title=src.stem, warnings=warnings)
