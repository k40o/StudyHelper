"""Boss battle rules — pure.

A "boss" is a document you fight by answering its questions. The boss's HP
scales with how many questions it has, so a meatier chapter is a tougher fight.
Per-question damage/combo is computed on the client for responsiveness; the
server owns HP (so the two agree) and the victory bonus.
"""
from __future__ import annotations

BASE_HP = 80
HP_PER_QUESTION = 10
MAX_HP = 220

# Bonus granted on top of the normal per-question rewards when a boss is beaten.
BOSS_BONUS_XP = 150
BOSS_BONUS_COINS = 75


def boss_hp(question_count: int) -> int:
    """Total HP for a boss backed by ``question_count`` questions."""
    if question_count <= 0:
        return BASE_HP
    return max(BASE_HP, min(MAX_HP, BASE_HP + question_count * HP_PER_QUESTION))
