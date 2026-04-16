"""YAML frontmatter injection for converted markdown output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def _yaml_escape(value: str) -> str:
    if any(ch in value for ch in ':#"\'\n') or value.strip() != value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def build_frontmatter(
    *,
    src: Path,
    converter_name: str,
    title: str | None = None,
    source_root: Path | None = None,
) -> str:
    source_display = (
        str(src.resolve().relative_to(source_root.resolve()))
        if source_root is not None
        else str(src)
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = ["---"]
    if title:
        lines.append(f"title: {_yaml_escape(title)}")
    lines.append(f"source: {_yaml_escape(source_display)}")
    lines.append(f"converter: {converter_name}")
    lines.append(f"converter_version: mdpack {__version__}")
    lines.append(f"converted_at: {now}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"
