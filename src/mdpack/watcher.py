"""File-system watcher that auto-converts changes from a source dir to Markdown."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .converters.base import ConversionError
from .registry import find_converter, supported_extensions
from .scanner import ScanConfig, Scanner
from .walker import ConvertJob, needs_update, resolve_dst, run_job

log = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 1.5


@dataclass
class WatchStatus:
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str = ""
    consecutive_errors: int = 0
    pending_paths: set[Path] = field(default_factory=set)


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "Watcher") -> None:
        self.watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:  # pragma: no cover - trivial
        self._dispatch(event.src_path, deleted=False)

    def on_modified(self, event: FileSystemEvent) -> None:  # pragma: no cover - trivial
        self._dispatch(event.src_path, deleted=False)

    def on_deleted(self, event: FileSystemEvent) -> None:  # pragma: no cover - trivial
        self._dispatch(event.src_path, deleted=True)

    def on_moved(self, event: FileSystemEvent) -> None:  # pragma: no cover - trivial
        self._dispatch(event.src_path, deleted=True)
        dest = getattr(event, "dest_path", None)
        if dest:
            self._dispatch(dest, deleted=False)

    def _dispatch(self, raw_path: str, *, deleted: bool) -> None:
        if not raw_path:
            return
        path = Path(raw_path)
        if path.is_dir():
            return
        self.watcher._on_event(path, deleted=deleted)


class Watcher:
    """Watches src_root and keeps out_root in sync as Markdown.

    Designed to be run by `mdpack watch` in the foreground. One Observer, one
    debounce timer. Events are coalesced into pending_paths; when the timer fires,
    every pending path is converted (or deleted) in one batch.
    """

    def __init__(
        self,
        src_root: Path,
        out_root: Path,
        *,
        on_batch: Callable[[list[str]], None] | None = None,
        scan_config: ScanConfig | None = None,
    ) -> None:
        self.src_root = src_root.resolve()
        self.out_root = out_root.resolve()
        self._pending: dict[Path, bool] = {}  # path -> deleted flag
        self._pending_lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._observer: Observer | None = None
        self.status = WatchStatus()
        self._on_batch = on_batch
        self._exts = {e.lower() for e in supported_extensions()}
        self._scan_config = scan_config or ScanConfig()

    def initial_sync(self, force: bool = False) -> tuple[int, int, int]:
        """Run an incremental pass to bring out_root up to date with src_root."""
        ok = skipped = failed = 0
        for job in Scanner(self._scan_config).scan(self.src_root, self.out_root):
            if not needs_update(job, force=force):
                skipped += 1
                continue
            try:
                run_job(job, source_root=self.src_root)
                ok += 1
            except ConversionError as e:
                failed += 1
                log.error("initial sync failed for %s: %s", e.src, e.reason)
        return ok, skipped, failed

    def start(self) -> None:
        self._observer = Observer()
        self._observer.schedule(_Handler(self), str(self.src_root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def _is_relevant(self, path: Path) -> bool:
        if path.suffix.lower() not in self._exts:
            return False
        try:
            path.resolve().relative_to(self.out_root)
        except ValueError:
            return True
        return False  # path lives under out_root — ignore, it's our own output

    def _on_event(self, path: Path, *, deleted: bool) -> None:
        if not self._is_relevant(path):
            return
        with self._pending_lock:
            if deleted and path in self._pending and not self._pending[path]:
                return
            self._pending[path] = deleted
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._pending_lock:
            batch = list(self._pending.items())
            self._pending.clear()
            self._timer = None

        messages: list[str] = []
        for path, deleted in batch:
            try:
                msg = self._process(path, deleted=deleted)
            except ConversionError as e:
                self.status.last_error_at = datetime.now(timezone.utc)
                self.status.last_error_message = e.reason
                self.status.consecutive_errors += 1
                messages.append(f"FAIL {path}: {e.reason}")
                log.error("%s: %s", path, e.reason)
                continue
            except Exception as e:
                self.status.last_error_at = datetime.now(timezone.utc)
                self.status.last_error_message = f"{type(e).__name__}: {e}"
                self.status.consecutive_errors += 1
                messages.append(f"FAIL {path}: {e}")
                log.exception("unexpected watcher error")
                continue
            if msg is not None:
                messages.append(msg)

        if not self.status.last_error_message or messages and all(
            not m.startswith("FAIL") for m in messages
        ):
            self.status.last_success_at = datetime.now(timezone.utc)
            self.status.consecutive_errors = 0

        if self._on_batch is not None and messages:
            self._on_batch(messages)

    def _process(self, src: Path, *, deleted: bool) -> str | None:
        dst = resolve_dst(src, self.src_root, self.out_root)

        if deleted:
            if dst.exists():
                dst.unlink()
                return f"del  {dst.relative_to(self.out_root)}"
            return None

        if not src.exists():
            if dst.exists():
                dst.unlink()
                return f"del  {dst.relative_to(self.out_root)}"
            return None

        conv = find_converter(src.suffix)
        if conv is None:
            return None

        job = ConvertJob(src=src, dst=dst, converter_name=conv.name)
        run_job(job, source_root=self.src_root)
        return f"ok   {dst.relative_to(self.out_root)}"
