"""Ingestion use-case: take a file path, parse it, and persist it — skipping
files that are unsupported or unchanged since last import.

This is the orchestration layer: it wires the parsing service to the repository
but contains no parsing or SQL details of its own.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..infrastructure.parsing import DocumentParsingService, ParserError
from ..infrastructure.persistence import Database, DocumentRepository

logger = logging.getLogger(__name__)

_HASH_CHUNK = 1 << 20  # 1 MiB


class IngestStatus(str, Enum):
    IMPORTED = "imported"      # newly added
    UPDATED = "updated"        # existed, file changed, re-imported
    UNCHANGED = "unchanged"    # already imported, identical content
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass
class IngestResult:
    path: str
    status: IngestStatus
    title: str | None = None
    blocks: int = 0
    error: str | None = None

    @property
    def changed(self) -> bool:
        return self.status in (IngestStatus.IMPORTED, IngestStatus.UPDATED)


class IngestionService:
    def __init__(self, database: Database, parsing_service: DocumentParsingService | None = None) -> None:
        self._db = database
        self._parser = parsing_service or DocumentParsingService()

    @property
    def supported_extensions(self) -> set[str]:
        return self._parser.supported_extensions

    def ingest_file(self, path: str | Path, user_id: int) -> IngestResult:
        path = Path(path)
        path_str = str(path)

        if not self._parser.can_parse(path):
            return IngestResult(path_str, IngestStatus.UNSUPPORTED)

        try:
            content_hash = self._hash_file(path)
        except OSError as exc:
            return IngestResult(path_str, IngestStatus.FAILED, error=str(exc))

        try:
            with self._db.unit_of_work() as session:
                repo = DocumentRepository(session)
                existing_hash = repo.hash_for_path(path_str)
                if existing_hash == content_hash:
                    return IngestResult(path_str, IngestStatus.UNCHANGED)

                parsed = self._parser.parse(path)
                record = repo.upsert(parsed, content_hash, user_id)
                block_count = len(parsed.blocks)
                title = record.title
                status = IngestStatus.UPDATED if existing_hash else IngestStatus.IMPORTED

            logger.info("Ingested %s (%s, %d blocks)", path.name, status.value, block_count)
            return IngestResult(path_str, status, title=title, blocks=block_count)

        except (ParserError, FileNotFoundError) as exc:
            logger.warning("Failed to ingest %s: %s", path, exc)
            return IngestResult(path_str, IngestStatus.FAILED, error=str(exc))

    def scan_folder(self, folder: str | Path, user_id: int) -> list[IngestResult]:
        """Recursively ingest every supported file in ``folder``, attributed to
        ``user_id`` (used for the single-owner desktop folder watcher)."""
        folder = Path(folder)
        results: list[IngestResult] = []
        if not folder.exists():
            return results
        for file in sorted(folder.rglob("*")):
            if file.is_file() and self._parser.can_parse(file):
                results.append(self.ingest_file(file, user_id))
        return results

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while chunk := fh.read(_HASH_CHUNK):
                h.update(chunk)
        return h.hexdigest()
