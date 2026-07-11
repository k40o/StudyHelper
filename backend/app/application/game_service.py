"""Game service: applies pure game rules to persisted state.

The single entry point ``submit_answer`` is the beating heart of the RPG loop:
one answer updates XP, coins, hearts, streak, the spaced-repetition schedule,
and checks for newly unlocked achievements — all in one transaction.
"""
from __future__ import annotations

import datetime as dt

from ..domain import achievements, boss, game
from ..domain.game import (
    coin_reward,
    level_for_xp,
    regen_hearts,
    update_streak,
    utcnow,
    xp_reward,
)
from ..domain.spaced_repetition import ReviewState, next_due, quality_from, sm2
from ..infrastructure.persistence import (
    AchievementRepository,
    AttemptRepository,
    BossRepository,
    Database,
    DocumentRepository,
    PlayerRepository,
    QuestionRepository,
    ReviewRepository,
    record_to_profile,
)


def _question_dict(r) -> dict:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "question_type": r.question_type,
        "prompt": r.prompt,
        "answer": r.answer,
        "explanation": r.explanation or "",
        "difficulty": r.difficulty,
        "topic": r.topic or "",
        "options": list(r.options or []),
        "answer_data": dict(r.answer_data or {}),
        "source_title": r.source_title or "",
        "source_location": r.source_location or "",
    }


