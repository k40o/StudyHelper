"""RAG indexing + retrieval.

Indexing: document -> chunks -> embeddings -> vector store.
Retrieval: query -> embedding -> nearest chunks (with citations).

Retrieval is what keeps the AI honest: the tutor and question generator only
ever see text that actually came from the student's own materials.
"""
from __future__ import annotations

import logging

from ..domain.document import ParsedDocument
from ..infrastructure.ai import AIProvider
from ..infrastructure.vectorstore import RetrievedChunk, VectorStore
from .chunking import Chunk, chunk_document

logger = logging.getLogger(__name__)


class RagService:
    def __init__(self, provider: AIProvider, store: VectorStore) -> None:
        self._provider = provider
        self._store = store

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #
    def index_document(self, doc: ParsedDocument, document_id: int, user_id: int) -> int:
        """Embed and store all chunks for one document. Idempotent: existing
        chunks for this document are replaced."""
        chunks = chunk_document(doc)
        # Clear any previous chunks for this document (handles edits/shrink).
        self._store.delete(where={"document_id": document_id})
        if not chunks:
            return 0

        embed_inputs = [self._embedding_input(doc, c) for c in chunks]
        embeddings = self._provider.embed_batch(embed_inputs, task_type="RETRIEVAL_DOCUMENT")

        ids = [f"{document_id}:{c.index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "file_path": doc.file_path,
                "title": doc.title,
                "source_type": doc.source_type.value,
                "heading": c.heading,
                "page": c.page,
                "slide": c.slide,
            }
            for c in chunks
        ]
        self._store.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        logger.info("Indexed %d chunks for document %s", len(chunks), document_id)
        return len(chunks)

    def remove_document(self, document_id: int) -> None:
        self._store.delete(where={"document_id": document_id})

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def retrieve(
        self, query: str, user_id: int, *, k: int = 5, min_score: float = 0.0
    ) -> list[RetrievedChunk]:
        """Retrieve only from ``user_id``'s own indexed materials — the vector
        store is shared across all accounts, so this filter is what keeps one
        student's notes out of another's tutor answers."""
        query_embedding = self._provider.embed(query, task_type="RETRIEVAL_QUERY")
        results = self._store.query(query_embedding, n_results=k, where={"user_id": user_id})
        return [r for r in results if r.score >= min_score]

    @property
    def chunk_count(self) -> int:
        return self._store.count()

    @staticmethod
    def _embedding_input(doc: ParsedDocument, chunk: Chunk) -> str:
        """Prepend title/heading context so embeddings capture topic, not just
        the raw sentence."""
        prefix_parts = [p for p in (doc.title, chunk.heading) if p]
        prefix = " > ".join(dict.fromkeys(prefix_parts))  # dedupe, keep order
        return f"{prefix}\n{chunk.text}" if prefix else chunk.text
