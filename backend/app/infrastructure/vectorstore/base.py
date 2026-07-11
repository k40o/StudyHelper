"""Vector store interface + retrieval result type.

The RAG pipeline depends on this abstraction, so ChromaDB can be swapped for
FAISS or an in-memory store without touching retrieval logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    id: str
    text: str
    metadata: dict
    score: float  # cosine similarity in [0, 1]; higher is more relevant


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    def query(
        self, embedding: list[float], n_results: int = 5, where: dict | None = None
    ) -> list[RetrievedChunk]: ...

    @abstractmethod
    def delete(self, ids: list[str] | None = None, where: dict | None = None) -> None: ...

    @abstractmethod
    def count(self) -> int: ...
