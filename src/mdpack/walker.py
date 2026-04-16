"""ConvertJob lifecycle: dst path resolution, freshness check, and execution.

Tree walking moved to `mdpack.scanner` in 0.3.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .converters.base import ConversionError
from .frontmatter import build_frontmatter
from .registry import find_converter


@dataclass
class ConvertJob:
    src: Path
    dst: Path
    converter_name: str


def needs_update(job: ConvertJob, force: bool = False) -> bool:
    if force:
        return True
    if not job.dst.exists():
        return True
    return job.src.stat().st_mtime > job.dst.stat().st_mtime


def resolve_dst(src: Path, source_root: Path, out_root: Path) -> Path:
    """Compute the dst .md path for a given src file under source_root."""
    src = src.resolve()
    source_root = source_root.resolve()
    out_root = out_root.resolve()
    try:
        rel = src.relative_to(source_root).with_suffix(".md")
    except ValueError:
        rel = Path(src.stem + ".md")
    return out_root / rel


def run_job(job: ConvertJob, *, source_root: Path) -> None:
    """Run a single convert job and write the resulting .md to disk."""
    conv = find_converter(job.src.suffix)
    if conv is None:
        raise ConversionError(job.src, "no converter registered")

    result = conv.convert(job.src)
    if not result.body.strip():
        raise ConversionError(job.src, "converter produced empty output")

    fm = build_frontmatter(
        src=job.src,
        converter_name=conv.name,
        title=result.title,
        source_root=source_root,
    )

    job.dst.parent.mkdir(parents=True, exist_ok=True)
    job.dst.write_text(fm + result.body, encoding="utf-8")
