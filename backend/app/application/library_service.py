"""Library service: the high-level coordinator for the knowledge base.

Composes ingestion (parse + store) with RAG (embed + index) so that a file is
searchable the moment it's imported. This is the single object the API and the
folder watcher talk to.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..core.config import Settings
from ..infrastructure.persistence import (
    Database,
    DocumentRepository,
    QuestionRepository,
    record_to_domain,
)
from .ingestion_service import IngestionService, IngestResult
from .question_generator import QuestionGenerator
from .rag_service import RagService
from .tutor_service import TutorAnswer, TutorService

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(
        self,
        database: Database,
        ingestion: IngestionService,
        rag: RagService | None,
        tutor: TutorService | None,
        settings: Settings,
        generator: QuestionGenerator | None = None,
    ) -> None:
        self._db = database
        self._ingestion = ingestion
        self._rag = rag
        self._tutor = tutor
        self._settings = settings
        self._generator = generator

    # -- Watcher/importer interface (duck-typed for FolderWatcher) --------- #
    @property
    def supported_extensions(self) -> set[str]:
        return self._ingestion.supported_extensions

    def ingest_file(self, path, user_id: int) -> IngestResult:
        """Import one file: store it, then (re)index it for RAG if AI is on."""
        result = self._ingestion.ingest_file(path, user_id)
        if result.changed and self._rag is not None:
            self._index_path(str(path))
        return result

    def scan_folder(self, folder, user_id: int) -> list[IngestResult]:
        """Recursively import + index every supported file in a folder.

        Mirrors ``IngestionService.scan_folder`` but routes through
        :meth:`ingest_file` so each file is also RAG-indexed. This makes
        LibraryService a full drop-in for the FolderWatcher.
        """
        from pathlib import Path

        folder = Path(folder)
        results: list[IngestResult] = []
        if not folder.exists():
            return results
        for file in sorted(folder.rglob("*")):
            if file.is_file() and file.suffix.lower() in self.supported_extensions:
                results.append(self.ingest_file(file, user_id))
        return results

    def _index_path(self, path_str: str) -> None:
        with self._db.session() as session:
            record = DocumentRepository(session).get_by_path(path_str)
            if record is None:
                return
            doc = record_to_domain(record)
            document_id = record.id
            user_id = record.user_id
        try:
            self._rag.index_document(doc, document_id, user_id)
        except Exception:  # never let indexing failure break import
            logger.exception("RAG indexing failed for %s", path_str)

    # -- Read/query API ---------------------------------------------------- #
    def list_documents(self, user_id: int) -> list[dict]:
        with self._db.session() as session:
            records = DocumentRepository(session).list_all(user_id)
            q_repo = QuestionRepository(session)
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "file_path": r.file_path,
                    "source_type": r.source_type,
                    "word_count": r.word_count,
                    "blocks": len(r.blocks),
                    "questions": q_repo.count(r.id),
                }
                for r in records
            ]

    # -- Deletion ---------------------------------------------------------- #
    def delete_document(self, document_id: int, user_id: int) -> bool:
        """Remove a document everywhere: vector chunks, DB row, and the file.

        The file is moved to a trash folder (not hard-deleted) so it won't be
        re-imported on the next startup scan, but can still be recovered.
        """
        with self._db.session() as session:
            record = DocumentRepository(session).get_by_id(document_id, user_id)
            if record is None:
                return False
            file_path = record.file_path

        if self._rag is not None:
            self._rag.remove_document(document_id)
        with self._db.unit_of_work() as session:
            DocumentRepository(session).delete_by_id(document_id)
        self._trash_file(file_path)
        logger.info("Deleted document %s (%s)", document_id, file_path)
        return True

    def remove_by_path(self, file_path) -> bool:
        """Sync-remove a document whose file was deleted outside the app
        (used by the folder watcher). Does not touch the filesystem."""
        file_path = str(file_path)
        with self._db.session() as session:
            record = DocumentRepository(session).get_by_path(file_path)
            if record is None:
                return False
            document_id = record.id

        if self._rag is not None:
            self._rag.remove_document(document_id)
        with self._db.unit_of_work() as session:
            DocumentRepository(session).delete_by_path(file_path)
        logger.info("Removed document for deleted file %s", file_path)
        return True

    def _trash_file(self, file_path: str) -> None:
        src = Path(file_path)
        if not src.exists():
            return
        trash_dir = self._settings.data_dir / ".trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        dest = trash_dir / src.name
        # Avoid clobbering an existing trashed file of the same name.
        counter = 1
        while dest.exists():
            dest = trash_dir / f"{src.stem}({counter}){src.suffix}"
            counter += 1
        try:
            shutil.move(str(src), str(dest))
        except OSError:
            logger.exception("Could not move %s to trash", src)

    # -- Questions --------------------------------------------------------- #
    def generate_questions(
        self, document_id: int, user_id: int, *, max_questions: int = 30, per_chunk: int = 3
    ) -> dict | None:
        """Generate and store questions for a document. Returns counts, or None
        if the document doesn't exist (or doesn't belong to this user)."""
        with self._db.session() as session:
            record = DocumentRepository(session).get_by_id(document_id, user_id)
            if record is None:
                return None
            doc = record_to_domain(record)

        if self._generator is None:
            return {
                "generated": 0,
                "total": self.question_count(user_id, document_id),
                "ai_enabled": False,
                "quota_exceeded": False,
            }

        batch = self._generator.generate_for_document(
            doc, document_id, per_chunk=per_chunk, max_questions=max_questions
        )
        with self._db.unit_of_work() as session:
            stored = QuestionRepository(session).add_many(batch.questions)
        return {
            "generated": stored,
            "total": self.question_count(user_id, document_id),
            "ai_enabled": True,
            "quota_exceeded": batch.quota_exceeded,
        }

    def list_questions(self, document_id: int, user_id: int) -> list[dict]:
        with self._db.session() as session:
            if DocumentRepository(session).get_by_id(document_id, user_id) is None:
                return []
            return [_q_dict(r) for r in QuestionRepository(session).list_by_document(document_id)]

    def random_questions(
        self, limit: int, user_id: int, document_id: int | None = None
    ) -> list[dict]:
        with self._db.session() as session:
            if document_id is not None:
                if DocumentRepository(session).get_by_id(document_id, user_id) is None:
                    return []
            return [
                _q_dict(r)
                for r in QuestionRepository(session).random(limit, user_id, document_id)
            ]

    def question_count(self, user_id: int, document_id: int | None = None) -> int:
        with self._db.session() as session:
            repo = QuestionRepository(session)
            return repo.count(document_id) if document_id is not None else repo.count_for_user(user_id)

    @property
    def ai_enabled(self) -> bool:
        return self._rag is not None and self._tutor is not None

    def search(self, query: str, user_id: int, k: int = 5) -> list[dict]:
        if self._rag is None:
            return []
        return [
            {
                "text": c.text,
                "title": c.metadata.get("title"),
                "source_type": c.metadata.get("source_type"),
                "page": c.metadata.get("page"),
                "slide": c.metadata.get("slide"),
                "score": round(c.score, 3),
            }
            for c in self._rag.retrieve(query, user_id, k=k)
        ]

    def ask(self, question: str, user_id: int) -> TutorAnswer:
        if self._tutor is None:
            return TutorAnswer("AI is not configured.", grounded=False)
        return self._tutor.answer(question, user_id)


def _q_dict(r) -> dict:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "question_type": r.question_type,
        "prompt": r.prompt,
        "answer": r.answer,
        "explanation": r.explanation or "",
        "difficulty": r.difficulty,
        "topic": r.topic or "",
        "options": list(r.options or []),
        "answer_data": dict(r.answer_data or {}),
        "source_title": r.source_title or "",
        "source_location": r.source_location or "",
    }
