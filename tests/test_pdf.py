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


def test_pdf_50mb_cap_defended_in_convert(tmp_path: Path) -> None:
    """Even if the Scanner missed it, PdfConverter must refuse oversize PDFs."""
    from mdpack.converters import pdf_conv

    big = tmp_path / "huge.pdf"
    big.write_bytes(b"%PDF" + b"x" * (pdf_conv.PDF_HARD_CAP_BYTES + 1))

    with pytest.raises(ConversionError) as ei:
        PdfConverter().convert(big)
    assert "exceeds" in ei.value.reason
    assert "MB" in ei.value.reason


def test_pdf_converter_singleton(tmp_path: Path) -> None:
    """Multiple convert() calls must reuse one Docling DocumentConverter."""
    from mdpack.converters import pdf_conv

    pdf_conv._reset_singleton_for_tests()

    instantiations = 0

    class FakeDoc:
        def export_to_markdown(self) -> str:
            return "# fake\n\nhello\n"

    class FakeResult:
        document = FakeDoc()

    class FakeConverter:
        def __init__(self) -> None:
            nonlocal instantiations
            instantiations += 1

        def convert(self, src: str) -> FakeResult:
            return FakeResult()

    fake_module = type("M", (), {"DocumentConverter": FakeConverter})()
    fake_pkg = type("P", (), {"document_converter": fake_module})()

    import sys
    sys.modules["docling"] = fake_pkg  # type: ignore[assignment]
    sys.modules["docling.document_converter"] = fake_module  # type: ignore[assignment]
    try:
        for i in range(5):
            p = tmp_path / f"p{i}.pdf"
            p.write_bytes(b"%PDF-1.4 stub")
            PdfConverter().convert(p)
        assert instantiations == 1
    finally:
        sys.modules.pop("docling", None)
        sys.modules.pop("docling.document_converter", None)
        pdf_conv._reset_singleton_for_tests()
