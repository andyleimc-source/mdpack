from pathlib import Path

from click.testing import CliRunner

from mdpack.cli import main


def test_formats_command() -> None:
    result = CliRunner().invoke(main, ["formats"])
    assert result.exit_code == 0
    assert "csv" in result.output
    assert "xlsx" in result.output
    assert "docx" in result.output


def test_doctor_reports_mdpack_version() -> None:
    result = CliRunner().invoke(main, ["doctor"])
    assert "mdpack:" in result.output


def test_convert_dir_mirrors_tree(tmp_path: Path) -> None:
    src = tmp_path / "in"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "a.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "b.csv").write_text("h\n2\n", encoding="utf-8")
    out = tmp_path / "out"

    result = CliRunner().invoke(main, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0, result.output

    assert (out / "sub" / "a.md").exists()
    assert (out / "b.md").exists()

    body = (out / "b.md").read_text(encoding="utf-8")
    assert body.startswith("---\n")
    assert "converter: csv" in body
    assert "source: b.csv" in body


def test_convert_skips_up_to_date(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "x.csv").write_text("h\n1\n", encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()

    first = runner.invoke(main, ["convert", str(src), "-o", str(out)])
    assert first.exit_code == 0
    assert "ok" in first.output

    second = runner.invoke(main, ["convert", str(src), "-o", str(out)])
    assert second.exit_code == 0
    assert "skip" in second.output


def test_convert_force_reconverts(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "x.csv").write_text("h\n1\n", encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()

    runner.invoke(main, ["convert", str(src), "-o", str(out)])
    third = runner.invoke(main, ["convert", str(src), "-o", str(out), "--force"])
    assert "ok" in third.output


def test_convert_no_supported_files_exits_nonzero(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "note.txt").write_text("hi", encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(main, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 1
    assert "No convertible files" in result.output
