"""Tests for Module 5: game rules, spaced repetition, and the GameService."""
from __future__ import annotations

import datetime as dt

import pytest

from app.application import GameService
from app.domain import achievements
from app.domain.game import (
    MAX_HEARTS,
    level_for_xp,
    regen_hearts,
    update_streak,
    xp_threshold,
)
from app.domain.spaced_repetition import ReviewState, quality_from, sm2
from app.infrastructure.persistence import (
    Database,
    DocumentRecord,
    QuestionRecord,
    ReviewRepository,
)
from conftest import create_test_user


@pytest.fixture
def db(tmp_path) -> Database:
    d = Database(f"sqlite:///{(tmp_path / 'game.db').as_posix()}")
    d.create_all()
    yield d
    d.dispose()


@pytest.fixture
def user_id(db) -> int:
    return create_test_user(db)


def _seed_question(db: Database, user_id: int, difficulty: str = "medium") -> int:
    with db.unit_of_work() as s:
        doc = DocumentRecord(
            user_id=user_id, file_path="/x.txt", source_type="txt", title="X",
            content_hash="h", word_count=1, doc_metadata={},
        )
        s.add(doc)
        s.flush()
        q = QuestionRecord(
            document_id=doc.id, question_type="multiple_choice", prompt="Q?",
            answer="A", explanation="", difficulty=difficulty, topic="",
            options=["A", "B"], answer_data={}, source_title="X",
            source_location="", prompt_hash="ph",
        )
        s.add(q)
        s.flush()
        return q.id


# --------------------------- Pure domain rules --------------------------- #
def test_leveling_curve():
    assert xp_threshold(1) == 0
    assert xp_threshold(2) == 100
    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2
    assert level_for_xp(300) == 3


def test_heart_regen():
    now = dt.datetime(2026, 1, 1, 12, 0, 0)
    assert regen_hearts(3, now, now) == (3, now)  # no time passed
    hearts, _ = regen_hearts(3, now, now + dt.timedelta(minutes=20))
    assert hearts == 4
    full, _ = regen_hearts(2, now, now + dt.timedelta(hours=5))
    assert full == MAX_HEARTS  # capped


def test_streak_logic():
    day = dt.date(2026, 1, 10)
    assert update_streak(0, 0, None, day) == (1, 1)  # first ever
    assert update_streak(3, 5, day - dt.timedelta(days=1), day) == (4, 5)  # consecutive
    assert update_streak(3, 5, day - dt.timedelta(days=3), day) == (1, 5)  # broken
    assert update_streak(3, 5, day, day) == (3, 5)  # same day, no change


def test_sm2_schedule():
    s0 = ReviewState()
    s1 = sm2(s0, quality_from(True))
    assert s1.repetitions == 1 and s1.interval == 1
    s2 = sm2(s1, quality_from(True))
    assert s2.interval == 6
    wrong = sm2(s2, quality_from(False))
    assert wrong.repetitions == 0 and wrong.interval == 1  # reset


def test_achievements_earned():
    keys = achievements.earned_keys(
        {"total_answers": 1, "correct_answers": 0, "current_streak": 0, "level": 1, "coins": 0, "accuracy": 0}
    )
    assert "first_steps" in keys
    assert "scholar" not in keys


# --------------------------- GameService --------------------------- #
def test_correct_answer_rewards(db, user_id):
    qid = _seed_question(db, user_id, "hard")
    result = GameService(db).submit_answer(qid, True, user_id)
    assert result["correct"]
    assert result["xp_earned"] == 25  # hard
    assert result["coins_earned"] == 8
    assert result["hearts"] == MAX_HEARTS
    assert result["current_streak"] == 1
    assert any(a["key"] == "first_steps" for a in result["new_achievements"])
    p = result["profile"]
    assert p["total_answers"] == 1 and p["correct_answers"] == 1 and p["accuracy"] == 100


def test_wrong_answer_loses_heart(db, user_id):
    qid = _seed_question(db, user_id)
    result = GameService(db).submit_answer(qid, False, user_id)
    assert result["xp_earned"] == 0
    assert result["lost_heart"] is True
    assert result["hearts"] == MAX_HEARTS - 1


def test_answer_creates_review(db, user_id):
    qid = _seed_question(db, user_id)
    GameService(db).submit_answer(qid, True, user_id)
    with db.session() as s:
        assert ReviewRepository(s).get(qid) is not None


def test_unknown_question_returns_none(db, user_id):
    assert GameService(db).submit_answer(999, True, user_id) is None


def test_answer_rejects_other_users_question(db, user_id):
    other_user = create_test_user(db, "other@example.com")
    qid = _seed_question(db, other_user)
    assert GameService(db).submit_answer(qid, True, user_id) is None


def test_get_profile_defaults(db, user_id):
    p = GameService(db).get_profile(user_id)
    assert p["level"] == 1
    assert p["hearts"] == MAX_HEARTS
    assert len(p["achievements"]) == len(achievements.ACHIEVEMENTS)
    assert all(not a["unlocked"] for a in p["achievements"])
