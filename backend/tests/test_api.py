"""Tests for the REST API (offline: AI provider forced off for determinism)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import AISettings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYGAME_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDYGAME_MATERIALS_DIR", str(tmp_path / "mat"))
    monkeypatch.setenv("STUDYGAME_DATA_DIR", str(tmp_path / "data"))
    # Force AI off regardless of a real key in .env, so this suite is offline.
    monkeypatch.setattr("app.api.container.load_ai_settings", lambda: AISettings(api_key=""))
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Sign up a fresh account and return its Authorization header."""
    r = client.post("/api/auth/signup", json={"email": "student@example.com", "password": "hunter2pass"})
    assert r.status_code == 200
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_signup_and_me(client):
    r = client.post("/api/auth/signup", json={"email": "new@example.com", "password": "longenough1"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "new@example.com"

    headers = {"Authorization": f"Bearer {body['token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


def test_signup_rejects_duplicate_email(client):
    client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "longenough1"})
    r = client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "longenough1"})
    assert r.status_code == 400


def test_signup_rejects_short_password(client):
    r = client.post("/api/auth/signup", json={"email": "short@example.com", "password": "abc"})
    assert r.status_code == 400


def test_login_success_and_failure(client):
    client.post("/api/auth/signup", json={"email": "login@example.com", "password": "longenough1"})
    ok = client.post("/api/auth/login", json={"email": "login@example.com", "password": "longenough1"})
    assert ok.status_code == 200

    bad = client.post("/api/auth/login", json={"email": "login@example.com", "password": "wrongpass1"})
    assert bad.status_code == 401


def test_protected_routes_require_auth(client):
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/profile").status_code == 401


# --------------------------------------------------------------------------- #
# Documents / library (authenticated)
# --------------------------------------------------------------------------- #
def test_health(client, auth_headers):
    body = client.get("/api/health", headers=auth_headers).json()
    assert body["status"] == "ok"
    assert body["ai_enabled"] is False
    assert body["document_count"] == 0


def test_upload_and_list(client, auth_headers):
    files = {"file": ("cells.txt", b"# Cells\nMitochondria make energy.", "text/plain")}
    result = client.post("/api/documents/upload", files=files, headers=auth_headers).json()
    assert result["status"] == "imported"
    assert result["title"] == "Cells"

    docs = client.get("/api/documents", headers=auth_headers).json()
    assert len(docs) == 1
    assert docs[0]["title"] == "Cells"

    # Re-uploading identical content is de-duplicated.
    again = client.post("/api/documents/upload", files=files, headers=auth_headers).json()
    assert again["status"] == "unchanged"
    assert len(client.get("/api/documents", headers=auth_headers).json()) == 1


def test_documents_are_private_per_account(client):
    a = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "longenough1"})
    b = client.post("/api/auth/signup", json={"email": "b@example.com", "password": "longenough1"})
    a_headers = {"Authorization": f"Bearer {a.json()['token']}"}
    b_headers = {"Authorization": f"Bearer {b.json()['token']}"}

    files = {"file": ("mine.txt", b"# Mine\nPrivate notes.", "text/plain")}
    client.post("/api/documents/upload", files=files, headers=a_headers)

    assert len(client.get("/api/documents", headers=a_headers).json()) == 1
    assert len(client.get("/api/documents", headers=b_headers).json()) == 0


def test_unsupported_type_rejected(client, auth_headers):
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_delete_document(client, auth_headers, tmp_path):
    files = {"file": ("gone.txt", b"# Gone\nThis will be deleted.", "text/plain")}
    client.post("/api/documents/upload", files=files, headers=auth_headers)
    docs = client.get("/api/documents", headers=auth_headers).json()
    assert len(docs) == 1
    doc_id = docs[0]["id"]

    resp = client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/documents", headers=auth_headers).json() == []

    # The original file was moved to the trash folder, not left in materials.
    trash = tmp_path / "data" / ".trash"
    assert (trash / "gone.txt").exists()

    # Deleting a non-existent id → 404.
    assert client.delete(f"/api/documents/{doc_id}", headers=auth_headers).status_code == 404


def test_tutor_and_search_when_ai_off(client, auth_headers):
    ask = client.post("/api/tutor/ask", json={"question": "anything"}, headers=auth_headers).json()
    assert ask["grounded"] is False

    search = client.post("/api/search", json={"query": "anything"}, headers=auth_headers).json()
    assert search["hits"] == []


def test_profile_defaults(client, auth_headers):
    p = client.get("/api/profile", headers=auth_headers).json()
    assert p["level"] == 1
    assert p["hearts"] == p["max_hearts"] == 5
    assert p["total_answers"] == 0
    assert len(p["achievements"]) >= 8


def test_answer_unknown_question_404(client, auth_headers):
    resp = client.post("/api/answer", json={"question_id": 999, "correct": True}, headers=auth_headers)
    assert resp.status_code == 404
