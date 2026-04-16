"""mdpack CLI entry point."""

from __future__ import annotations

import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path

import click

from . import __version__
from .converters.base import ConversionError
from .registry import CONVERTERS, supported_extensions
from .scanner import (
    DEFAULT_EXCLUDE_DIRS,
    ScanConfig,
    ScanStats,
    Scanner,
    parse_size,
)
from .walker import ConvertJob, needs_update, run_job


def _scan_options(f):
    """Shared scanner-related flags for `convert` and `watch`."""
    f = click.option(
        "--max-size",
        "max_size",
        default="100MB",
        show_default=True,
        help="Skip files larger than this (e.g. 50MB, 1GB). 0 = unlimited.",
    )(f)
    f = click.option(
        "--pdf-max-size",
        "pdf_max_size",
        default="50MB",
        show_default=True,
        help="Skip PDF files larger than this (Docling is memory-hungry). 0 = unlimited.",
    )(f)
    f = click.option(
        "--include-hidden",
        is_flag=True,
        help="Include dotfiles and dotdirs (off by default).",
    )(f)
    f = click.option(
        "--follow-symlinks",
        is_flag=True,
        help="Descend into symlinked directories (off by default; loop-protected).",
    )(f)
    f = click.option(
        "--ignore-file",
        type=click.Path(path_type=Path, dir_okay=False),
        default=None,
        help="Path to a gitignore-syntax file (default: <src>/.mdpackignore).",
    )(f)
    f = click.option(
        "--exclude",
        "exclude",
        multiple=True,
        metavar="PATTERN",
        help="Gitignore-syntax pattern to exclude. Repeatable.",
    )(f)
    f = click.option(
        "--respect-gitignore",
        is_flag=True,
        help="Also honor <src>/.gitignore.",
    )(f)
    f = click.option(
        "--max-depth",
        type=int,
        default=None,
        help="Cap recursion depth.",
    )(f)
    return f


def _build_scan_config(
    *,
    max_size: str,
    pdf_max_size: str,
    include_hidden: bool,
    follow_symlinks: bool,
    ignore_file: Path | None,
    exclude: tuple[str, ...],
    respect_gitignore: bool,
    max_depth: int | None,
) -> ScanConfig:
    return ScanConfig(
        exclude_dirs=DEFAULT_EXCLUDE_DIRS,
        extra_excludes=tuple(exclude),
        ignore_file=ignore_file,
        respect_gitignore=respect_gitignore,
        follow_symlinks=follow_symlinks,
        include_hidden=include_hidden,
        max_size_bytes=parse_size(max_size),
        pdf_max_size_bytes=parse_size(pdf_max_size),
        max_depth=max_depth,
    )


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
@click.option("--no-progress", is_flag=True, help="Hide the progress bar even on a TTY.")
@click.option(
    "-j",
    "--jobs",
    "jobs_n",
    type=int,
    default=1,
    show_default=True,
    help="Worker threads. PDFs share a Docling singleton — extra threads don't help PDF.",
)
@_scan_options
def convert(
    src: Path,
    output: Path | None,
    force: bool,
    quiet: bool,
    no_progress: bool,
    jobs_n: int,
    max_size: str,
    pdf_max_size: str,
    include_hidden: bool,
    follow_symlinks: bool,
    ignore_file: Path | None,
    exclude: tuple[str, ...],
    respect_gitignore: bool,
    max_depth: int | None,
) -> None:
    """Convert SRC (file or directory) into Markdown."""
    src = src.resolve()

    if output is None:
        out_root = src.parent / (src.stem + "_md") if src.is_file() else src / "converted"
    else:
        out_root = output.resolve()

    try:
        cfg = _build_scan_config(
            max_size=max_size,
            pdf_max_size=pdf_max_size,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
            ignore_file=ignore_file,
            exclude=exclude,
            respect_gitignore=respect_gitignore,
            max_depth=max_depth,
        )
    except ValueError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)

    jobs, stats = Scanner(cfg).scan_with_stats(src, out_root)
    if not jobs:
        _maybe_explain_empty(src, stats)
        sys.exit(1)

    source_root = src if src.is_dir() else src.parent
    show_bar = not quiet and not no_progress and sys.stderr.isatty() and len(jobs) > 1

    if jobs_n > 1:
        ok, skipped, failed = _run_concurrent(
            jobs, source_root=source_root, out_root=out_root,
            force=force, quiet=quiet, show_bar=show_bar, jobs_n=jobs_n,
        )
    else:
        ok, skipped, failed = _run_serial(
            jobs, source_root=source_root, out_root=out_root,
            force=force, quiet=quiet, show_bar=show_bar,
        )

    _print_summary(ok, skipped, failed, out_root, stats)
    if failed:
        sys.exit(2)


