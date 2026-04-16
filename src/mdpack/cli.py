"""mdpack CLI entry point."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

from . import __version__
from .converters.base import ConversionError
from .registry import CONVERTERS, supported_extensions
from .walker import iter_jobs, needs_update, run_job


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
            run_job(job, source_root=source_root)
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


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


@main.command()
@click.argument("src", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: <src>/converted).",
)
@click.option(
    "--no-initial-sync",
    is_flag=True,
    help="Skip the one-time incremental sync at startup.",
)
@click.option("--force-initial-sync", is_flag=True, help="Re-convert all files at startup.")
@click.option("--quiet", is_flag=True, help="Only print errors and batch summaries.")
def watch(
    src: Path,
    output: Path | None,
    no_initial_sync: bool,
    force_initial_sync: bool,
    quiet: bool,
) -> None:
    """Watch SRC for changes and auto-convert them to Markdown.

    Runs in the foreground — press Ctrl-C to stop. Create/modify/delete/move
    events on supported file types trigger a debounced re-conversion.
    """
    from .watcher import Watcher

    src = src.resolve()
    out_root = output.resolve() if output else (src / "converted")

    def _print_batch(messages: list[str]) -> None:
        for m in messages:
            if m.startswith("FAIL"):
                click.echo(m, err=True)
            elif not quiet:
                click.echo(m)

    watcher = Watcher(src, out_root, on_batch=_print_batch)

    if not no_initial_sync:
        ok, skipped, failed = watcher.initial_sync(force=force_initial_sync)
        if not quiet:
            click.echo(
                f"initial sync: {ok} converted, {skipped} up-to-date, {failed} failed "
                f"(src={src}, out={out_root})"
            )

    watcher.start()
    click.echo(f"watching {src} → {out_root} (Ctrl-C to stop)")
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nstopping...")
    finally:
        watcher.stop()


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
        click.echo(f"{ok} pandoc:   {first} (used for DOCX, PPTX)")
    else:
        click.echo(
            f"{bad} pandoc:   not found "
            "(DOCX/PPTX conversion will fail — `brew install pandoc`)"
        )
        problems += 1

    try:
        import openpyxl
        click.echo(f"{ok} openpyxl: {openpyxl.__version__}")
    except ImportError:
        click.echo(
            f"{bad} openpyxl: not installed (XLSX conversion will fail — `pip install openpyxl`)"
        )
        problems += 1

    import importlib.util as _iu
    if _iu.find_spec("docling") is not None:
        click.echo(f"{ok} docling:  installed (PDF enabled)")
    else:
        click.echo(
            "ℹ️  docling:  not installed — PDF disabled. "
            "Install with `pip install 'mdpack[pdf]'` (pulls ~1GB)"
        )

    import importlib.util as _iu2
    if _iu2.find_spec("watchdog") is not None:
        click.echo(f"{ok} watchdog: installed (watch mode available)")
    else:
        click.echo(f"{bad} watchdog: missing — reinstall mdpack")
        problems += 1

    if problems:
        sys.exit(1)
