"""Shared pandoc subprocess helper for DOCX / PPTX / (future) HTML / EPUB."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..utils import strip_base64_images
from .base import ConversionError, ConvertResult


def run_pandoc(src: Path, from_fmt: str, timeout: int = 120) -> ConvertResult:
    """Convert src via `pandoc --from=<from_fmt> --to=gfm --wrap=none`.

    Returns a ConvertResult with base64 images stripped. Raises ConversionError
    with an actionable message if pandoc is missing, times out, or exits non-zero.
    """
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise ConversionError(
            src,
            "pandoc not found on PATH. Install it:\n"
            "  macOS:  brew install pandoc\n"
            "  Ubuntu: apt install pandoc\n"
            "  Other:  https://pandoc.org/installing.html",
        )

    try:
        result = subprocess.run(
            [pandoc, f"--from={from_fmt}", "--to=gfm", "--wrap=none", str(src)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ConversionError(src, f"pandoc timed out after {timeout}s") from e
    except OSError as e:
        raise ConversionError(src, f"failed to run pandoc: {e}") from e

    if result.returncode != 0:
        raise ConversionError(
            src, f"pandoc exited {result.returncode}: {result.stderr.strip()[:200]}"
        )

    body, stripped = strip_base64_images(result.stdout)
    warnings: list[str] = []
    if stripped:
        warnings.append(f"stripped {stripped} inline base64 image(s)")

    return ConvertResult(body=body, title=src.stem, warnings=warnings)
