"""SQLAlchemy ORM models — the physical database schema.

Module 2 introduces ``documents`` and ``blocks``. Later modules add their own
tables (questions, progress, achievements, sessions...) against the same
``Base``, so the schema grows without touching these definitions.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the app."""


class UserRecord(Base):
    """An account. Every document/player/achievement row belongs to one."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class DocumentRecord(Base):
    """One imported study file."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(512))
    # SHA-256 of the file bytes — used to skip re-importing unchanged files.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    blocks: Mapped[list["BlockRecord"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="BlockRecord.position",
    )
    questions: Mapped[list["QuestionRecord"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class BlockRecord(Base):
    """One atomic piece of content within a document, with its source location."""

    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)  # order within the document
    text: Mapped[str] = mapped_column(Text)
    block_type: Mapped[str] = mapped_column(String(16))
    level: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[DocumentRecord] = relationship(back_populates="blocks")


class QuestionRecord(Base):
    """One generated question of any of the 10 supported types."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    question_type: Mapped[str] = mapped_column(String(24))
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    topic: Mapped[str] = mapped_column(String(256), default="")
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer_data: Mapped[dict] = mapped_column(JSON, default=dict)
    source_title: Mapped[str] = mapped_column(String(512), default="")
    source_location: Mapped[str] = mapped_column(String(64), default="")
    # Hash of the normalized prompt, for de-duplication within a document.
    prompt_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[DocumentRecord] = relationship(back_populates="questions")


class PlayerRecord(Base):
    """The player's game profile. One row per user."""

    __tablename__ = "player"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    hearts: Mapped[int] = mapped_column(Integer, default=5)
    hearts_updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    total_answers: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewRecord(Base):
    """Spaced-repetition state for a single question (one row per question)."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True, index=True
    )
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[dt.date] = mapped_column(Date, index=True)
    last_reviewed: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class AchievementRecord(Base):
    """An unlocked achievement (keyed by its definition key), one row per user+key."""

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_achievement_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(48), index=True)
    unlocked_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class AnswerAttempt(Base):
    """A log of every answer, for history/stats."""

    __tablename__ = "answer_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class BossVictoryRecord(Base):
    """Record that a document's "boss" has been defeated (one row per document)."""

    __tablename__ = "boss_victories"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    times_defeated: Mapped[int] = mapped_column(Integer, default=0)
    first_defeated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    last_defeated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
