"""mdpack CLI entry point."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

from . import __version__
from .converters.base import ConversionError
from .frontmatter import build_frontmatter
from .registry import CONVERTERS, find_converter, supported_extensions
from .walker import ConvertJob, iter_jobs, needs_update


@click.group()
@click.version_option(__version__, prog_name="mdpack")
def main() -> None:
    """Convert any directory of docs to clean Markdown."""


@main.command()
@click.argument("src", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: <src>/converted or alongside the file).",
)
@click.option("--force", is_flag=True, help="Re-convert even if output is newer than source.")
@click.option("--quiet", is_flag=True, help="Only print errors.")
def convert(src: Path, output: Path | None, force: bool, quiet: bool) -> None:
    """Convert SRC (file or directory) into Markdown."""
    src = src.resolve()

    if output is None:
        out_root = src.parent / (src.stem + "_md") if src.is_file() else src / "converted"
    else:
        out_root = output.resolve()

    jobs = iter_jobs(src, out_root)
    if not jobs:
        click.echo(f"No convertible files found under {src}.", err=True)
        sys.exit(1)

    source_root = src if src.is_dir() else src.parent
    ok = 0
    skipped = 0
    failed = 0

    for job in jobs:
        if not needs_update(job, force=force):
            skipped += 1
            if not quiet:
                click.echo(f"skip   {_rel(job.dst, out_root)} (up to date)")
            continue
        try:
            _run_job(job, source_root=source_root)
            ok += 1
            if not quiet:
                click.echo(f"ok     {_rel(job.dst, out_root)}")
        except ConversionError as e:
            failed += 1
            click.echo(f"FAIL   {job.src}: {e.reason}", err=True)

    summary = f"\n{ok} converted, {skipped} skipped, {failed} failed → {out_root}"
    click.echo(summary, err=failed > 0)
    if failed:
        sys.exit(2)


def _run_job(job: ConvertJob, *, source_root: Path) -> None:
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


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


@main.command()
def formats() -> None:
    """List supported input formats and their backends."""
    click.echo("Supported formats:")
    for conv in CONVERTERS:
        exts = ", ".join(conv.extensions)
        click.echo(f"  {conv.name:<6} {exts}")


@main.command()
def doctor() -> None:
    """Check environment and report any issues."""
    import platform

    ok = "✅"
    bad = "❌"
    problems = 0

    click.echo(f"{ok} Python: {sys.version.split()[0]} ({platform.platform()})")
    click.echo(f"{ok} mdpack: {__version__}")
    click.echo(f"{ok} Supported extensions: {', '.join(supported_extensions())}")

    if shutil.which("pandoc"):
        import subprocess
        v = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=False)
        first = v.stdout.splitlines()[0] if v.stdout else "unknown"
        click.echo(f"{ok} pandoc:   {first}")
    else:
        click.echo(f"{bad} pandoc:   not found (DOCX conversion will fail — `brew install pandoc`)")
        problems += 1

    try:
        import openpyxl
        click.echo(f"{ok} openpyxl: {openpyxl.__version__}")
    except ImportError:
        click.echo(f"{bad} openpyxl: not installed (XLSX conversion will fail — `pip install openpyxl`)")
        problems += 1

    if problems:
        sys.exit(1)
