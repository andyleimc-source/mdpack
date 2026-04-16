"""Directory walking and output path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .registry import find_converter


@dataclass
class ConvertJob:
    src: Path
    dst: Path
    converter_name: str


def iter_jobs(src_root: Path, out_root: Path) -> list[ConvertJob]:
    """Walk src_root and return a list of jobs for files we know how to convert."""
    src_root = src_root.resolve()
    out_root = out_root.resolve()
    jobs: list[ConvertJob] = []

    if src_root.is_file():
        conv = find_converter(src_root.suffix)
        if conv is not None:
            dst = out_root / (src_root.stem + ".md")
            jobs.append(ConvertJob(src=src_root, dst=dst, converter_name=conv.name))
        return jobs

    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        conv = find_converter(path.suffix)
        if conv is None:
            continue
        rel = path.relative_to(src_root).with_suffix(".md")
        jobs.append(ConvertJob(src=path, dst=out_root / rel, converter_name=conv.name))

    return jobs


def needs_update(job: ConvertJob, force: bool = False) -> bool:
    if force:
        return True
    if not job.dst.exists():
        return True
    return job.src.stat().st_mtime > job.dst.stat().st_mtime
