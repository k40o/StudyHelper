"""Tests for Module 6: boss battles."""
from __future__ import annotations

import pytest

from app.application import GameService
from app.domain.boss import BASE_HP, BOSS_BONUS_COINS, BOSS_BONUS_XP, MAX_HP, boss_hp
from app.infrastructure.persistence import Database, DocumentRecord, QuestionRecord
from conftest import create_test_user


@pytest.fixture
def db(tmp_path) -> Database:
    d = Database(f"sqlite:///{(tmp_path / 'boss.db').as_posix()}")
    d.create_all()
    yield d
    d.dispose()


@pytest.fixture
def user_id(db) -> int:
    return create_test_user(db)


def _seed_doc_with_questions(db: Database, user_id: int, n: int) -> int:
    with db.unit_of_work() as s:
        doc = DocumentRecord(
            user_id=user_id, file_path=f"/doc_{n}.txt", source_type="txt", title="Chapter 8",
            content_hash="h", word_count=1, doc_metadata={},
        )
        s.add(doc)
        s.flush()
        for i in range(n):
            s.add(QuestionRecord(
                document_id=doc.id, question_type="multiple_choice", prompt=f"Q{i}?",
                answer="A", explanation="", difficulty="medium", topic="",
                options=["A", "B"], answer_data={}, source_title="Chapter 8",
                source_location="", prompt_hash=f"h{i}",
            ))
        return doc.id


def test_boss_hp_scales_and_caps():
    assert boss_hp(0) == BASE_HP
    assert boss_hp(5) == BASE_HP + 50
    assert boss_hp(1000) == MAX_HP  # capped


def test_get_boss(db, user_id):
    doc_id = _seed_doc_with_questions(db, user_id, 6)
    boss = GameService(db).get_boss(doc_id, user_id)
    assert boss["title"] == "Chapter 8"
    assert boss["question_count"] == 6
    assert boss["max_hp"] == boss_hp(6)
    assert boss["defeated"] is False
    assert boss["times_defeated"] == 0


def test_complete_boss_awards_bonus_and_records(db, user_id):
    doc_id = _seed_doc_with_questions(db, user_id, 6)
    svc = GameService(db)

    result = svc.complete_boss(doc_id, user_id)
    assert result["xp_earned"] == BOSS_BONUS_XP
    assert result["coins_earned"] == BOSS_BONUS_COINS
    assert result["times_defeated"] == 1
    assert result["profile"]["coins"] == BOSS_BONUS_COINS
    assert result["profile"]["total_xp"] == BOSS_BONUS_XP

    # Now marked defeated, and a second win increments the counter.
    boss = svc.get_boss(doc_id, user_id)
    assert boss["defeated"] is True
    again = svc.complete_boss(doc_id, user_id)
    assert again["times_defeated"] == 2


def test_list_bosses(db, user_id):
    _seed_doc_with_questions(db, user_id, 3)
    _seed_doc_with_questions(db, user_id, 8)
    bosses = GameService(db).list_bosses(user_id)
    assert len(bosses) == 2
    assert {b["question_count"] for b in bosses} == {3, 8}


def test_complete_unknown_boss_returns_none(db, user_id):
    assert GameService(db).complete_boss(999, user_id) is None
