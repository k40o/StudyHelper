"""ChromaDB-backed vector store (persistent, cosine similarity)."""
from __future__ import annotations

from pathlib import Path

from .base import RetrievedChunk, VectorStore


def _sanitize(metadata: dict) -> dict:
    """Chroma rejects ``None`` metadata values; drop them and coerce types."""
    clean: dict = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: str | Path, collection_name: str = "study_chunks") -> None:
        import chromadb

        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        if not ids:
            return
        # upsert so re-indexing a changed document overwrites old chunks.
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=[_sanitize(m) for m in metadatas],
        )

    def query(self, embedding, n_results=5, where=None) -> list[RetrievedChunk]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where or None,
        )
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[RetrievedChunk] = []
        for i, chunk_id in enumerate(ids):
            # cosine distance -> similarity
            score = 1.0 - float(distances[i]) if i < len(distances) else 0.0
            chunks.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=docs[i] if i < len(docs) else "",
                    metadata=metas[i] if i < len(metas) else {},
                    score=score,
                )
            )
        return chunks

    def delete(self, ids=None, where=None) -> None:
        if ids is None and where is None:
            return
        self._collection.delete(ids=ids, where=where)

    def count(self) -> int:
        return self._collection.count()
