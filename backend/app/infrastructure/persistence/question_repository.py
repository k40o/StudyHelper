"""Repository + mappers for generated questions."""
from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...domain.question import Difficulty, Question, QuestionType
from .models import DocumentRecord, QuestionRecord


def prompt_hash(question: Question) -> str:
    return hashlib.sha256(question.normalized_key().encode("utf-8")).hexdigest()


def question_to_record(question: Question, doc_hash: str) -> QuestionRecord:
    return QuestionRecord(
        document_id=question.document_id,
        question_type=question.question_type.value,
        prompt=question.prompt,
        answer=question.answer,
        explanation=question.explanation,
        difficulty=question.difficulty.value,
        topic=question.topic,
        options=question.options or [],
        answer_data=question.answer_data or {},
        source_title=question.source_title,
        source_location=question.source_location,
        prompt_hash=doc_hash,
    )


def record_to_question(record: QuestionRecord) -> Question:
    return Question(
        id=record.id,
        document_id=record.document_id,
        question_type=QuestionType(record.question_type),
        prompt=record.prompt,
        answer=record.answer,
        explanation=record.explanation or "",
        difficulty=Difficulty(record.difficulty),
        topic=record.topic or "",
        options=list(record.options or []),
        answer_data=dict(record.answer_data or {}),
        source_title=record.source_title or "",
        source_location=record.source_location or "",
    )


class QuestionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def existing_hashes(self, document_id: int) -> set[str]:
        stmt = select(QuestionRecord.prompt_hash).where(
            QuestionRecord.document_id == document_id
        )
        return set(self.session.scalars(stmt))

    def add_many(self, questions: list[Question]) -> int:
        """Persist questions, skipping any whose prompt duplicates an existing
        one for the same document. Returns the number actually stored."""
        stored = 0
        # De-dupe within the batch as well as against the database.
        by_doc_seen: dict[int, set[str]] = {}
        for q in questions:
            if q.document_id is None or not q.is_valid:
                continue
            seen = by_doc_seen.get(q.document_id)
            if seen is None:
                seen = self.existing_hashes(q.document_id)
                by_doc_seen[q.document_id] = seen
            h = prompt_hash(q)
            if h in seen:
                continue
            seen.add(h)
            self.session.add(question_to_record(q, h))
            stored += 1
        return stored

    def list_by_document(self, document_id: int) -> list[QuestionRecord]:
        stmt = select(QuestionRecord).where(QuestionRecord.document_id == document_id)
        return list(self.session.scalars(stmt))

    def list_all(self, limit: int | None = None) -> list[QuestionRecord]:
        stmt = select(QuestionRecord)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def by_ids(self, ids: list[int]) -> list[QuestionRecord]:
        if not ids:
            return []
        records = self.session.scalars(
            select(QuestionRecord).where(QuestionRecord.id.in_(ids))
        )
        # Preserve the order of the requested ids.
        by_id = {r.id: r for r in records}
        return [by_id[i] for i in ids if i in by_id]

    def get(self, question_id: int) -> QuestionRecord | None:
        return self.session.get(QuestionRecord, question_id)

    def owner(self, question_id: int) -> int | None:
        """The user_id of the document this question belongs to, or None."""
        stmt = (
            select(DocumentRecord.user_id)
            .join(QuestionRecord, QuestionRecord.document_id == DocumentRecord.id)
            .where(QuestionRecord.id == question_id)
        )
        return self.session.scalar(stmt)

    def random(
        self, limit: int, user_id: int, document_id: int | None = None
    ) -> list[QuestionRecord]:
        """Random questions from ``document_id`` if given (caller must have
        already verified it belongs to ``user_id``), else from anywhere in the
        user's own library."""
        stmt = select(QuestionRecord)
        if document_id is not None:
            stmt = stmt.where(QuestionRecord.document_id == document_id)
        else:
            stmt = stmt.join(DocumentRecord, QuestionRecord.document_id == DocumentRecord.id).where(
                DocumentRecord.user_id == user_id
            )
        stmt = stmt.order_by(func.random()).limit(limit)
        return list(self.session.scalars(stmt))

    def count(self, document_id: int) -> int:
        """Question count for a single, already-ownership-checked document."""
        stmt = select(func.count()).select_from(QuestionRecord).where(
            QuestionRecord.document_id == document_id
        )
        return self.session.scalar(stmt) or 0

    def count_for_user(self, user_id: int) -> int:
        """Total question count across every document the user owns."""
        stmt = (
            select(func.count())
            .select_from(QuestionRecord)
            .join(DocumentRecord, QuestionRecord.document_id == DocumentRecord.id)
            .where(DocumentRecord.user_id == user_id)
        )
        return self.session.scalar(stmt) or 0
