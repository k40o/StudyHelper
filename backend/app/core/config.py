"""Application configuration.

Centralizes paths and settings so nothing else hardcodes locations. Values can
be overridden via environment variables (useful for tests and deployment).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Project root = three levels up from this file (backend/app/core/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Load backend/.env into the environment if present (no-op if the file or the
# python-dotenv package is missing).
try:  # pragma: no cover - trivial glue
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    study_materials_dir: Path = PROJECT_ROOT / "StudyMaterials"
    data_dir: Path = PROJECT_ROOT / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studygame.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / ".secret_key"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.study_materials_dir.mkdir(parents=True, exist_ok=True)

    def load_or_create_secret_key(self) -> str:
        """Auth token signing key. Uses ``STUDYGAME_SECRET_KEY`` if set (handy for
        multi-instance deployments); otherwise persists a random one alongside the
        database so tokens keep working across restarts."""
        env_key = os.environ.get("STUDYGAME_SECRET_KEY", "").strip()
        if env_key:
            return env_key
        if self.secret_key_path.exists():
            return self.secret_key_path.read_text(encoding="utf-8").strip()
        import secrets as _secrets

        key = _secrets.token_hex(32)
        self.secret_key_path.write_text(key, encoding="utf-8")
        return key


@dataclass(frozen=True)
class AISettings:
    """Configuration for the AI provider (Gemini by default)."""

    api_key: str = ""
    text_model: str = "gemini-2.5-flash"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def load_ai_settings() -> AISettings:
    return AISettings(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        text_model=os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
        embed_model=os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
        embed_dim=int(os.environ.get("GEMINI_EMBED_DIM", "768")),
    )


def load_settings() -> Settings:
    """Build settings, allowing env-var overrides for the key directories."""
    root = Path(os.environ.get("STUDYGAME_ROOT", PROJECT_ROOT))
    return Settings(
        project_root=root,
        study_materials_dir=Path(
            os.environ.get("STUDYGAME_MATERIALS_DIR", root / "StudyMaterials")
        ),
        data_dir=Path(os.environ.get("STUDYGAME_DATA_DIR", root / "data")),
    )
