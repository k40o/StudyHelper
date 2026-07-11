"""Tests for GeminiProvider's retry/backoff behavior — specifically that a hard
quota cap fails fast instead of retrying every remaining call in a batch."""
from __future__ import annotations

import json

import pytest

from app.core.config import AISettings
from app.infrastructure.ai import AIError, QuotaExceededError
from app.infrastructure.ai.gemini_provider import GeminiProvider


class _FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)

    def json(self) -> dict:
        return self._body


@pytest.fixture
def provider(monkeypatch) -> GeminiProvider:
    p = GeminiProvider(AISettings(api_key="test-key"))
    monkeypatch.setattr(p, "_sleep", lambda attempt: None)  # skip real backoff delays
    return p


def test_quota_exceeded_fails_fast_without_retrying(provider, monkeypatch):
    calls = []

    def fake_post(url, params=None, json=None, timeout=None):
        calls.append(1)
        return _FakeResponse(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})

    monkeypatch.setattr(provider._session, "post", fake_post)

    with pytest.raises(QuotaExceededError):
        provider.generate("hello")

    assert len(calls) == 1  # no retries wasted on a call guaranteed to fail again


def test_transient_429_is_retried(provider, monkeypatch):
    responses = [
        _FakeResponse(429, {"error": {"code": 429, "status": "RATE_LIMIT_EXCEEDED", "message": "slow down"}}),
        _FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
    ]

    def fake_post(url, params=None, json=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(provider._session, "post", fake_post)
    assert provider.generate("hello") == "ok"


def test_non_quota_429_after_retries_raises_plain_ai_error(provider, monkeypatch):
    def fake_post(url, params=None, json=None, timeout=None):
        return _FakeResponse(429, {"error": {"code": 429, "status": "RATE_LIMIT_EXCEEDED", "message": "slow down"}})

    monkeypatch.setattr(provider._session, "post", fake_post)

    with pytest.raises(AIError) as exc_info:
        provider.generate("hello")
    assert not isinstance(exc_info.value, QuotaExceededError)
