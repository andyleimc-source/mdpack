from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from mdpack.scanner import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_MAX_SIZE_BYTES,
    DEFAULT_PDF_MAX_SIZE_BYTES,
    ScanConfig,
    Scanner,
    parse_size,
)


def _csv(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("h\n1\n", encoding="utf-8")


def test_default_excludes_vcs_and_caches(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "real.csv")
    _csv(src / ".git" / "tracked.csv")
    _csv(src / "node_modules" / "pkg.csv")
    _csv(src / ".venv" / "site.csv")
    _csv(src / "__pycache__" / "x.csv")

    jobs, stats = Scanner().scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["real.csv"]
    assert stats.excluded_dirs + stats.excluded_hidden >= 4


def test_self_recursion_prevented(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = src / "converted"
    _csv(src / "a.csv")
    _csv(out / "stale" / "b.csv")

    jobs, stats = Scanner().scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["a.csv"]
    assert stats.skipped_out_root + stats.excluded_dirs >= 1


def test_self_recursion_via_symlink(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out_real"
    _csv(src / "a.csv")
    _csv(out / "evil.csv")
    (src / "link_to_out").symlink_to(out, target_is_directory=True)

    cfg = ScanConfig(follow_symlinks=True)
    jobs, _ = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["a.csv"]


def test_mdpackignore_respected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "keep.csv")
    _csv(src / "drafts" / "skip.csv")
    _csv(src / "notes.tmp.csv")
    (src / ".mdpackignore").write_text("drafts/\n*.tmp.csv\n", encoding="utf-8")

    jobs, _ = Scanner().scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["keep.csv"]


def test_cli_exclude_flag_accumulates(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "keep.csv")
    _csv(src / "archive" / "old.csv")
    _csv(src / "archive2" / "old.csv")
    _csv(src / "report.old.csv")

    cfg = ScanConfig(extra_excludes=("archive/", "archive2/", "*.old.csv"))
    jobs, _ = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["keep.csv"]


def test_max_size_skips_large_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    small = src / "small.csv"
    big = src / "big.csv"
    small.parent.mkdir()
    small.write_text("h\n1\n", encoding="utf-8")
    big.write_bytes(b"x" * 2048)

    cfg = ScanConfig(max_size_bytes=1024)
    jobs, stats = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["small.csv"]
    assert stats.skipped_size == 1
    assert big in stats.skipped_size_paths


def test_pdf_50mb_skipped_independently(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    pdf = src / "big.pdf"
    csv = src / "big.csv"
    pdf.write_bytes(b"%PDF" + b"x" * (60 * 1024))
    csv.write_bytes(b"h,v\n" + b"x" * (60 * 1024))

    cfg = ScanConfig(max_size_bytes=200 * 1024, pdf_max_size_bytes=50 * 1024)
    jobs, stats = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["big.csv"]
    assert pdf in stats.skipped_size_paths


def test_symlink_not_followed_by_default(tmp_path: Path) -> None:
    src = tmp_path / "src"
    outside = tmp_path / "outside"
    out = tmp_path / "out"
    _csv(src / "real.csv")
    _csv(outside / "stranger.csv")
    (src / "link").symlink_to(outside, target_is_directory=True)

    jobs, _ = Scanner().scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["real.csv"]


def test_symlink_followed_when_opted_in(tmp_path: Path) -> None:
    src = tmp_path / "src"
    outside = tmp_path / "outside"
    out = tmp_path / "out"
    _csv(src / "real.csv")
    _csv(outside / "stranger.csv")
    (src / "link").symlink_to(outside, target_is_directory=True)

    cfg = ScanConfig(follow_symlinks=True)
    jobs, _ = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["real.csv", "stranger.csv"]


def test_symlink_loop_protected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "a.csv")
    (src / "loop").symlink_to(src, target_is_directory=True)

    cfg = ScanConfig(follow_symlinks=True)
    jobs, stats = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["a.csv"]
    assert stats.skipped_symlink_loop >= 1


def test_hidden_dir_excluded_by_default(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "visible.csv")
    _csv(src / ".secret" / "hush.csv")

    jobs, stats = Scanner().scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["visible.csv"]
    assert stats.excluded_hidden >= 1


def test_include_hidden_flag(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "visible.csv")
    _csv(src / ".secret" / "hush.csv")

    cfg = ScanConfig(include_hidden=True)
    jobs, _ = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["hush.csv", "visible.csv"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", 0),
        ("", 0),
        ("1024", 1024),
        ("1KB", 1024),
        ("1K", 1024),
        ("50MB", 50 * 1024 * 1024),
        ("1.5GB", int(1.5 * 1024**3)),
        ("2GiB", 2 * 1024**3),
        (4096, 4096),
    ],
)
def test_parse_size_variants(value: str | int, expected: int) -> None:
    assert parse_size(value) == expected


@pytest.mark.parametrize("bad", ["bogus", "5XB", "abc", "5  KB extra", "MB"])
def test_parse_size_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_size(bad)


def test_scanner_is_iterator(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "a.csv")
    iterator = Scanner().scan(src, out)
    assert isinstance(iterator, Iterator)
    items = list(iterator)
    assert [j.src.name for j in items] == ["a.csv"]


def test_single_file_input(tmp_path: Path) -> None:
    f = tmp_path / "lonely.csv"
    f.write_text("h\n1\n", encoding="utf-8")
    out = tmp_path / "out"
    jobs, _ = Scanner().scan_with_stats(f, out)
    assert len(jobs) == 1
    assert jobs[0].src == f.resolve()
    assert jobs[0].dst == (out / "lonely.md").resolve() or jobs[0].dst.name == "lonely.md"


def test_max_depth_caps_recursion(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "a.csv")
    _csv(src / "d1" / "b.csv")
    _csv(src / "d1" / "d2" / "c.csv")

    cfg = ScanConfig(max_depth=1)
    jobs, _ = Scanner(cfg).scan_with_stats(src, out)
    names = sorted(j.src.name for j in jobs)
    assert names == ["a.csv", "b.csv"]


def test_unreadable_dir_skipped(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    _csv(src / "ok.csv")
    locked = src / "locked"
    locked.mkdir()
    _csv(locked / "secret.csv")
    os.chmod(locked, 0o000)
    try:
        jobs, _ = Scanner().scan_with_stats(src, out)
        names = sorted(j.src.name for j in jobs)
        assert "ok.csv" in names
    finally:
        os.chmod(locked, 0o755)


def test_default_excludes_constant_includes_converted() -> None:
    assert "converted" in DEFAULT_EXCLUDE_DIRS
    assert ".git" in DEFAULT_EXCLUDE_DIRS
    assert "node_modules" in DEFAULT_EXCLUDE_DIRS


def test_default_caps_match_plan() -> None:
    assert DEFAULT_MAX_SIZE_BYTES == 100 * 1024 * 1024
    assert DEFAULT_PDF_MAX_SIZE_BYTES == 50 * 1024 * 1024
