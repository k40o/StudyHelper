"""A dependency-light vector store (NumPy cosine similarity, JSON persistence).

For a personal study corpus (thousands of chunks) a brute-force cosine search is
plenty fast, and it avoids ChromaDB's heavy native dependencies — which makes the
app deployable on tiny/free cloud instances. Selected via ``VECTOR_STORE=simple``.
Implements the same :class:`VectorStore` interface as the Chroma backend.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import RetrievedChunk, VectorStore


def _matches(metadata: dict, where: dict | None) -> bool:
    if not where:
        return True
    return all(metadata.get(k) == v for k, v in where.items())


class SimpleVectorStore(VectorStore):
    def __init__(self, persist_dir: str | Path, collection_name: str = "study_chunks") -> None:
        self._dir = Path(persist_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{collection_name}.json"
        # id -> {"vec": [...], "doc": str, "meta": {...}}
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data), encoding="utf-8")

    def add(self, ids, embeddings, documents, metadatas) -> None:
        if not ids:
            return
        for i, chunk_id in enumerate(ids):
            self._data[chunk_id] = {
                "vec": [float(x) for x in embeddings[i]],
                "doc": documents[i],
                "meta": metadatas[i],
            }
        self._save()

    def query(self, embedding, n_results=5, where=None) -> list[RetrievedChunk]:
        items = [(cid, r) for cid, r in self._data.items() if _matches(r["meta"], where)]
        if not items:
            return []
        import numpy as np

        mat = np.array([r["vec"] for _, r in items], dtype=float)
        q = np.array(embedding, dtype=float)
        mat_norm = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        q_norm = q / (np.linalg.norm(q) + 1e-9)
        sims = mat_norm @ q_norm
        top = np.argsort(-sims)[:n_results]
        return [
            RetrievedChunk(
                id=items[int(i)][0],
                text=items[int(i)][1]["doc"],
                metadata=items[int(i)][1]["meta"],
                score=float(sims[int(i)]),
            )
            for i in top
        ]

    def delete(self, ids=None, where=None) -> None:
        removed = False
        if ids:
            for cid in ids:
                if self._data.pop(cid, None) is not None:
                    removed = True
        if where:
            for cid in [c for c, r in self._data.items() if _matches(r["meta"], where)]:
                self._data.pop(cid, None)
                removed = True
        if removed:
            self._save()

    def count(self) -> int:
        return len(self._data)
