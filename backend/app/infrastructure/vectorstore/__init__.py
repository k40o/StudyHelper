"""Vector store package: embeddings storage + similarity search for RAG."""
from .base import RetrievedChunk, VectorStore
from .chroma_store import ChromaVectorStore
from .simple_store import SimpleVectorStore

__all__ = ["VectorStore", "RetrievedChunk", "ChromaVectorStore", "SimpleVectorStore"]
