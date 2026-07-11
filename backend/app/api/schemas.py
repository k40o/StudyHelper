"""Pydantic request/response models for the REST API."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    ai_enabled: bool
    document_count: int


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class DocumentOut(BaseModel):
    id: int
    title: str
    file_path: str
    source_type: str
    word_count: int
    blocks: int
    questions: int = 0


class ImportResult(BaseModel):
    path: str
    status: str
    title: str | None = None
    blocks: int = 0
    error: str | None = None
    warning: str | None = None


class AskRequest(BaseModel):
    question: str


class SourceOut(BaseModel):
    title: str
    location: str
    score: float


class AskResponse(BaseModel):
    text: str
    grounded: bool
    sources: list[SourceOut] = []


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class SearchHit(BaseModel):
    text: str
    title: str | None = None
    source_type: str | None = None
    page: int | None = None
    slide: int | None = None
    score: float


class SearchResponse(BaseModel):
    hits: list[SearchHit] = []


class QuestionOut(BaseModel):
    id: int
    document_id: int
    question_type: str
    prompt: str
    answer: str
    explanation: str = ""
    difficulty: str = "medium"
    topic: str = ""
    options: list[str] = []
    answer_data: dict = {}
    source_title: str = ""
    source_location: str = ""


class GenerateRequest(BaseModel):
    max_questions: int = 20


class GenerateResponse(BaseModel):
    generated: int
    total: int
    ai_enabled: bool
    quota_exceeded: bool = False


class AchievementOut(BaseModel):
    key: str
    name: str
    description: str
    icon: str
    unlocked: bool = False


class ProfileOut(BaseModel):
    level: int
    total_xp: int
    xp_in_level: int
    xp_for_next: int
    coins: int
    hearts: int
    max_hearts: int
    current_streak: int
    longest_streak: int
    total_answers: int
    correct_answers: int
    accuracy: int
    due_reviews: int
    achievements: list[AchievementOut] = []


class AnswerRequest(BaseModel):
    question_id: int
    correct: bool


class NewAchievement(BaseModel):
    key: str
    name: str
    description: str
    icon: str


class AnswerResponse(BaseModel):
    correct: bool
    xp_earned: int
    coins_earned: int
    hearts: int
    lost_heart: bool
    level: int
    leveled_up: bool
    current_streak: int
    new_achievements: list[NewAchievement] = []
    profile: ProfileOut


class BossOut(BaseModel):
    document_id: int
    title: str
    question_count: int
    max_hp: int
    defeated: bool
    times_defeated: int


class BossCompleteResponse(BaseModel):
    document_id: int
    xp_earned: int
    coins_earned: int
    times_defeated: int
    leveled_up: bool
    level: int
    profile: ProfileOut
