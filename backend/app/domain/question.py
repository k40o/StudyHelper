"""Question domain model.

One flexible :class:`Question` type covers all 10 question formats. Format-specific
data (MCQ options, matching pairs, ordering sequences) lives in ``options`` and
``answer_data`` so the database schema stays simple while supporting every type.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    MATCHING = "matching"
    ORDERING = "ordering"
    SCENARIO = "scenario"
    CASE_STUDY = "case_study"
    FLASHCARD = "flashcard"
    TRICK = "trick"

    @classmethod
    def coerce(cls, value: str) -> "QuestionType | None":
        if not value:
            return None
        key = value.strip().lower().replace("-", "_").replace(" ", "_")
        for member in cls:
            if member.value == key:
                return member
        return None


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    @classmethod
    def coerce(cls, value: str) -> "Difficulty":
        key = (value or "").strip().lower()
        for member in cls:
            if member.value == key:
                return member
        return cls.MEDIUM


@dataclass
class Question:
    question_type: QuestionType
    prompt: str
    answer: str
    explanation: str = ""
    difficulty: Difficulty = Difficulty.MEDIUM
    topic: str = ""
    # MCQ / true-false / ordering: the choices shown to the learner.
    options: list[str] = field(default_factory=list)
    # Structured answer for complex types, e.g.
    #   matching:  {"pairs": [{"left": "...", "right": "..."}]}
    #   ordering:  {"correct_order": ["first", "second", ...]}
    #   mcq:       {"correct_index": 2}
    answer_data: dict = field(default_factory=dict)
    source_title: str = ""
    source_location: str = ""  # e.g. "slide 7" or "page 12"
    document_id: int | None = None
    id: int | None = None

    def normalized_key(self) -> str:
        """A canonical form of the prompt for duplicate detection."""
        text = self.prompt.lower().strip()
        text = re.sub(r"[^a-z0-9 ]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @property
    def is_valid(self) -> bool:
        """Reject half-formed questions before they reach the database."""
        if not self.prompt.strip() or not self.answer.strip():
            return False
        if self.question_type == QuestionType.MULTIPLE_CHOICE and len(self.options) < 2:
            return False
        return True
