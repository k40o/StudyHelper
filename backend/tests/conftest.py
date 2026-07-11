"""Shared test fixtures, including an offline fake AI provider.

FakeProvider gives deterministic, keyword-based embeddings: two texts that
share words get similar vectors. That's enough to test the RAG/tutor plumbing
without hitting the network or spending Gemini quota.
"""
from __future__ import annotations

import math
import re
import zlib

import pytest

from app.core.security import hash_password
from app.infrastructure.ai import AIProvider
from app.infrastructure.persistence import Database, UserRepository


def create_test_user(db: Database, email: str = "student@example.com") -> int:
    """Insert a user row directly (bypassing AuthService/HTTP) so tests that
    exercise repositories/services below the API layer have a valid owner to
    satisfy the ``documents.user_id`` / ``player.user_id`` foreign keys."""
    with db.unit_of_work() as session:
        return UserRepository(session).create(email, hash_password("testpass123")).id


class FakeProvider(AIProvider):
    def __init__(self, dim: int = 64, answer: str = "The answer, per your notes, is X [1].") -> None:
        self._dim = dim
        self._answer = answer
        self.generate_calls: list[str] = []
        self.embed_calls: list[str] = []

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def generate(self, prompt, *, system=None, temperature=0.7, max_output_tokens=None, json_mode=False):
        self.generate_calls.append(prompt)
        return self._answer

    def embed(self, text, *, task_type="RETRIEVAL_DOCUMENT"):
        self.embed_calls.append(text)
        vec = [0.0] * self._dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vec[zlib.crc32(word.encode()) % self._dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()
