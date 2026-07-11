"""Repositories for the game layer: player profile, spaced-repetition reviews,
achievements, and the answer log."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...domain.game import PlayerProfile, utcnow
from ...domain.spaced_repetition import ReviewState
from .models import (
    AchievementRecord,
    AnswerAttempt,
    BossVictoryRecord,
    DocumentRecord,
    PlayerRecord,
    QuestionRecord,
    ReviewRecord,
)


class PlayerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, user_id: int) -> PlayerRecord:
        stmt = select(PlayerRecord).where(PlayerRecord.user_id == user_id)
        player = self.session.scalar(stmt)
        if player is None:
            player = PlayerRecord(user_id=user_id, hearts=5, hearts_updated_at=utcnow())
            self.session.add(player)
            self.session.flush()
        return player


def record_to_profile(p: PlayerRecord) -> PlayerProfile:
    return PlayerProfile(
        total_xp=p.total_xp,
        coins=p.coins,
        hearts=p.hearts,
        current_streak=p.current_streak,
        longest_streak=p.longest_streak,
        total_answers=p.total_answers,
        correct_answers=p.correct_answers,
    )


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, question_id: int) -> ReviewRecord | None:
        stmt = select(ReviewRecord).where(ReviewRecord.question_id == question_id)
        return self.session.scalar(stmt)

    def upsert(self, question_id: int, state: ReviewState, due_date: dt.date) -> ReviewRecord:
        record = self.get(question_id)
        if record is None:
            record = ReviewRecord(question_id=question_id, due_date=due_date)
            self.session.add(record)
        record.repetitions = state.repetitions
        record.ease = state.ease
        record.interval = state.interval
        record.due_date = due_date
        record.last_reviewed = utcnow()
        return record

    def due_question_ids(self, today: dt.date, user_id: int, limit: int | None = None) -> list[int]:
        stmt = (
            select(ReviewRecord.question_id)
            .join(QuestionRecord, ReviewRecord.question_id == QuestionRecord.id)
            .join(DocumentRecord, QuestionRecord.document_id == DocumentRecord.id)
            .where(ReviewRecord.due_date <= today, DocumentRecord.user_id == user_id)
            .order_by(ReviewRecord.due_date)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count_due(self, today: dt.date, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(ReviewRecord)
            .join(QuestionRecord, ReviewRecord.question_id == QuestionRecord.id)
            .join(DocumentRecord, QuestionRecord.document_id == DocumentRecord.id)
            .where(ReviewRecord.due_date <= today, DocumentRecord.user_id == user_id)
        )
        return self.session.scalar(stmt) or 0


class AchievementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def unlocked_keys(self, user_id: int) -> set[str]:
        stmt = select(AchievementRecord.key).where(AchievementRecord.user_id == user_id)
        return set(self.session.scalars(stmt))

    def unlock(self, user_id: int, key: str) -> None:
        self.session.add(AchievementRecord(user_id=user_id, key=key))


class AttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, question_id: int, correct: bool) -> None:
        self.session.add(AnswerAttempt(question_id=question_id, correct=correct))


class BossRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, document_id: int) -> BossVictoryRecord | None:
        stmt = select(BossVictoryRecord).where(BossVictoryRecord.document_id == document_id)
        return self.session.scalar(stmt)

    def defeated_ids(self) -> set[int]:
        return set(self.session.scalars(select(BossVictoryRecord.document_id)))

    def record_victory(self, document_id: int) -> BossVictoryRecord:
        record = self.get(document_id)
        if record is None:
            record = BossVictoryRecord(document_id=document_id, times_defeated=0)
            self.session.add(record)
        record.times_defeated += 1
        record.last_defeated_at = utcnow()
        return record
