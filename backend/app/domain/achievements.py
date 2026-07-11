"""Achievement definitions and evaluation — pure.

Each achievement is unlocked when its condition holds against a stats snapshot.
The GameService diffs the result against already-unlocked keys to detect *new*
unlocks after each answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    description: str
    icon: str
    condition: Callable[[dict], bool]


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_steps", "First Steps", "Answer your first question", "🎓",
                lambda s: s["total_answers"] >= 1),
    Achievement("quick_learner", "Quick Learner", "Answer 10 questions correctly", "⚡",
                lambda s: s["correct_answers"] >= 10),
    Achievement("scholar", "Scholar", "Answer 50 questions correctly", "📚",
                lambda s: s["correct_answers"] >= 50),
    Achievement("on_fire", "On Fire", "Reach a 3-day streak", "🔥",
                lambda s: s["current_streak"] >= 3),
    Achievement("unstoppable", "Unstoppable", "Reach a 7-day streak", "🚀",
                lambda s: s["current_streak"] >= 7),
    Achievement("rising_star", "Rising Star", "Reach level 5", "⭐",
                lambda s: s["level"] >= 5),
    Achievement("master_mind", "Mastermind", "Reach level 10", "🧠",
                lambda s: s["level"] >= 10),
    Achievement("treasure_hunter", "Treasure Hunter", "Collect 100 coins", "💰",
                lambda s: s["coins"] >= 100),
    Achievement("sharpshooter", "Sharpshooter", "90%+ accuracy over 20+ answers", "🎯",
                lambda s: s["total_answers"] >= 20 and s["accuracy"] >= 90),
]

_BY_KEY = {a.key: a for a in ACHIEVEMENTS}


def get(key: str) -> Achievement | None:
    return _BY_KEY.get(key)


def earned_keys(stats: dict) -> set[str]:
    """Return the set of achievement keys currently satisfied by ``stats``."""
    return {a.key for a in ACHIEVEMENTS if a.condition(stats)}
