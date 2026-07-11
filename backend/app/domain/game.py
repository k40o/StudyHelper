"""Core game/RPG rules — pure functions, no I/O.

Everything here is deterministic and unit-testable: leveling curve, XP/coin
rewards, heart regeneration, and daily streak logic. The GameService applies
these to persisted state.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# --- Tunables --------------------------------------------------------------- #
BASE_XP = 100           # scales the leveling curve
MAX_HEARTS = 5
HEART_REGEN_MINUTES = 20

XP_BY_DIFFICULTY = {"easy": 10, "medium": 15, "hard": 25}
COINS_BY_DIFFICULTY = {"easy": 3, "medium": 5, "hard": 8}


def utcnow() -> dt.datetime:
    """Naive UTC timestamp (matches the naive datetimes SQLite stores)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


# --- Leveling --------------------------------------------------------------- #
def xp_threshold(level: int) -> int:
    """Total XP required to *be at* a given level (level 1 = 0 XP)."""
    if level <= 1:
        return 0
    return BASE_XP * (level - 1) * level // 2


def level_for_xp(total_xp: int) -> int:
    level = 1
    while xp_threshold(level + 1) <= total_xp:
        level += 1
    return level


# --- Rewards ---------------------------------------------------------------- #
def xp_reward(difficulty: str, correct: bool) -> int:
    return XP_BY_DIFFICULTY.get(difficulty, 15) if correct else 0


def coin_reward(difficulty: str, correct: bool) -> int:
    return COINS_BY_DIFFICULTY.get(difficulty, 5) if correct else 0


# --- Hearts ----------------------------------------------------------------- #
def regen_hearts(
    hearts: int, updated_at: dt.datetime, now: dt.datetime
) -> tuple[int, dt.datetime]:
    """Return (hearts, updated_at) after applying time-based regeneration."""
    if hearts >= MAX_HEARTS:
        return MAX_HEARTS, now
    elapsed_min = (now - updated_at).total_seconds() / 60
    gained = int(elapsed_min // HEART_REGEN_MINUTES)
    if gained <= 0:
        return hearts, updated_at
    new_hearts = min(MAX_HEARTS, hearts + gained)
    if new_hearts >= MAX_HEARTS:
        return MAX_HEARTS, now
    # Advance the clock only by the intervals we actually consumed.
    advanced = updated_at + dt.timedelta(minutes=gained * HEART_REGEN_MINUTES)
    return new_hearts, advanced


# --- Streaks ---------------------------------------------------------------- #
def update_streak(
    current: int, longest: int, last_active: dt.date | None, today: dt.date
) -> tuple[int, int]:
    """Return (current_streak, longest_streak) after activity on ``today``."""
    if last_active == today:
        return current, longest  # already counted today
    if last_active is not None and (today - last_active).days == 1:
        current += 1
    else:
        current = 1  # first ever, or the chain broke
    return current, max(longest, current)


# --- Aggregate profile view ------------------------------------------------- #
@dataclass
class PlayerProfile:
    total_xp: int = 0
    coins: int = 0
    hearts: int = MAX_HEARTS
    current_streak: int = 0
    longest_streak: int = 0
    total_answers: int = 0
    correct_answers: int = 0

    @property
    def level(self) -> int:
        return level_for_xp(self.total_xp)

    @property
    def xp_in_level(self) -> int:
        return self.total_xp - xp_threshold(self.level)

    @property
    def xp_for_next(self) -> int:
        return xp_threshold(self.level + 1) - xp_threshold(self.level)

    @property
    def accuracy(self) -> int:
        return round(self.correct_answers / self.total_answers * 100) if self.total_answers else 0
