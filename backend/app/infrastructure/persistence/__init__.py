"""Persistence package: SQLite via SQLAlchemy."""
from .database import Database
from .game_repository import (
    AchievementRepository,
    AttemptRepository,
    BossRepository,
    PlayerRepository,
    ReviewRepository,
    record_to_profile,
)
from .models import (
    AchievementRecord,
    AnswerAttempt,
    Base,
    BlockRecord,
    BossVictoryRecord,
    DocumentRecord,
    PlayerRecord,
    QuestionRecord,
    ReviewRecord,
    UserRecord,
)
from .question_repository import (
    QuestionRepository,
    prompt_hash,
    question_to_record,
    record_to_question,
)
from .repositories import DocumentRepository, UserRepository, record_to_domain

__all__ = [
    "Database",
    "Base",
    "DocumentRecord",
    "BlockRecord",
    "QuestionRecord",
    "PlayerRecord",
    "ReviewRecord",
    "AchievementRecord",
    "AnswerAttempt",
    "UserRecord",
    "UserRepository",
    "DocumentRepository",
    "record_to_domain",
    "QuestionRepository",
    "record_to_question",
    "question_to_record",
    "prompt_hash",
    "PlayerRepository",
    "ReviewRepository",
    "AchievementRepository",
    "AttemptRepository",
    "BossRepository",
    "BossVictoryRecord",
    "record_to_profile",
]
