"""Tests for Module 4: question generation, normalization, and dedupe."""
from __future__ import annotations

import json

import pytest

from app.application.question_generator import QuestionGenerator, _parse_questions
from app.domain.document import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    SourceLocation,
    SourceType,
)
from app.domain.question import Difficulty, Question, QuestionType
from app.infrastructure.ai import AIProvider
from app.infrastructure.persistence import Database, DocumentRecord, QuestionRepository
from conftest import create_test_user


class QueuedProvider(AIProvider):
    """Returns pre-canned JSON responses in order (one per generate call)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._i = 0

    @property
    def embedding_dim(self) -> int:
        return 8

    def generate(self, prompt, *, system=None, temperature=0.7, max_output_tokens=None, json_mode=False):
        r = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return r

    def embed(self, text, *, task_type="RETRIEVAL_DOCUMENT"):
        return [0.0] * 8


def _two_slide_doc() -> ParsedDocument:
    return ParsedDocument(
        file_path="/s/bio.pptx",
        source_type=SourceType.PPTX,
        title="Biology",
        blocks=[
            ContentBlock("Mitochondria", BlockType.HEADING, 1, SourceLocation(slide=1)),
            ContentBlock("Mitochondria produce ATP.", location=SourceLocation(slide=1)),
            ContentBlock("Cell Cycle", BlockType.HEADING, 1, SourceLocation(slide=2)),
            ContentBlock("The phases are G1, S, G2, M.", location=SourceLocation(slide=2)),
        ],
    )


SLIDE1_JSON = json.dumps(
    {
        "questions": [
            {
                "type": "multiple_choice",
                "question": "What do mitochondria produce?",
                "options": ["ATP", "DNA", "RNA", "Lipids"],
                "answer": "ATP",
                "explanation": "Mitochondria are the powerhouse.",
                "difficulty": "easy",
                "topic": "Cell biology",
            },
            {
                "type": "true_false",
                "question": "Mitochondria produce ATP.",
                "answer": "true",
                "explanation": "Yes.",
                "difficulty": "easy",
                "topic": "Cell biology",
            },
        ]
    }
)

SLIDE2_JSON = json.dumps(
    {
        "questions": [
            {
                "type": "flashcard",
                "question": "Cell cycle phases",
                "answer": "G1, S, G2, M",
                "difficulty": "medium",
                "topic": "Cell cycle",
            },
            {
                "type": "ordering",
                "question": "Order the cell cycle phases.",
                "correct_order": ["G1", "S", "G2", "M"],
                "difficulty": "medium",
                "topic": "Cell cycle",
            },
            {
                "type": "matching",
                "question": "Match phase to description.",
                "pairs": [
                    {"left": "S", "right": "DNA synthesis"},
                    {"left": "M", "right": "Mitosis"},
                ],
                "difficulty": "hard",
                "topic": "Cell cycle",
            },
        ]
    }
)


def test_generate_for_document_normalizes_all_types():
    provider = QueuedProvider([SLIDE1_JSON, SLIDE2_JSON])
    gen = QuestionGenerator(provider)
    questions = gen.generate_for_document(_two_slide_doc(), document_id=1)

    by_type = {q.question_type: q for q in questions}
    assert len(questions) == 5

    mcq = by_type[QuestionType.MULTIPLE_CHOICE]
    assert mcq.options == ["ATP", "DNA", "RNA", "Lipids"]
    assert mcq.answer_data["correct_index"] == 0
    assert mcq.source_location == "slide 1"
    assert mcq.difficulty == Difficulty.EASY

    assert by_type[QuestionType.TRUE_FALSE].options == ["True", "False"]

    ordering = by_type[QuestionType.ORDERING]
    assert ordering.answer_data["correct_order"] == ["G1", "S", "G2", "M"]
    assert ordering.source_location == "slide 2"

    matching = by_type[QuestionType.MATCHING]
    assert len(matching.answer_data["pairs"]) == 2


def test_generation_dedupes_identical_prompts():
    # Both chunks return the SAME question -> stored once.
    provider = QueuedProvider([SLIDE1_JSON, SLIDE1_JSON])
    gen = QuestionGenerator(provider)
    questions = gen.generate_for_document(_two_slide_doc(), document_id=1)
    prompts = [q.prompt for q in questions]
    assert len(prompts) == len(set(prompts))  # no duplicates


def test_parse_lenient_handles_code_fence():
    raw = "```json\n" + SLIDE1_JSON + "\n```"
    assert len(_parse_questions(raw)) == 2


def test_invalid_items_dropped():
    bad = json.dumps({"questions": [{"type": "multiple_choice", "question": "Q?", "options": ["only one"], "answer": "only one"}]})
    assert _parse_questions(bad) == []  # MCQ with <2 options is invalid


def test_repository_dedupe(tmp_path):
    db = Database(f"sqlite:///{(tmp_path / 'q.db').as_posix()}")
    db.create_all()
    user_id = create_test_user(db)
    # A parent document must exist (foreign keys are enforced).
    with db.unit_of_work() as s:
        doc = DocumentRecord(
            user_id=user_id, file_path="/e.txt", source_type="txt", title="E",
            content_hash="h", word_count=1, doc_metadata={},
        )
        s.add(doc)
        s.flush()
        doc_id = doc.id

    q = Question(
        question_type=QuestionType.SHORT_ANSWER,
        prompt="What is entropy?",
        answer="A measure of disorder.",
        document_id=doc_id,
    )
    with db.unit_of_work() as s:
        assert QuestionRepository(s).add_many([q, q]) == 1  # in-batch dedupe
    with db.unit_of_work() as s:
        assert QuestionRepository(s).add_many([q]) == 0  # already in DB
    with db.session() as s:
        assert QuestionRepository(s).count(doc_id) == 1
    db.dispose()
