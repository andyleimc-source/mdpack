from pathlib import Path

from mdpack.converters.csv_conv import CsvConverter


def test_basic_csv(tmp_path: Path) -> None:
    src = tmp_path / "leads.csv"
    src.write_text("name,email,score\nAlice,a@x.com,42\nBob,b@x.com,17\n", encoding="utf-8")

    result = CsvConverter().convert(src)

    assert "# leads" in result.body
    assert "| name | email | score |" in result.body
    assert "| Alice | a@x.com | 42 |" in result.body
    assert result.warnings == []


def test_csv_pipe_character_escaped(tmp_path: Path) -> None:
    src = tmp_path / "weird.csv"
    src.write_text("a,b\n\"x|y\",z\n", encoding="utf-8")
    result = CsvConverter().convert(src)
    assert "x\\|y" in result.body


def test_empty_csv(tmp_path: Path) -> None:
    src = tmp_path / "empty.csv"
    src.write_text("", encoding="utf-8")
    result = CsvConverter().convert(src)
    assert result.body == ""
    assert "empty" in result.warnings[0]


def test_header_only_csv(tmp_path: Path) -> None:
    src = tmp_path / "header.csv"
    src.write_text("a,b,c\n", encoding="utf-8")
    result = CsvConverter().convert(src)
    assert "| a | b | c |" in result.body
    assert any("no data rows" in w for w in result.warnings)


def test_ragged_rows_padded(tmp_path: Path) -> None:
    src = tmp_path / "ragged.csv"
    src.write_text("a,b,c\n1,2\n3,4,5,6\n", encoding="utf-8")
    result = CsvConverter().convert(src)
    lines = [line for line in result.body.splitlines() if line.startswith("|")]
    widths = {line.count("|") for line in lines}
    assert len(widths) == 1
