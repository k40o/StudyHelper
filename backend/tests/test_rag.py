"""Tests for Module 3: chunking, RAG retrieval, and the AI tutor.

Uses ChromaDB for real vector storage/search and the offline FakeProvider for
embeddings/generation.
"""
from __future__ import annotations

import pytest

from app.application import RagService, TutorService, chunk_document
from app.domain.document import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    SourceLocation,
    SourceType,
)
from app.infrastructure.vectorstore import ChromaVectorStore, SimpleVectorStore


def _biology_doc() -> ParsedDocument:
    return ParsedDocument(
        file_path="/study/biology.pptx",
        source_type=SourceType.PPTX,
        title="Cell Biology",
        blocks=[
            ContentBlock("Mitochondria", BlockType.HEADING, 1, SourceLocation(slide=1)),
            ContentBlock(
                "Mitochondria are the powerhouse of the cell and produce ATP energy.",
                BlockType.PARAGRAPH,
                location=SourceLocation(slide=1),
            ),
            ContentBlock("Photosynthesis", BlockType.HEADING, 1, SourceLocation(slide=2)),
            ContentBlock(
                "Chloroplasts capture sunlight to make glucose during photosynthesis.",
                BlockType.PARAGRAPH,
                location=SourceLocation(slide=2),
            ),
        ],
    )


@pytest.fixture
def store(tmp_path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "chroma", collection_name="test")


# --------------------------------------------------------------------------- #
# Chunking (pure)
# --------------------------------------------------------------------------- #
def test_chunking_preserves_heading_and_location():
    chunks = chunk_document(_biology_doc(), max_chars=200, min_chars=10)
    assert len(chunks) == 2
    mito, photo = chunks
    assert mito.heading == "Mitochondria"
    assert mito.slide == 1
    assert photo.heading == "Photosynthesis"
    assert photo.slide == 2


# --------------------------------------------------------------------------- #
# RAG retrieval
# --------------------------------------------------------------------------- #
def test_index_and_retrieve(fake_provider, store):
    rag = RagService(fake_provider, store)
    n = rag.index_document(_biology_doc(), document_id=1, user_id=1)
    assert n == 2
    assert rag.chunk_count == 2

    hits = rag.retrieve("mitochondria energy", user_id=1, k=2)
    assert hits
    assert "Mitochondria" in hits[0].text  # most relevant chunk first
    assert hits[0].metadata["slide"] == 1


def test_retrieve_is_scoped_to_user(fake_provider, store):
    # Two accounts, two documents — one user must never see the other's chunks.
    rag = RagService(fake_provider, store)
    rag.index_document(_biology_doc(), document_id=1, user_id=1)
    rag.index_document(_biology_doc(), document_id=2, user_id=2)

    hits = rag.retrieve("mitochondria energy", user_id=1, k=5)
    assert hits and all(h.metadata["user_id"] == 1 for h in hits)


def test_simple_store_index_retrieve_delete(fake_provider, tmp_path):
    # The NumPy-based store used for lean deployments must behave like Chroma.
    store = SimpleVectorStore(tmp_path / "vectors", collection_name="test")
    rag = RagService(fake_provider, store)
    rag.index_document(_biology_doc(), document_id=1, user_id=1)
    assert rag.chunk_count == 2

    hits = rag.retrieve("photosynthesis chloroplast", user_id=1, k=2)
    assert hits and "Photosynthesis" in hits[0].text

    # Persistence: a fresh instance reads the saved file.
    reopened = SimpleVectorStore(tmp_path / "vectors", collection_name="test")
    assert reopened.count() == 2

    store.delete(where={"document_id": 1})
    assert store.count() == 0


def test_reindex_replaces_chunks(fake_provider, store):
    rag = RagService(fake_provider, store)
    rag.index_document(_biology_doc(), document_id=1, user_id=1)
    # Re-index the same doc id: count stays 2, no duplicates.
    rag.index_document(_biology_doc(), document_id=1, user_id=1)
    assert rag.chunk_count == 2


# --------------------------------------------------------------------------- #
# Tutor grounding
# --------------------------------------------------------------------------- #
def test_tutor_answers_from_materials(fake_provider, store):
    rag = RagService(fake_provider, store)
    rag.index_document(_biology_doc(), document_id=1, user_id=1)

    tutor = TutorService(fake_provider, rag, min_score=0.2)
    answer = tutor.answer("What do mitochondria do?", user_id=1)

    assert answer.grounded
    assert fake_provider.generate_calls  # the model WAS asked
    assert answer.sources
    assert answer.sources[0].location == "slide 1"


def test_tutor_refuses_when_not_in_materials(fake_provider, store):
    rag = RagService(fake_provider, store)
    rag.index_document(_biology_doc(), document_id=1, user_id=1)

    tutor = TutorService(fake_provider, rag, min_score=0.4)
    answer = tutor.answer("Explain quantum chromodynamics gluon confinement", user_id=1)

    assert not answer.grounded
    assert "couldn't find" in answer.text.lower()
    # Crucially, the model is never called when nothing relevant is retrieved.
    assert fake_provider.generate_calls == []


def test_tutor_handles_empty_question(fake_provider, store):
    tutor = TutorService(fake_provider, RagService(fake_provider, store))
    answer = tutor.answer("   ", user_id=1)
    assert not answer.grounded
