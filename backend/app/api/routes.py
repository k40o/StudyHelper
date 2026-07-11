"""REST API routes: auth, documents, upload, tutor, search, game, bosses.

Every route except ``/auth/signup`` and ``/auth/login`` requires a bearer
token (see :func:`get_current_user`) and operates only on that user's own data.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..application import AuthError, GameService, LibraryService
from .schemas import (
    AnswerRequest,
    AnswerResponse,
    AskRequest,
    AskResponse,
    AuthResponse,
    BossCompleteResponse,
    BossOut,
    DocumentOut,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    ImportResult,
    LoginRequest,
    ProfileOut,
    QuestionOut,
    SearchHit,
    SearchRequest,
    SearchResponse,
    SignupRequest,
    SourceOut,
    UserOut,
)

router = APIRouter(prefix="/api")


def get_library(request: Request) -> LibraryService:
    return request.app.state.container.library


def get_game(request: Request) -> GameService:
    return request.app.state.container.game


def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.removeprefix("Bearer ").strip()
    user = request.app.state.container.auth.user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@router.post("/auth/signup", response_model=AuthResponse)
def signup(request: Request, body: SignupRequest) -> AuthResponse:
    try:
        result = request.app.state.container.auth.signup(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AuthResponse(**result)


@router.post("/auth/login", response_model=AuthResponse)
def login(request: Request, body: LoginRequest) -> AuthResponse:
    try:
        result = request.app.state.container.auth.login(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return AuthResponse(**result)


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**user)


# --------------------------------------------------------------------------- #
# Library
# --------------------------------------------------------------------------- #
@router.get("/health", response_model=HealthResponse)
def health(request: Request, user: dict = Depends(get_current_user)) -> HealthResponse:
    library = get_library(request)
    return HealthResponse(
        ai_enabled=library.ai_enabled,
        document_count=len(library.list_documents(user["id"])),
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(request: Request, user: dict = Depends(get_current_user)) -> list[DocumentOut]:
    return [DocumentOut(**d) for d in get_library(request).list_documents(user["id"])]


@router.post("/documents/upload", response_model=ImportResult)
async def upload_document(
    request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)
) -> ImportResult:
    library = get_library(request)
    settings = request.app.state.container.settings

    filename = Path(file.filename or "upload").name  # strip any path components
    if Path(filename).suffix.lower() not in library.supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {sorted(library.supported_extensions)}",
        )

    # Per-user subfolder avoids filename collisions between accounts (file
    # paths are globally unique); actual ownership is passed explicitly below.
    user_dir = settings.study_materials_dir / str(user["id"])
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / filename
    dest.write_bytes(await file.read())

    result = library.ingest_file(dest, user["id"])
    return ImportResult(
        path=result.path,
        status=result.status.value,
        title=result.title,
        blocks=result.blocks,
        error=result.error,
        warning=result.warning,
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    request: Request, document_id: int, user: dict = Depends(get_current_user)
) -> None:
    deleted = get_library(request).delete_document(document_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/documents/{document_id}/generate", response_model=GenerateResponse)
def generate_questions(
    request: Request, document_id: int, body: GenerateRequest, user: dict = Depends(get_current_user)
) -> GenerateResponse:
    result = get_library(request).generate_questions(
        document_id, user["id"], max_questions=body.max_questions
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not result["ai_enabled"]:
        raise HTTPException(status_code=503, detail="AI is not configured")
    return GenerateResponse(**result)


@router.get("/documents/{document_id}/questions", response_model=list[QuestionOut])
def document_questions(
    request: Request, document_id: int, user: dict = Depends(get_current_user)
) -> list[QuestionOut]:
    return [QuestionOut(**q) for q in get_library(request).list_questions(document_id, user["id"])]


@router.get("/quiz", response_model=list[QuestionOut])
def quiz(
    request: Request,
    limit: int = 10,
    document_id: int | None = None,
    user: dict = Depends(get_current_user),
) -> list[QuestionOut]:
    return [
        QuestionOut(**q)
        for q in get_library(request).random_questions(limit, user["id"], document_id)
    ]


@router.get("/profile", response_model=ProfileOut)
def profile(request: Request, user: dict = Depends(get_current_user)) -> ProfileOut:
    return ProfileOut(**get_game(request).get_profile(user["id"]))


@router.post("/answer", response_model=AnswerResponse)
def submit_answer(
    request: Request, body: AnswerRequest, user: dict = Depends(get_current_user)
) -> AnswerResponse:
    result = get_game(request).submit_answer(body.question_id, body.correct, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return AnswerResponse(**result)


@router.get("/reviews/due", response_model=list[QuestionOut])
def due_reviews(
    request: Request, limit: int = 10, user: dict = Depends(get_current_user)
) -> list[QuestionOut]:
    return [QuestionOut(**q) for q in get_game(request).due_questions(user["id"], limit)]


@router.get("/bosses", response_model=list[BossOut])
def bosses(request: Request, user: dict = Depends(get_current_user)) -> list[BossOut]:
    return [BossOut(**b) for b in get_game(request).list_bosses(user["id"])]


@router.get("/bosses/{document_id}", response_model=BossOut)
def boss_detail(
    request: Request, document_id: int, user: dict = Depends(get_current_user)
) -> BossOut:
    b = get_game(request).get_boss(document_id, user["id"])
    if b is None:
        raise HTTPException(status_code=404, detail="Boss not found")
    return BossOut(**b)


@router.post("/bosses/{document_id}/complete", response_model=BossCompleteResponse)
def complete_boss(
    request: Request, document_id: int, user: dict = Depends(get_current_user)
) -> BossCompleteResponse:
    result = get_game(request).complete_boss(document_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Boss not found")
    return BossCompleteResponse(**result)


@router.post("/tutor/ask", response_model=AskResponse)
def ask_tutor(
    request: Request, body: AskRequest, user: dict = Depends(get_current_user)
) -> AskResponse:
    answer = get_library(request).ask(body.question, user["id"])
    return AskResponse(
        text=answer.text,
        grounded=answer.grounded,
        sources=[SourceOut(title=s.title, location=s.location, score=s.score) for s in answer.sources],
    )


@router.post("/search", response_model=SearchResponse)
def search(request: Request, body: SearchRequest, user: dict = Depends(get_current_user)) -> SearchResponse:
    hits = get_library(request).search(body.query, user["id"], k=body.k)
    return SearchResponse(hits=[SearchHit(**h) for h in hits])
