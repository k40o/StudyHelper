"""Google Gemini provider (REST).

Uses the Generative Language REST API directly so we control embedding
dimensionality, task types, and retry behaviour. Free-tier friendly: retries on
rate-limit (429) and transient (503) errors with exponential backoff.
"""
from __future__ import annotations

import logging
import math
import time

import requests

from ...core.config import AISettings, load_ai_settings
from .base import AIError, AIProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE = {429, 500, 503}


class GeminiProvider(AIProvider):
    def __init__(
        self,
        settings: AISettings | None = None,
        *,
        timeout: float = 60.0,
        max_retries: int = 4,
    ) -> None:
        self._settings = settings or load_ai_settings()
        if not self._settings.is_configured:
            raise AIError("GEMINI_API_KEY is not set (check backend/.env)")
        self._timeout = timeout
        self._max_retries = max_retries
        self._session = requests.Session()

    @property
    def embedding_dim(self) -> int:
        return self._settings.embed_dim

    # ------------------------------------------------------------------ #
    # Text generation
    # ------------------------------------------------------------------ #
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        generation_config: dict = {"temperature": temperature}
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        data = self._post(f"models/{self._settings.text_model}:generateContent", body)
        return self._extract_text(data)

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            feedback = data.get("promptFeedback", {})
            raise AIError(f"No candidates returned (promptFeedback={feedback})")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            reason = candidates[0].get("finishReason", "UNKNOWN")
            raise AIError(f"Empty response (finishReason={reason})")
        return text

    # ------------------------------------------------------------------ #
    # Embeddings
    # ------------------------------------------------------------------ #
    def embed(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        body = {
            "model": f"models/{self._settings.embed_model}",
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
            "outputDimensionality": self._settings.embed_dim,
        }
        data = self._post(f"models/{self._settings.embed_model}:embedContent", body)
        values = data.get("embedding", {}).get("values")
        if not values:
            raise AIError(f"No embedding returned: {data}")
        return _l2_normalize(values)

    # ------------------------------------------------------------------ #
    # HTTP with retry/backoff
    # ------------------------------------------------------------------ #
    def _post(self, path: str, body: dict) -> dict:
        url = f"{_BASE_URL}/{path}"
        params = {"key": self._settings.api_key}
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                resp = self._session.post(url, params=params, json=body, timeout=self._timeout)
            except requests.RequestException as exc:  # network error
                last_error = exc
                self._sleep(attempt)
                continue

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in _RETRYABLE and attempt < self._max_retries - 1:
                logger.warning("Gemini %s -> %s, retrying", path, resp.status_code)
                self._sleep(attempt)
                continue
            raise AIError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

        raise AIError(f"Gemini API unreachable after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _sleep(attempt: int) -> None:
        time.sleep(min(2 ** attempt, 8))  # 1, 2, 4, 8s


def _l2_normalize(vec: list[float]) -> list[float]:
    """Unit-normalize so cosine similarity behaves consistently.

    Gemini's embedding endpoint does not normalize when a reduced
    outputDimensionality is requested, so we do it here.
    """
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]
