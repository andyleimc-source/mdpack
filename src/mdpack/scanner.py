"""Configurable file-system scanner that yields ConvertJob instances.

Replaces the old `walker.iter_jobs` which had no exclusions, no size caps,
followed symlinks, and `sorted()`-materialized every Path. The Scanner here
is a true generator and applies all filtering at the directory level so we
never recurse into junk (`.git`, `node_modules`, `Library`, the output
directory, …).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from .registry import find_converter, supported_extensions
from .walker import ConvertJob

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", "dist", "build",
    "node_modules", ".next", ".nuxt", ".parcel-cache", ".turbo",
    "target",
    ".idea", ".vscode",
    "Library", ".Trash", ".cache",
    "converted",
})

DEFAULT_MAX_SIZE_BYTES: int = 100 * 1024 * 1024
DEFAULT_PDF_MAX_SIZE_BYTES: int = 50 * 1024 * 1024


_SIZE_PATTERN = re.compile(
    r"^\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[KMGT]?I?B?)?\s*$",
    re.IGNORECASE,
)
_SIZE_UNITS = {
    "": 1, "B": 1,
    "K": 1024, "KB": 1024, "KIB": 1024,
    "M": 1024**2, "MB": 1024**2, "MIB": 1024**2,
    "G": 1024**3, "GB": 1024**3, "GIB": 1024**3,
    "T": 1024**4, "TB": 1024**4, "TIB": 1024**4,
}


def parse_size(value: str | int) -> int:
    """Parse a human size like '50MB', '1.5GiB', '0', '1024'.

    Returns bytes. `0` (or empty) means unlimited (returns 0). Base 1024,
    matching `du -h`/`ls -lh`.
    """
    if isinstance(value, int):
        return max(0, value)
    s = value.strip()
    if not s:
        return 0
    m = _SIZE_PATTERN.match(s)
    if not m:
        raise ValueError(f"invalid size: {value!r}")
    num = float(m.group("num"))
    unit = (m.group("unit") or "").upper()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"invalid size unit: {value!r}")
    return int(num * _SIZE_UNITS[unit])


@dataclass(frozen=True)
class ScanConfig:
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS
    extra_excludes: tuple[str, ...] = ()
    ignore_file: Path | None = None
    respect_gitignore: bool = False
    follow_symlinks: bool = False
    include_hidden: bool = False
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES
    pdf_max_size_bytes: int = DEFAULT_PDF_MAX_SIZE_BYTES
    max_depth: int | None = None


@dataclass
class ScanStats:
    scanned_dirs: int = 0
    excluded_dirs: int = 0
    excluded_hidden: int = 0
    skipped_size: int = 0
    skipped_symlink_loop: int = 0
    skipped_out_root: int = 0
    skipped_unsupported: int = 0
    total_jobs: int = 0
    skipped_size_paths: list[Path] = field(default_factory=list)


class Scanner:
    """Walk a source tree and yield ConvertJob for files we know how to handle.

    All filtering happens here. cli.py and watcher.py both go through this so
    behavior stays consistent. The walker is a generator — never materializes
    the whole tree.
    """

    def __init__(self, config: ScanConfig | None = None) -> None:
        self.config = config or ScanConfig()
        self._supported_exts = {e.lower() for e in supported_extensions()}

    def scan(self, src_root: Path, out_root: Path) -> Iterator[ConvertJob]:
        """Yield ConvertJob for each scannable, convertible, under-cap file."""
        return self._scan(src_root, out_root, ScanStats())

    def scan_with_stats(
        self, src_root: Path, out_root: Path
    ) -> tuple[list[ConvertJob], ScanStats]:
        """Materialize jobs into a list and return ScanStats. Used by CLI for
        progress bar (`length=`) and end-of-run summary."""
        stats = ScanStats()
        jobs = list(self._scan(src_root, out_root, stats))
        stats.total_jobs = len(jobs)
        return jobs, stats

    def _build_spec(self, src_root: Path) -> pathspec.PathSpec | None:
        lines: list[str] = []
        if self.config.ignore_file is None:
            auto_ignore = src_root / ".mdpackignore"
            if auto_ignore.exists():
                lines.extend(auto_ignore.read_text(encoding="utf-8").splitlines())
        elif self.config.ignore_file.exists():
            lines.extend(
                self.config.ignore_file.read_text(encoding="utf-8").splitlines()
            )
        if self.config.respect_gitignore:
            gi = src_root / ".gitignore"
            if gi.exists():
                lines.extend(gi.read_text(encoding="utf-8").splitlines())
        lines.extend(self.config.extra_excludes)
        if not lines:
            return None
        return pathspec.PathSpec.from_lines("gitignore", lines)

    def _scan(
        self, src_root: Path, out_root: Path, stats: ScanStats
    ) -> Iterator[ConvertJob]:
        src_root = src_root.resolve()
        out_root_resolved = out_root.resolve()

        if src_root.is_file():
            job = self._make_job_for_file(src_root, src_root.parent, out_root, stats)
            if job is not None:
                yield job
            return

        spec = self._build_spec(src_root)
        seen_inodes: set[tuple[int, int]] = set()
        try:
            st = src_root.stat()
            seen_inodes.add((st.st_dev, st.st_ino))
        except OSError:
            return
        yield from self._walk(
            src_root, src_root, out_root, out_root_resolved,
            spec, seen_inodes, 0, stats,
        )

    def _walk(
        self,
        current: Path,
        src_root: Path,
        out_root: Path,
        out_root_resolved: Path,
        spec: pathspec.PathSpec | None,
        seen_inodes: set[tuple[int, int]],
        depth: int,
        stats: ScanStats,
    ) -> Iterator[ConvertJob]:
        if self.config.max_depth is not None and depth > self.config.max_depth:
            return

        try:
            with os.scandir(current) as it:
                entries = sorted(it, key=lambda e: e.name)
        except (PermissionError, OSError):
            return

        stats.scanned_dirs += 1
        follow = self.config.follow_symlinks

        for entry in entries:
            name = entry.name
            entry_path = Path(entry.path)

            if not self.config.include_hidden and name.startswith("."):
                stats.excluded_hidden += 1
                continue

            is_symlink = entry.is_symlink()
            try:
                is_dir = entry.is_dir(follow_symlinks=True)
                is_file = entry.is_file(follow_symlinks=True)
            except OSError:
                continue

            if name in self.config.exclude_dirs:
                if is_dir:
                    stats.excluded_dirs += 1
                continue

            try:
                rel = entry_path.relative_to(src_root)
            except ValueError:
                rel = Path(name)
            rel_posix = rel.as_posix()
            match_target = rel_posix + ("/" if is_dir else "")
            if spec is not None and spec.match_file(match_target):
                if is_dir:
                    stats.excluded_dirs += 1
                continue

            if is_dir:
                if self._is_inside_out_root(entry_path, out_root_resolved):
                    stats.skipped_out_root += 1
                    continue
                if is_symlink and not follow:
                    stats.excluded_dirs += 1
                    continue
                if is_symlink and follow:
                    try:
                        st = entry.stat(follow_symlinks=True)
                    except OSError:
                        continue
                    key = (st.st_dev, st.st_ino)
                    if key in seen_inodes:
                        stats.skipped_symlink_loop += 1
                        continue
                    seen_inodes.add(key)
                yield from self._walk(
                    entry_path, src_root, out_root, out_root_resolved,
                    spec, seen_inodes, depth + 1, stats,
                )
            elif is_file:
                if self._is_inside_out_root(entry_path, out_root_resolved):
                    stats.skipped_out_root += 1
                    continue
                job = self._make_job_for_file(entry_path, src_root, out_root, stats)
                if job is not None:
                    yield job

    def _is_inside_out_root(self, path: Path, out_root_resolved: Path) -> bool:
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            return False
        if resolved == out_root_resolved:
            return True
        return out_root_resolved in resolved.parents

    def _make_job_for_file(
        self, path: Path, src_root: Path, out_root: Path, stats: ScanStats
    ) -> ConvertJob | None:
        ext = path.suffix.lower()
        conv = find_converter(ext)
        if conv is None:
            stats.skipped_unsupported += 1
            return None

        try:
            size = path.stat().st_size
        except OSError:
            return None

        cap = self.config.max_size_bytes
        if cap and size > cap:
            stats.skipped_size += 1
            stats.skipped_size_paths.append(path)
            return None
        if ext == ".pdf":
            pdf_cap = self.config.pdf_max_size_bytes
            if pdf_cap and size > pdf_cap:
                stats.skipped_size += 1
                stats.skipped_size_paths.append(path)
                return None

        try:
            rel = path.relative_to(src_root).with_suffix(".md")
        except ValueError:
            rel = Path(path.stem + ".md")
        dst = out_root / rel
        return ConvertJob(src=path, dst=dst, converter_name=conv.name)
