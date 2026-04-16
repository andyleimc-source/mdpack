from mdpack.utils import md_escape_cell, strip_base64_images


def test_strip_base64_image() -> None:
    md = (
        "before\n"
        "![alt text](data:image/png;base64,AAAABBBBCCCCDDDDDD==)\n"
        "middle\n"
        "![](data:image/jpeg;base64,XXX)\n"
        "after\n"
    )
    out, count = strip_base64_images(md)
    assert count == 2
    assert "data:image" not in out
    assert "<!-- image -->" in out


def test_strip_leaves_regular_images_alone() -> None:
    md = "![real](images/foo.png)"
    out, count = strip_base64_images(md)
    assert count == 0
    assert out == md


def test_md_escape_cell_pipes() -> None:
    assert md_escape_cell("a|b") == "a\\|b"


def test_md_escape_cell_newlines() -> None:
    assert md_escape_cell("line1\nline2") == "line1 line2"
