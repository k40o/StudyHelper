"""Composition root: builds and wires every service once at startup.

Keeping all construction in one place means routes just ask for a ready-made
``LibraryService`` and never new-up infrastructure themselves.
"""
from __future__ import annotations

import logging
import os

from ..application import (
    AuthService,
    GameService,
    IngestionService,
    LibraryService,
    QuestionGenerator,
    RagService,
    TutorService,
)
from ..core.config import Settings, load_ai_settings, load_settings
from ..infrastructure.ai import AIError, GeminiProvider
from ..infrastructure.persistence import Database
from ..infrastructure.vectorstore import ChromaVectorStore, SimpleVectorStore, VectorStore
from ..infrastructure.watcher import FolderWatcher

logger = logging.getLogger(__name__)


class Container:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.settings.ensure_dirs()

        # Persistence
        self.database = Database(self.settings.database_url)
        self.database.create_all()

        # Auth
        self.secret_key = self.settings.load_or_create_secret_key()
        self.auth = AuthService(self.database, self.secret_key)

        # AI + RAG (degrade gracefully if no key / provider fails to build)
        self.provider = self._build_provider()
        if self.provider is not None:
            store = self._build_vector_store()
            self.rag: RagService | None = RagService(self.provider, store)
            self.tutor: TutorService | None = TutorService(self.provider, self.rag)
            self.generator: QuestionGenerator | None = QuestionGenerator(self.provider)
        else:
            self.rag = None
            self.tutor = None
            self.generator = None

        # Coordinator + folder watcher
        ingestion = IngestionService(self.database)
        self.library = LibraryService(
            self.database, ingestion, self.rag, self.tutor, self.settings, self.generator
        )
        self.game = GameService(self.database)
        self.watcher = FolderWatcher(
            self.settings.study_materials_dir, self.library, self._resolve_watcher_owner
        )

    def _resolve_watcher_owner(self) -> int | None:
        """Files dropped straight into the watched folder (not uploaded through
        the UI) are attributed to the sole account, if there's exactly one —
        the common case for a personal desktop install. With zero or several
        accounts, ownership is ambiguous, so auto-import is skipped."""
        from ..infrastructure.persistence import UserRecord

        with self.database.session() as session:
            ids = session.query(UserRecord.id).all()
        return ids[0][0] if len(ids) == 1 else None

    def _build_vector_store(self) -> VectorStore:
        """Pick the vector backend. ``VECTOR_STORE=simple`` uses the dependency-light
        NumPy store (good for cheap cloud hosts); anything else uses ChromaDB when
        it's installed, falling back to the simple store."""
        kind = os.environ.get("VECTOR_STORE", "").strip().lower()
        if not kind:
            try:
                import chromadb  # noqa: F401

                kind = "chroma"
            except ImportError:
                kind = "simple"
        if kind == "simple":
            logger.info("Using SimpleVectorStore (NumPy)")
            return SimpleVectorStore(self.settings.data_dir / "vectors")
        logger.info("Using ChromaVectorStore")
        return ChromaVectorStore(self.settings.data_dir / "chroma")

    @staticmethod
    def _build_provider() -> GeminiProvider | None:
        ai_settings = load_ai_settings()
        if not ai_settings.is_configured:
            logger.warning("GEMINI_API_KEY not set — AI features disabled.")
            return None
        try:
            return GeminiProvider(ai_settings)
        except AIError as exc:  # pragma: no cover
            logger.error("Failed to init Gemini provider: %s", exc)
            return None

    def start(self) -> None:
        """Startup scan + begin live watching."""
        results = self.watcher.start(scan=True)
        changed = [r for r in results if r.changed]
        logger.info("Startup scan imported %d file(s)", len(changed))

    def stop(self) -> None:
        self.watcher.stop()
        self.database.dispose()
