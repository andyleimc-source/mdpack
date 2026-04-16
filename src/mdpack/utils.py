"""Small shared helpers."""

from __future__ import annotations

import re

_BASE64_IMG_RE = re.compile(r"!\[[^\]]*\]\(data:image/[^)]+\)")


def strip_base64_images(text: str) -> tuple[str, int]:
    """Replace ``![alt](data:image/...;base64,...)`` with ``<!-- image -->``.

    Inline base64 images inflate markdown to multi-MB sizes and break downstream
    chunking — always strip before writing output.
    """
    count = 0

    def _sub(_: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "<!-- image -->"

    return _BASE64_IMG_RE.sub(_sub, text), count


def md_escape_cell(value: str) -> str:
    """Escape a cell for use inside a markdown table row."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