def _maybe_explain_empty(src: Path, stats: ScanStats) -> None:
    click.echo(f"No convertible files found under {src}.", err=True)
    bits: list[str] = []
    if stats.excluded_dirs:
        bits.append(f"{stats.excluded_dirs} dirs excluded")
    if stats.excluded_hidden:
        bits.append(f"{stats.excluded_hidden} hidden entries skipped")
    if stats.skipped_size:
        bits.append(f"{stats.skipped_size} files over size cap")
    if stats.skipped_out_root:
        bits.append(f"{stats.skipped_out_root} entries inside output dir")
    if bits:
        click.echo("(" + ", ".join(bits) + ")", err=True)


def _run_serial(
    jobs: list[ConvertJob], *, source_root: Path, out_root: Path,
    force: bool, quiet: bool, show_bar: bool,
) -> tuple[int, int, int]:
    ok = skipped = failed = 0
    bar_cm = (
        click.progressbar(
            jobs, label="converting", file=sys.stderr,
            item_show_func=lambda j: j.src.name if j else "",
        )
        if show_bar
        else nullcontext(jobs)
    )
    with bar_cm as iterator:
        for job in iterator:
            if not needs_update(job, force=force):
                skipped += 1
                if not quiet and not show_bar:
                    click.echo(f"skip   {_rel(job.dst, out_root)} (up to date)")
                continue
            try:
                run_job(job, source_root=source_root)
                ok += 1
                if not quiet and not show_bar:
                    click.echo(f"ok     {_rel(job.dst, out_root)}")
            except ConversionError as e:
                failed += 1
                click.echo(f"FAIL   {job.src}: {e.reason}", err=True)
    return ok, skipped, failed


def _run_concurrent(
    jobs: list[ConvertJob], *, source_root: Path, out_root: Path,
    force: bool, quiet: bool, show_bar: bool, jobs_n: int,
) -> tuple[int, int, int]:
    ok = skipped = failed = 0
    pending: list[ConvertJob] = []
    for job in jobs:
        if not needs_update(job, force=force):
            skipped += 1
            if not quiet and not show_bar:
                click.echo(f"skip   {_rel(job.dst, out_root)} (up to date)")
        else:
            pending.append(job)

    if not pending:
        return ok, skipped, failed

    bar_cm = (
        click.progressbar(length=len(pending), label="converting", file=sys.stderr)
        if show_bar
        else nullcontext(None)
    )
    with bar_cm as bar:
        with ThreadPoolExecutor(max_workers=jobs_n) as ex:
            futures = {ex.submit(run_job, job, source_root=source_root): job for job in pending}
            for fut in as_completed(futures):
                job = futures[fut]
                try:
                    fut.result()
                    ok += 1
                    if not quiet and not show_bar:
                        click.echo(f"ok     {_rel(job.dst, out_root)}")
                except ConversionError as e:
                    failed += 1
                    click.echo(f"FAIL   {job.src}: {e.reason}", err=True)
                except Exception as e:
                    failed += 1
                    click.echo(f"FAIL   {job.src}: {type(e).__name__}: {e}", err=True)
                if bar is not None:
                    bar.update(1)
    return ok, skipped, failed


def _print_summary(
    ok: int, skipped: int, failed: int, out_root: Path, stats: ScanStats
) -> None:
    extras: list[str] = []
    if stats.excluded_dirs:
        extras.append(f"{stats.excluded_dirs} dirs excluded")
    if stats.excluded_hidden:
        extras.append(f"{stats.excluded_hidden} hidden")
    if stats.skipped_size:
        extras.append(f"{stats.skipped_size} oversize")
    if stats.skipped_out_root:
        extras.append(f"{stats.skipped_out_root} in out_root")
    if stats.skipped_symlink_loop:
        extras.append(f"{stats.skipped_symlink_loop} symlink loops")
    suffix = f" [{', '.join(extras)}]" if extras else ""
    summary = f"\n{ok} converted, {skipped} skipped, {failed} failed → {out_root}{suffix}"
    click.echo(summary, err=failed > 0)


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
@_scan_options
def watch(
    src: Path,
    output: Path | None,
    no_initial_sync: bool,
    force_initial_sync: bool,
    quiet: bool,
    max_size: str,
    pdf_max_size: str,
    include_hidden: bool,
    follow_symlinks: bool,
    ignore_file: Path | None,
    exclude: tuple[str, ...],
    respect_gitignore: bool,
    max_depth: int | None,
) -> None:
    """Watch SRC for changes and auto-convert them to Markdown.

    Runs in the foreground — press Ctrl-C to stop. Create/modify/delete/move
    events on supported file types trigger a debounced re-conversion.
    """
    from .watcher import Watcher

    src = src.resolve()
    out_root = output.resolve() if output else (src / "converted")

    try:
        cfg = _build_scan_config(
            max_size=max_size,
            pdf_max_size=pdf_max_size,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
            ignore_file=ignore_file,
            exclude=exclude,
            respect_gitignore=respect_gitignore,
            max_depth=max_depth,
        )
    except ValueError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)

    def _print_batch(messages: list[str]) -> None:
        for m in messages:
            if m.startswith("FAIL"):
                click.echo(m, err=True)
            elif not quiet:
                click.echo(m)

    watcher = Watcher(src, out_root, on_batch=_print_batch, scan_config=cfg)

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
