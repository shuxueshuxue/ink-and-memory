#!/usr/bin/env python3
# [Input] Consume auth token helpers and common FastAPI dependency inputs.
# [Output] Provide shared auth/date/text helpers to backend router modules.
# [Pos] shared dependency node in backend/routers
# [Sync] 2026-05-25: extracted common dependency helpers from backend/server.py.
# [Sync] 2026-06-23: allow auth dependencies to read system access tokens from
#                    Authorization headers or OAuth login cookies.

import os
from datetime import datetime
import re
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import auth

http_bearer = HTTPBearer(auto_error=False)


def _count_mixed_words(text: str) -> int:
    """
    Count words in mixed Chinese/English text.
    - CJK characters count as 1 each
    - English is counted by whitespace-separated tokens
    """
    word_count = 0
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x3040 <= code <= 0x309F
            or 0x30A0 <= code <= 0x30FF
        ):
            word_count += 1
    english_words = re.sub(
        r"[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF]",
        " ",
        text,
    )
    word_count += len([w for w in english_words.split() if w])
    return word_count


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """
    Dependency to extract and verify JWT token from Authorization header.

    Raises:
        HTTPException 401 if token is missing or invalid
    """
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get("access_token") or request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    user_data = auth.verify_access_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_data


def _clean_timestamp(ts_raw: Optional[str]) -> Optional[datetime]:
    """Best-effort ISO parser for timestamps stored in DB."""
    if not ts_raw:
        return None
    try:
        cleaned = ts_raw.replace("Z", "+00:00")
        if "T" not in cleaned and " " in cleaned:
            cleaned = cleaned.replace(" ", "T")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _validate_date_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        datetime.fromisoformat(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
    if len(value) != 10:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
    return value
