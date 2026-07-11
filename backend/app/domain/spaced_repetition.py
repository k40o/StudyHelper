"""Spaced repetition scheduling (SM-2 algorithm), pure functions.

Each question a learner answers carries a review state. Correct answers push
the next review further out; wrong answers reset it so the question resurfaces
soon. This is what makes the app teach what you keep getting wrong.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


@dataclass
class ReviewState:
    repetitions: int = 0
    ease: float = DEFAULT_EASE
    interval: int = 0  # days until next review


def quality_from(correct: bool) -> int:
    """Map a quiz outcome to an SM-2 quality score (0-5)."""
    return 4 if correct else 1


def sm2(state: ReviewState, quality: int) -> ReviewState:
    """Return the next review state given an answer quality (SM-2)."""
    q = max(0, min(5, quality))

    if q < 3:  # incorrect — relearn from the start
        repetitions = 0
        interval = 1
    else:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = round(state.interval * state.ease)
        repetitions = state.repetitions + 1

    ease = state.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ease = max(MIN_EASE, ease)
    return ReviewState(repetitions=repetitions, ease=ease, interval=max(1, interval))


def next_due(state: ReviewState, today: dt.date) -> dt.date:
    return today + dt.timedelta(days=state.interval)
