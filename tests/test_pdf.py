from pathlib import Path
from unittest.mock import patch

import pytest

from mdpack.converters.base import ConversionError
from mdpack.converters.pdf_conv import PdfConverter


def test_pdf_import_error_message(tmp_path: Path) -> None:
    """Without docling installed, PdfConverter must give an actionable error."""
    fake = tmp_path / "missing.pdf"
    fake.write_bytes(b"%PDF-1.4 not a real pdf")

    # Simulate docling not being importable even if it's actually installed
    import builtins

    real_import = builtins.__import__

    def _blocked(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("docling"):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", _blocked):
        with pytest.raises(ConversionError) as ei:
            PdfConverter().convert(fake)

    assert "docling" in ei.value.reason
    assert "mdpack[pdf]" in ei.value.reason


docling_spec = pytest.importorskip.__wrapped__ if hasattr(pytest.importorskip, "__wrapped__") else None


@pytest.mark.skipif(
    __import__("importlib.util", fromlist=["find_spec"]).find_spec("docling") is None,
    reason="docling not installed",
)
def test_pdf_real_conversion(tmp_path: Path) -> None:
    """If docling is actually installed, it should convert a simple PDF."""
    # Build a trivial PDF using reportlab if available; otherwise skip.
    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    src = tmp_path / "hello.pdf"
    c = canvas.Canvas(str(src))
    c.drawString(100, 750, "Hello mdpack")
    c.showPage()
    c.save()
    assert reportlab is not None

    result = PdfConverter().convert(src)
    assert "Hello" in result.body
