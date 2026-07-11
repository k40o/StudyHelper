"""AI provider interface.

Everything in the app talks to AI through this interface, never to a specific
vendor. Swapping Gemini for Ollama (or a mock in tests) means implementing this
one class — no other code changes (Dependency Inversion).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIError(Exception):
    """Raised for any provider-level failure (network, quota, bad response)."""


class QuotaExceededError(AIError):
    """The account has run out of API quota. Unlike a transient rate limit,
    retrying within seconds won't help — callers doing bulk work (e.g.
    per-chunk question generation) should stop entirely rather than retry
    every remaining call and wait through certain repeated failures."""


class AIProvider(ABC):
    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimensionality of vectors returned by :meth:`embed`."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Return the model's text completion for ``prompt``."""

    @abstractmethod
    def embed(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        """Return an embedding vector for a single piece of text."""

    def embed_batch(
        self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Embed many texts. Default loops :meth:`embed`; providers may override
        with a true batch call for efficiency."""
        return [self.embed(t, task_type=task_type) for t in texts]
