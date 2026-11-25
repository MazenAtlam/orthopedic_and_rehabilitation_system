"""Shared Flask extensions and process-local security helpers."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from flask import Flask, Response
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import bcrypt as _bcrypt

from app.errors import error_response
from app.models import Base


class BcryptHasher:
    """bcrypt password hashing with a configurable work factor."""

    def __init__(self) -> None:
        self._rounds = 12

    def init_app(self, app: Flask) -> None:
        """Read the work factor from the application configuration."""
        self._rounds = int(app.config.get("BCRYPT_ROUNDS", 12))
        app.extensions["password_hasher"] = self

    def generate(self, password: str) -> str:
        """Return a bcrypt hash suitable for ``user.password_hash``."""
        salt = _bcrypt.gensalt(rounds=self._rounds)
        return _bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")

    def verify(self, password: str, password_hash: str) -> bool:
        """Check a password without revealing why a hash failed to match."""
        try:
            return _bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("ascii")
            )
        except (TypeError, ValueError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Report whether a stored hash uses a different work factor."""
        parts = password_hash.split("$")
        if len(parts) < 3:
            return True
        try:
            return int(parts[2]) != self._rounds
        except ValueError:
            return True


@dataclass(slots=True)
class _Attempt:
    """Failure count and lock state for one login identity."""

    count: int
    first_at: float
    locked_until: float


class LoginAttemptTracker:
    """Track failed logins and temporary locks for one process.

    The store is intentionally in-process and protected by a lock. Multi-worker
    deployments should replace it with a shared store; the public methods stay
    the same so callers do not change.
    """

    def __init__(self) -> None:
        self._attempts: dict[str, _Attempt] = {}
        self._lock = threading.Lock()
        self._max_attempts = 5
        self._lock_seconds = 900.0
        self._window_seconds = 900.0

    def init_app(self, app: Flask) -> None:
        """Load login limits from the application configuration."""
        self._max_attempts = int(app.config["LOGIN_MAX_ATTEMPTS"])
        self._lock_seconds = float(app.config["LOGIN_LOCK_MINUTES"]) * 60.0
        self._window_seconds = float(app.config["LOGIN_ATTEMPT_WINDOW_MINUTES"]) * 60.0
        app.extensions["login_attempt_tracker"] = self

    @staticmethod
    def key(email: str, ip_address: str | None = None) -> str:
        """Build a stable key from a normalised email and optional client IP."""
        return f"{email.strip().lower()}|{ip_address or ''}"

    def is_locked(self, key: str) -> bool:
        """Return whether login is temporarily blocked for ``key``."""
        now = time.monotonic()
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None:
                return False
            if attempt.locked_until > now:
                return True
            if (
                attempt.locked_until > 0
                or now - attempt.first_at >= self._window_seconds
            ):
                self._attempts.pop(key, None)
            return False

    def record_failure(self, key: str) -> int:
        """Record a failed login and return the current consecutive count."""
        now = time.monotonic()
        with self._lock:
            attempt = self._attempts.get(key)
            expired = attempt is None or (
                attempt.locked_until > 0 and now >= attempt.locked_until
            )
            outside_window = (
                attempt is not None
                and attempt.locked_until == 0
                and now - attempt.first_at >= self._window_seconds
            )
            if expired or outside_window or attempt is None:
                attempt = _Attempt(count=0, first_at=now, locked_until=0.0)
            attempt.count += 1
            if attempt.count >= self._max_attempts:
                attempt.locked_until = now + self._lock_seconds
            self._attempts[key] = attempt
            return attempt.count

    def reset(self, key: str) -> None:
        """Clear failure state after a successful login or a password change."""
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        """Clear all tracked login attempts, primarily for test isolation."""
        with self._lock:
            self._attempts.clear()

    def remaining_attempts(self, key: str) -> int:
        """Return how many failures remain before a temporary lock."""
        now = time.monotonic()
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None or attempt.locked_until > now:
                return 0
            if (
                attempt.locked_until > 0
                or now - attempt.first_at >= self._window_seconds
            ):
                self._attempts.pop(key, None)
                return self._max_attempts
            return max(0, self._max_attempts - attempt.count)

    def locked_for(self, key: str) -> int:
        """Return the whole seconds remaining in a temporary lock."""
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None:
                return 0
            return max(0, math.ceil(attempt.locked_until - time.monotonic()))


class TokenDenylist:
    """Process-local revocation store for refresh-token ``jti`` values."""

    def __init__(self) -> None:
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    def init_app(self, app: Flask) -> None:
        """Expose the denylist to route helpers."""
        app.extensions["token_denylist"] = self

    def revoke(self, jti: str, expires_at: int | float) -> None:
        """Revoke a token until its original expiry time."""
        if not jti:
            return
        now = time.time()
        with self._lock:
            for token_id, expiry in list(self._entries.items()):
                if expiry <= now:
                    self._entries.pop(token_id, None)
            self._entries[jti] = float(expires_at)

    def is_revoked(self, jti: str) -> bool:
        """Return whether a token identifier has been revoked."""
        if not jti:
            return False
        with self._lock:
            expiry = self._entries.get(jti)
            if expiry is None:
                return False
            if expiry <= time.time():
                self._entries.pop(jti, None)
                return False
            return True

    def clear(self) -> None:
        """Clear all revoked token identifiers, primarily for test isolation."""
        with self._lock:
            self._entries.clear()


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
jwt = JWTManager()
bcrypt = BcryptHasher()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)
login_tracker = LoginAttemptTracker()
token_denylist = TokenDenylist()


def _register_jwt_callbacks() -> None:
    """Map JWT failures onto the shared structured error envelope."""

    @jwt.token_in_blocklist_loader
    def _is_revoked(
        _jwt_header: dict[str, object], jwt_payload: dict[str, object]
    ) -> bool:
        jti = jwt_payload.get("jti")
        return token_denylist.is_revoked(jti if isinstance(jti, str) else "")

    @jwt.unauthorized_loader
    def _unauthorized(_reason: str) -> Response:
        return error_response(401, "login", "Authentication is required.")

    @jwt.invalid_token_loader
    def _invalid(_reason: str) -> Response:
        return error_response(401, "invalid_token", "The token is invalid.")

    @jwt.expired_token_loader
    def _expired(_header: dict[str, object], _payload: dict[str, object]) -> Response:
        return error_response(401, "expired", "The token has expired.")

    @jwt.revoked_token_loader
    def _revoked(_header: dict[str, object], _payload: dict[str, object]) -> Response:
        return error_response(401, "revoked", "The token has been revoked.")


def init_extensions(app: Flask) -> None:
    """Attach and configure every extension on an application instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    cors.init_app(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=app.config["CORS_SUPPORTS_CREDENTIALS"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "Idempotency-Key",
        ],
        expose_headers=["X-Request-ID"],
    )
    login_tracker.init_app(app)
    token_denylist.init_app(app)
    _register_jwt_callbacks()


def revoke_current_token() -> None:
    """Revoke the JWT in the current request context using its ``jti`` and ``exp``."""
    claims = get_jwt()
    jti = claims.get("jti")
    expiry = claims.get("exp")
    if isinstance(jti, str) and isinstance(expiry, (int, float)):
        token_denylist.revoke(jti, expiry)
