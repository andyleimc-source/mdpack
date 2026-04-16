"""Tests for the file-system watcher.

Uses short sleeps to let watchdog + the 1.5s debounce do their work. If these
tests prove flaky on CI, consider monkey-patching DEBOUNCE_SECONDS to 0.1.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from mdpack import watcher as watcher_mod
from mdpack.watcher import Watcher


@pytest.fixture
def fast_debounce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink debounce window so tests don't each pay 1.5s."""
    monkeypatch.setattr(watcher_mod, "DEBOUNCE_SECONDS", 0.2)


def _wait_for(cond, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_watcher_picks_up_new_file(tmp_path: Path, fast_debounce: None) -> None:
    src = tmp_path / "A"
    out = tmp_path / "B"
    src.mkdir()

    w = Watcher(src, out)
    w.start()
    try:
        (src / "notes.csv").write_text("h,v\n1,2\n", encoding="utf-8")
        assert _wait_for(lambda: (out / "notes.md").exists())
        body = (out / "notes.md").read_text(encoding="utf-8")
        assert "converter: csv" in body
        assert "| 1 | 2 |" in body
    finally:
        w.stop()


def test_watcher_updates_on_modification(tmp_path: Path, fast_debounce: None) -> None:
    src = tmp_path / "A"
    out = tmp_path / "B"
    src.mkdir()
    (src / "x.csv").write_text("h\n1\n", encoding="utf-8")

    w = Watcher(src, out)
    w.initial_sync()
    assert (out / "x.md").exists()
    first_mtime = (out / "x.md").stat().st_mtime

    w.start()
    try:
        time.sleep(0.1)
        (src / "x.csv").write_text("h\n1\n2\n3\n", encoding="utf-8")
        assert _wait_for(
            lambda: (out / "x.md").stat().st_mtime > first_mtime
            and "| 3 |" in (out / "x.md").read_text(encoding="utf-8")
        )
    finally:
        w.stop()


def test_watcher_deletes_output_when_source_removed(
    tmp_path: Path, fast_debounce: None
) -> None:
    src = tmp_path / "A"
    out = tmp_path / "B"
    src.mkdir()
    (src / "gone.csv").write_text("h\n1\n", encoding="utf-8")

    w = Watcher(src, out)
    w.initial_sync()
    assert (out / "gone.md").exists()

    w.start()
    try:
        (src / "gone.csv").unlink()
        assert _wait_for(lambda: not (out / "gone.md").exists())
    finally:
        w.stop()


def test_watcher_ignores_writes_inside_out_root(tmp_path: Path, fast_debounce: None) -> None:
    """If the user points -o at a subdirectory of src, watcher must not recurse on itself."""
    src = tmp_path / "A"
    out = src / "converted"
    src.mkdir()

    w = Watcher(src, out)
    w.start()
    try:
        (src / "a.csv").write_text("h\n1\n", encoding="utf-8")
        assert _wait_for(lambda: (out / "a.md").exists())

        # Touching the generated md file must not kick off a loop
        pre_mtime = (out / "a.md").stat().st_mtime
        (out / "a.md").write_text("# tampered\n", encoding="utf-8")
        time.sleep(0.6)
        # We expect the file to remain as we tampered with it (not rewritten).
        assert (out / "a.md").read_text(encoding="utf-8") == "# tampered\n"
        assert (out / "a.md").stat().st_mtime >= pre_mtime
    finally:
        w.stop()


def test_initial_sync_handles_empty_dir(tmp_path: Path) -> None:
    src = tmp_path / "A"
    out = tmp_path / "B"
    src.mkdir()
    ok, skipped, failed = Watcher(src, out).initial_sync()
    assert (ok, skipped, failed) == (0, 0, 0)


def test_initial_sync_skips_files_inside_out_root(tmp_path: Path) -> None:
    """initial_sync must not re-process files that live inside out_root."""
    src = tmp_path / "A"
    out = src / "converted"
    src.mkdir()
    (src / "a.csv").write_text("h\n1\n", encoding="utf-8")
    (out / "stale").mkdir(parents=True)
    (out / "stale" / "ghost.csv").write_text("h\n9\n", encoding="utf-8")

    ok, _, failed = Watcher(src, out).initial_sync()
    assert failed == 0
    assert ok == 1
    assert (out / "a.md").exists()
    assert not (out / "stale" / "ghost.md").exists()


def test_initial_sync_default_excludes(tmp_path: Path) -> None:
    """initial_sync uses Scanner defaults — dotdirs and .git skipped."""
    src = tmp_path / "A"
    out = tmp_path / "B"
    src.mkdir()
    (src / ".git").mkdir()
    (src / ".git" / "tracked.csv").write_text("h\n1\n", encoding="utf-8")
    (src / "real.csv").write_text("h\n1\n", encoding="utf-8")

    ok, _, failed = Watcher(src, out).initial_sync()
    assert failed == 0
    assert ok == 1
    assert (out / "real.md").exists()
    assert not (out / ".git" / "tracked.md").exists()
