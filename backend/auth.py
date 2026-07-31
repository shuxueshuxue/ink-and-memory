#!/usr/bin/env python3
# [Input] Consume JWT/password environment variables and opaque token values.
# [Output] Provide password hashing, access-token JWT, refresh-token, and token hash helpers.
# [Pos] auth utility node in backend
# [Sync] 2026-06-23: support JWT_SECRET/JWT_EXPIRES_IN, token types, and refresh-token hashing for OAuth/Device Flow.
"""
Authentication module for Ink & Memory.

Provides JWT token generation/verification, refresh-token helpers, and
password hashing for password, Google OAuth, and Device Flow logins.
"""

from datetime import datetime, timedelta
import hashlib
import os
import re
import secrets
from typing import Optional

import bcrypt
import jwt

# @@@ JWT Configuration
SECRET_KEY = (
    os.environ.get("JWT_SECRET")
    or os.environ.get("JWT_SECRET_KEY")
    or "dev-secret-change-in-production-123456789"
)
ALGORITHM = "HS256"


def parse_duration(value: Optional[str], default: str = "7d") -> timedelta:
    """Parse compact duration strings such as ``15m`` or ``30d``."""

    raw = (value or default).strip().lower()
    if raw.isdigit():
        return timedelta(seconds=int(raw))

    match = re.fullmatch(r"(\d+)\s*([smhd])", raw)
    if not match:
        match = re.fullmatch(r"(\d+)\s*(seconds?|minutes?|hours?|days?)", raw)
    if not match:
        raise ValueError(f"Invalid duration value: {value!r}")

    amount = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("s"):
        return timedelta(seconds=amount)
    if unit.startswith("m"):
        return timedelta(minutes=amount)
    if unit.startswith("h"):
        return timedelta(hours=amount)
    if unit.startswith("d"):
        return timedelta(days=amount)
    raise ValueError(f"Invalid duration unit: {unit!r}")


ACCESS_TOKEN_EXPIRE_DELTA = parse_duration(os.environ.get("JWT_EXPIRES_IN"), "7d")
REFRESH_TOKEN_EXPIRE_DELTA = parse_duration(
    os.environ.get("REFRESH_TOKEN_EXPIRES_IN"), "30d"
)
ACCESS_TOKEN_EXPIRE_MINUTES = int(ACCESS_TOKEN_EXPIRE_DELTA.total_seconds() // 60)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def create_access_token(
    user_id: int,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token.

    Args:
        user_id: User ID
        email: User email

    Returns:
        JWT token string
    """
    now = datetime.utcnow()
    expire = now + (expires_delta or ACCESS_TOKEN_EXPIRE_DELTA)

    payload = {
        "sub": str(user_id),  # Subject: user ID
        "email": email,
        "typ": "access",
        "exp": expire,  # Expiration time
        "iat": now,  # Issued at
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def hash_token(token: str) -> str:
    """Return a stable SHA-256 hash for opaque refresh/device tokens."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token_value() -> tuple[str, str, datetime]:
    """Create an opaque refresh token and its DB-safe hash/expiry."""

    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + REFRESH_TOKEN_EXPIRE_DELTA
    return token, hash_token(token), expires_at


def verify_access_token(token: str) -> Optional[dict]:
    """
    Verify JWT token and extract payload.

    Args:
        token: JWT token string

    Returns:
        Payload dict with user_id and email, or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("typ")
        if token_type not in (None, "access"):
            return None

        user_id = int(payload.get("sub"))
        email = payload.get("email")

        if user_id is None or email is None:
            return None

        return {
            "user_id": user_id,
            "email": email
        }
    except jwt.ExpiredSignatureError:
        print("Token expired")
        return None
    except (jwt.InvalidTokenError, TypeError, ValueError):
        print("Invalid token")
        return None

def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        Token string or None
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]
