from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
from mdpack.converters.xlsx_conv import XlsxConverter  # noqa: E402


def _make_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    wb.save(path)


def test_basic_xlsx(tmp_path: Path) -> None:
    src = tmp_path / "report.xlsx"
    _make_xlsx(src, {"Summary": [["Region", "Revenue"], ["APAC", 4200000], ["EMEA", 3100000]]})

    result = XlsxConverter().convert(src)

    assert "# report" in result.body
    assert "## Summary" in result.body
    assert "| Region | Revenue |" in result.body
    assert "| APAC | 4200000 |" in result.body


def test_multiple_sheets(tmp_path: Path) -> None:
    src = tmp_path / "multi.xlsx"
    _make_xlsx(
        src,
        {
            "Q1": [["x", "y"], [1, 2]],
            "Q2": [["x", "y"], [3, 4]],
        },
    )
    result = XlsxConverter().convert(src)
    assert "## Q1" in result.body
    assert "## Q2" in result.body


def test_empty_sheet_skipped(tmp_path: Path) -> None:
    src = tmp_path / "partial.xlsx"
    _make_xlsx(src, {"Data": [["a", "b"], [1, 2]], "Empty": []})
    result = XlsxConverter().convert(src)
    assert "## Data" in result.body
    assert "## Empty" not in result.body
    assert any("Empty" in w for w in result.warnings)


def test_all_empty(tmp_path: Path) -> None:
    src = tmp_path / "void.xlsx"
    _make_xlsx(src, {"S1": [], "S2": []})
    result = XlsxConverter().convert(src)
    assert result.body == ""
    assert result.warnings == ["all sheets empty"]


def test_integer_floats_not_printed_as_decimals(tmp_path: Path) -> None:
    src = tmp_path / "nums.xlsx"
    _make_xlsx(src, {"S": [["v"], [42.0]]})
    result = XlsxConverter().convert(src)
    assert "| 42 |" in result.body
    assert "42.0" not in result.body
