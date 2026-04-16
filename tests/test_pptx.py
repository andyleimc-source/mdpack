import shutil
import subprocess
from pathlib import Path

import pytest

from mdpack.converters.pptx_conv import PptxConverter

HAS_PANDOC = shutil.which("pandoc") is not None
pytestmark = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc not installed")


def _make_pptx(path: Path, text: str) -> None:
    """Build a minimal .pptx by having pandoc generate it from a tiny md."""
    md = path.with_suffix(".md")
    md.write_text(f"# {text}\n\nSome body text.\n", encoding="utf-8")
    subprocess.run(["pandoc", str(md), "-o", str(path)], check=True)
    md.unlink()


def test_pptx_basic(tmp_path: Path) -> None:
    src = tmp_path / "deck.pptx"
    _make_pptx(src, "Slide Title")

    result = PptxConverter().convert(src)

    assert "Slide Title" in result.body or "Some body text" in result.body
    assert result.title == "deck"


def test_pptx_missing_source() -> None:
    from mdpack.converters.base import ConversionError

    with pytest.raises(ConversionError):
        PptxConverter().convert(Path("/nonexistent/deck.pptx"))
