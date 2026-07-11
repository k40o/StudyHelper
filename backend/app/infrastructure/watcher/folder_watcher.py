"""Folder watcher: auto-import study files.

Two mechanisms, as chosen for this project:
  1. **Startup scan** — recursively ingest everything already in the folder
     (catches files added while the app was closed).
  2. **Live watch** — a watchdog observer fires on new/changed/moved files.

Live events are *debounced*: editors and copy operations emit a burst of
"modified" events, and a file may still be mid-write. We wait a short settle
period after the last event before ingesting, so we never parse a half-written
file.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ...application.ingestion_service import IngestionService, IngestResult

logger = logging.getLogger(__name__)

ResultCallback = Callable[[IngestResult], None]


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(
        self,
        callback: Callable[[Path], None],
        extensions: set[str],
        settle: float,
        delete_callback: Callable[[Path], None] | None = None,
    ) -> None:
        self._callback = callback
        self._delete_callback = delete_callback
        self._extensions = extensions
        self._settle = settle
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def _handle_delete(self, raw_path: str) -> None:
        path = Path(raw_path)
        if path.suffix.lower() not in self._extensions or self._delete_callback is None:
            return
        # Cancel any pending import for this path first.
        with self._lock:
            if (existing := self._timers.pop(path, None)) is not None:
                existing.cancel()
        self._delete_callback(path)

    def _schedule(self, raw_path: str) -> None:
        path = Path(raw_path)
        if path.suffix.lower() not in self._extensions:
            return
        with self._lock:
            if (existing := self._timers.get(path)) is not None:
                existing.cancel()
            timer = threading.Timer(self._settle, self._fire, args=(path,))
            self._timers[path] = timer
            timer.start()

    def _fire(self, path: Path) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if path.exists():
            self._callback(path)

    def cancel_all(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_delete(event.src_path)  # gone from its old path
            self._schedule(event.dest_path)  # arrived at new path

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_delete(event.src_path)


class FolderWatcher:
    """Auto-imports files dropped in a folder, attributed to a single "owner"
    account — the natural model for a personal desktop install where one
    person uses the app on their own machine. ``owner_provider`` is re-queried
    on every event/scan (rather than fixed at construction) so watching can
    start before that account exists yet and pick it up once it does.
    """

    def __init__(
        self,
        folder: str | Path,
        ingestion_service: IngestionService,
        owner_provider: Callable[[], int | None],
        on_result: ResultCallback | None = None,
        settle_seconds: float = 0.4,
    ) -> None:
        self._folder = Path(folder)
        self._ingest = ingestion_service
        self._owner_provider = owner_provider
        self._on_result = on_result
        self._observer: Observer | None = None
        # Only sync deletions if the importer knows how to remove by path
        # (LibraryService does; the bare IngestionService does not).
        delete_cb = getattr(ingestion_service, "remove_by_path", None)
        self._handler = _DebouncedHandler(
            callback=self._ingest_and_report,
            extensions=ingestion_service.supported_extensions,
            settle=settle_seconds,
            delete_callback=delete_cb,
        )

    def _ingest_and_report(self, path: Path) -> IngestResult | None:
        owner = self._owner_provider()
        if owner is None:
            logger.warning("Skipping %s: no single account to attribute it to yet", path)
            return None
        result = self._ingest.ingest_file(path, owner)
        if self._on_result is not None:
            self._on_result(result)
        return result

    def scan_existing(self) -> list[IngestResult]:
        """Startup scan of everything already in the folder."""
        owner = self._owner_provider()
        if owner is None:
            logger.warning("Skipping startup scan: no single account to attribute files to yet")
            return []
        results = self._ingest.scan_folder(self._folder, owner)
        if self._on_result is not None:
            for result in results:
                self._on_result(result)
        return results

    def start(self, scan: bool = True) -> list[IngestResult]:
        """Scan existing files (optional) then begin live watching."""
        self._folder.mkdir(parents=True, exist_ok=True)
        initial = self.scan_existing() if scan else []

        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._folder), recursive=True)
        self._observer.start()
        logger.info("Watching %s for study files", self._folder)
        return initial

    def stop(self) -> None:
        self._handler.cancel_all()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
