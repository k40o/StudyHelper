"""AI Tutor: answer a student's question using ONLY their uploaded materials.

Guardrails against hallucination:
  * We retrieve real chunks first; if none clear a relevance threshold, we
    short-circuit and honestly say the answer isn't in their materials — the
    model is never even asked.
  * When we do call the model, the system prompt and context format force it to
    ground every claim in the numbered sources and cite them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..infrastructure.ai import AIProvider
from .rag_service import RagService

_SYSTEM_PROMPT = (
    "You are a focused study tutor. Answer the student's question using ONLY the "
    "numbered context passages provided, which come from the student's own study "
    "materials. Rules:\n"
    "1. If the context does not contain the answer, reply exactly: "
    "\"I couldn't find this in your study materials.\"\n"
    "2. Never use outside knowledge or invent facts.\n"
    "3. Cite the sources you used with their bracket numbers, e.g. [1], [2].\n"
    "4. Be clear and concise, like a good teacher."
)

_NOT_FOUND = "I couldn't find this in your study materials."


@dataclass
class Source:
    title: str
    location: str  # e.g. "slide 3" or "page 12" or ""
    score: float


@dataclass
class TutorAnswer:
    text: str
    grounded: bool
    sources: list[Source] = field(default_factory=list)


class TutorService:
    def __init__(
        self,
        provider: AIProvider,
        rag: RagService,
        *,
        k: int = 5,
        min_score: float = 0.40,
    ) -> None:
        self._provider = provider
        self._rag = rag
        self._k = k
        self._min_score = min_score

    def answer(self, question: str, user_id: int) -> TutorAnswer:
        question = question.strip()
        if not question:
            return TutorAnswer(_NOT_FOUND, grounded=False)

        chunks = self._rag.retrieve(question, user_id, k=self._k)
        relevant = [c for c in chunks if c.score >= self._min_score]
        if not relevant:
            # Nothing in the materials is close enough — don't even ask the model.
            return TutorAnswer(_NOT_FOUND, grounded=False)

        context = self._format_context(relevant)
        prompt = (
            f"Context passages:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the context above, and cite the passages you used."
        )
        text = self._provider.generate(prompt, system=_SYSTEM_PROMPT, temperature=0.2)

        sources = [
            Source(
                title=c.metadata.get("title", "Untitled"),
                location=_location_str(c.metadata),
                score=round(c.score, 3),
            )
            for c in relevant
        ]
        grounded = _NOT_FOUND.lower() not in text.lower()
        return TutorAnswer(text=text, grounded=grounded, sources=sources)

    @staticmethod
    def _format_context(chunks) -> str:
        lines = []
        for i, c in enumerate(chunks, start=1):
            loc = _location_str(c.metadata)
            title = c.metadata.get("title", "Untitled")
            citation = f"{title}, {loc}" if loc else title
            lines.append(f"[{i}] ({citation})\n{c.text}")
        return "\n\n".join(lines)


def _location_str(metadata: dict) -> str:
    if metadata.get("slide") is not None:
        return f"slide {metadata['slide']}"
    if metadata.get("page") is not None:
        return f"page {metadata['page']}"
    return ""
