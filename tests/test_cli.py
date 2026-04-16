from pathlib import Path

from click.testing import CliRunner

from mdpack.cli import main


def test_formats_command() -> None:
    result = CliRunner().invoke(main, ["formats"])
    assert result.exit_code == 0
    assert "csv" in result.output
    assert "xlsx" in result.output
    assert "docx" in result.output
    assert "pptx" in result.output
    assert "pdf" in result.output


def test_doctor_reports_mdpack_version() -> None:
    result = CliRunner().invoke(main, ["doctor"])
    assert "mdpack:" in result.output


def test_watch_help() -> None:
    result = CliRunner().invoke(main, ["watch", "--help"])
    assert result.exit_code == 0
    assert "Watch SRC for changes" in result.output
    assert "--no-initial-sync" in result.output


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


def test_convert_skips_git_and_node_modules(tmp_path: Path) -> None:
    src = tmp_path / "in"
    out = tmp_path / "out"
    (src / ".git").mkdir(parents=True)
    (src / ".git" / "x.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "node_modules" / "pkg").mkdir(parents=True)
    (src / "node_modules" / "pkg" / "y.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "real.csv").write_text("h\n1\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "real.md").exists()
    assert not (out / ".git" / "x.md").exists()
    assert not (out / "node_modules" / "pkg" / "y.md").exists()


def test_convert_max_size_skips_large(tmp_path: Path) -> None:
    src = tmp_path / "in"
    out = tmp_path / "out"
    src.mkdir()
    (src / "small.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "big.csv").write_bytes(b"h,v\n" + b"x" * 4096)

    result = CliRunner().invoke(
        main, ["convert", str(src), "-o", str(out), "--max-size", "1KB"]
    )
    assert result.exit_code == 0, result.output
    assert (out / "small.md").exists()
    assert not (out / "big.md").exists()
    assert "oversize" in result.output


def test_convert_exclude_flag_accumulates(tmp_path: Path) -> None:
    src = tmp_path / "in"
    out = tmp_path / "out"
    (src / "keep").mkdir(parents=True)
    (src / "archive").mkdir()
    (src / "keep" / "k.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "archive" / "a.csv").write_text("h\n2\n", encoding="utf-8")
    (src / "report.old.csv").write_text("h\n3\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["convert", str(src), "-o", str(out),
         "--exclude", "archive/", "--exclude", "*.old.csv"],
    )
    assert result.exit_code == 0, result.output
    assert (out / "keep" / "k.md").exists()
    assert not (out / "archive" / "a.md").exists()
    assert not (out / "report.old.md").exists()


def test_convert_jobs_flag_runs(tmp_path: Path) -> None:
    src = tmp_path / "in"
    out = tmp_path / "out"
    src.mkdir()
    for i in range(5):
        (src / f"f{i}.csv").write_text(f"h\n{i}\n", encoding="utf-8")

    result = CliRunner().invoke(
        main, ["convert", str(src), "-o", str(out), "-j", "3"]
    )
    assert result.exit_code == 0, result.output
    for i in range(5):
        assert (out / f"f{i}.md").exists()


def test_convert_no_progress_no_ansi(tmp_path: Path) -> None:
    src = tmp_path / "in"
    out = tmp_path / "out"
    src.mkdir()
    (src / "a.csv").write_text("h\n1\n", encoding="utf-8")

    result = CliRunner().invoke(
        main, ["convert", str(src), "-o", str(out), "--no-progress"]
    )
    assert result.exit_code == 0, result.output
    assert "\x1b[" not in result.output


def test_convert_self_recursion_with_default_out(tmp_path: Path) -> None:
    """Default out is <src>/converted; second run must not blow up on its own output."""
    src = tmp_path / "in"
    src.mkdir()
    (src / "a.csv").write_text("h\n1\n", encoding="utf-8")

    runner = CliRunner()
    first = runner.invoke(main, ["convert", str(src)])
    assert first.exit_code == 0, first.output
    second = runner.invoke(main, ["convert", str(src)])
    assert second.exit_code == 0, second.output
    assert "1 converted" in first.output or "ok" in first.output
    assert "skip" in second.output
