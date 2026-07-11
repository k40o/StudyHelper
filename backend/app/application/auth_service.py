"""Account creation and login.

Kept intentionally small: email + password, one account tier, no email
verification or password reset flow (out of scope for a personal study app).
"""
from __future__ import annotations

import re

from ..core.security import create_token, decode_token, hash_password, verify_password
from ..infrastructure.persistence import Database, UserRepository

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Raised for any signup/login failure the API should surface to the user."""


class AuthService:
    def __init__(self, database: Database, secret_key: str) -> None:
        self._db = database
        self._secret_key = secret_key

    def signup(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if not _EMAIL_RE.match(email):
            raise AuthError("Enter a valid email address.")
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters.")
        with self._db.unit_of_work() as session:
            repo = UserRepository(session)
            if repo.get_by_email(email) is not None:
                raise AuthError("An account with that email already exists.")
            user = repo.create(email, hash_password(password))
            session.flush()
            return self._issue(user.id, user.email)

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        with self._db.session() as session:
            user = UserRepository(session).get_by_email(email)
            if user is None or not verify_password(password, user.password_hash):
                raise AuthError("Incorrect email or password.")
            return self._issue(user.id, user.email)

    def user_from_token(self, token: str) -> dict | None:
        user_id = decode_token(token, self._secret_key)
        if user_id is None:
            return None
        with self._db.session() as session:
            user = UserRepository(session).get_by_id(user_id)
            if user is None:
                return None
            return {"id": user.id, "email": user.email}

    def _issue(self, user_id: int, email: str) -> dict:
        token = create_token(user_id, self._secret_key)
        return {"token": token, "user": {"id": user_id, "email": email}}
