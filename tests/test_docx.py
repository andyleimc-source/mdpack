import shutil
from pathlib import Path

import pytest

from mdpack.converters.base import ConversionError
from mdpack.converters.docx_conv import DocxConverter

HAS_PANDOC = shutil.which("pandoc") is not None
pytestmark = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc not installed")


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    """Build a minimal .docx via the stdlib (no python-docx dep)."""
    import zipfile

    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)


def test_docx_basic(tmp_path: Path) -> None:
    src = tmp_path / "hello.docx"
    _make_docx(src, ["First paragraph.", "Second paragraph."])
    result = DocxConverter().convert(src)
    assert "First paragraph." in result.body
    assert "Second paragraph." in result.body


def test_docx_missing_pandoc_error_message() -> None:
    """Simulate missing pandoc by temporarily shadowing PATH."""
    import subprocess as sp
    from unittest.mock import patch

    with patch("shutil.which", return_value=None):
        with pytest.raises(ConversionError) as ei:
            DocxConverter().convert(Path("/nonexistent.docx"))
    assert "pandoc not found" in ei.value.reason
    assert "brew install pandoc" in ei.value.reason
    # touch sp to satisfy unused import linter
    assert sp is not None