class GameService:
    def __init__(self, database: Database) -> None:
        self._db = database

    # ------------------------------------------------------------------ #
    def get_profile(self, user_id: int) -> dict:
        with self._db.unit_of_work() as session:
            player = PlayerRepository(session).get_or_create(user_id)
            hearts, updated = regen_hearts(
                player.hearts, player.hearts_updated_at, utcnow()
            )
            player.hearts, player.hearts_updated_at = hearts, updated
            profile = record_to_profile(player)
            due = ReviewRepository(session).count_due(dt.date.today(), user_id)
            unlocked = AchievementRepository(session).unlocked_keys(user_id)
            return _profile_payload(profile, due, unlocked)

    def submit_answer(self, question_id: int, correct: bool, user_id: int) -> dict | None:
        today = dt.date.today()
        now = utcnow()
        with self._db.unit_of_work() as session:
            question_repo = QuestionRepository(session)
            question = question_repo.get(question_id)
            if question is None or question_repo.owner(question_id) != user_id:
                return None
            difficulty = question.difficulty

            player = PlayerRepository(session).get_or_create(user_id)
            player.hearts, player.hearts_updated_at = regen_hearts(
                player.hearts, player.hearts_updated_at, now
            )

            prev_level = level_for_xp(player.total_xp)
            xp = xp_reward(difficulty, correct)
            coins = coin_reward(difficulty, correct)
            player.total_xp += xp
            player.coins += coins
            player.total_answers += 1
            if correct:
                player.correct_answers += 1

            lost_heart = False
            if not correct and player.hearts > 0:
                player.hearts -= 1
                player.hearts_updated_at = now  # reset the regen clock on a loss
                lost_heart = True

            player.current_streak, player.longest_streak = update_streak(
                player.current_streak, player.longest_streak, player.last_active_date, today
            )
            player.last_active_date = today

            new_level = level_for_xp(player.total_xp)

            # Spaced repetition update for this question
            reviews = ReviewRepository(session)
            existing = reviews.get(question_id)
            state = (
                ReviewState(existing.repetitions, existing.ease, existing.interval)
                if existing
                else ReviewState()
            )
            new_state = sm2(state, quality_from(correct))
            reviews.upsert(question_id, new_state, next_due(new_state, today))

            AttemptRepository(session).add(question_id, correct)

            # Achievements
            profile = record_to_profile(player)
            stats = {
                "total_answers": profile.total_answers,
                "correct_answers": profile.correct_answers,
                "current_streak": profile.current_streak,
                "level": profile.level,
                "coins": profile.coins,
                "accuracy": profile.accuracy,
            }
            ach_repo = AchievementRepository(session)
            already = ach_repo.unlocked_keys(user_id)
            earned = achievements.earned_keys(stats)
            new_achievements = []
            for key in earned - already:
                ach_repo.unlock(user_id, key)
                a = achievements.get(key)
                if a:
                    new_achievements.append(
                        {"key": a.key, "name": a.name, "description": a.description, "icon": a.icon}
                    )

            due = reviews.count_due(today, user_id)
            return {
                "correct": correct,
                "xp_earned": xp,
                "coins_earned": coins,
                "hearts": player.hearts,
                "lost_heart": lost_heart,
                "level": new_level,
                "leveled_up": new_level > prev_level,
                "current_streak": player.current_streak,
                "new_achievements": new_achievements,
                "profile": _profile_payload(profile, due, earned),
            }

    def due_questions(self, user_id: int, limit: int = 10) -> list[dict]:
        with self._db.session() as session:
            ids = ReviewRepository(session).due_question_ids(dt.date.today(), user_id, limit)
            records = QuestionRepository(session).by_ids(ids)
            return [_question_dict(r) for r in records]

    # ------------------------------------------------------------------ #
    # Boss battles
    # ------------------------------------------------------------------ #
    def list_bosses(self, user_id: int) -> list[dict]:
        with self._db.session() as session:
            docs = DocumentRepository(session).list_all(user_id)
            q_repo = QuestionRepository(session)
            b_repo = BossRepository(session)
            return [
                _boss_dict(d, q_repo.count(d.id), b_repo.get(d.id)) for d in docs
            ]

    def get_boss(self, document_id: int, user_id: int) -> dict | None:
        with self._db.session() as session:
            doc = DocumentRepository(session).get_by_id(document_id, user_id)
            if doc is None:
                return None
            qcount = QuestionRepository(session).count(document_id)
            victory = BossRepository(session).get(document_id)
            return _boss_dict(doc, qcount, victory)

    def complete_boss(self, document_id: int, user_id: int) -> dict | None:
        """Award the victory bonus and record the defeat."""
        with self._db.unit_of_work() as session:
            doc = DocumentRepository(session).get_by_id(document_id, user_id)
            if doc is None:
                return None
            player = PlayerRepository(session).get_or_create(user_id)
            prev_level = level_for_xp(player.total_xp)
            player.total_xp += boss.BOSS_BONUS_XP
            player.coins += boss.BOSS_BONUS_COINS
            victory = BossRepository(session).record_victory(document_id)
            new_level = level_for_xp(player.total_xp)

            profile = record_to_profile(player)
            due = ReviewRepository(session).count_due(dt.date.today(), user_id)
            unlocked = AchievementRepository(session).unlocked_keys(user_id)
            return {
                "document_id": document_id,
                "xp_earned": boss.BOSS_BONUS_XP,
                "coins_earned": boss.BOSS_BONUS_COINS,
                "times_defeated": victory.times_defeated,
                "leveled_up": new_level > prev_level,
                "level": new_level,
                "profile": _profile_payload(profile, due, unlocked),
            }


def _boss_dict(doc, question_count: int, victory) -> dict:
    return {
        "document_id": doc.id,
        "title": doc.title,
        "question_count": question_count,
        "max_hp": boss.boss_hp(question_count),
        "defeated": victory is not None,
        "times_defeated": victory.times_defeated if victory else 0,
    }


def _profile_payload(profile, due_count: int, unlocked_keys: set[str]) -> dict:
    return {
        "level": profile.level,
        "total_xp": profile.total_xp,
        "xp_in_level": profile.xp_in_level,
        "xp_for_next": profile.xp_for_next,
        "coins": profile.coins,
        "hearts": profile.hearts,
        "max_hearts": game.MAX_HEARTS,
        "current_streak": profile.current_streak,
        "longest_streak": profile.longest_streak,
        "total_answers": profile.total_answers,
        "correct_answers": profile.correct_answers,
        "accuracy": profile.accuracy,
        "due_reviews": due_count,
        "achievements": [
            {
                "key": a.key,
                "name": a.name,
                "description": a.description,
                "icon": a.icon,
                "unlocked": a.key in unlocked_keys,
            }
            for a in achievements.ACHIEVEMENTS
        ],
    }
