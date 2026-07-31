#!/usr/bin/env python3
# [Input] Consume database session storage APIs, edit-session events, and shared auth/date helpers.
# [Output] Register /api/sessions* endpoints and session event stream.
# [Pos] session route node in backend/routers
# [Sync] 2026-05-25: extracted session storage routes from backend/server.py.
# [Sync] 2026-06-14: publish Edit Session update/delete events and expose
#                    /api/sessions/events SSE for frontend Agent-write sync.

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import database
from session_events import EditSessionEvent, session_event_bus

from .deps import (
    _clean_timestamp,
    _count_mixed_words,
    _validate_date_str,
    get_current_user,
)

router = APIRouter()


class SessionBatchRequest(BaseModel):
    ids: List[str]


@router.post("/api/sessions")
async def save_session(request: dict, current_user: dict = Depends(get_current_user)):
    """
    Save or update a session.

    Request body:
    {
        "session_id": "string",
        "name": "optional string",
        "editor_state": {...},
        "labels": ["optional", "list", "of", "tags"]
    }
    """
    user_id = current_user["user_id"]
    session_id = request.get("session_id")
    editor_state = request.get("editor_state")
    name = request.get("name")
    labels = request.get("labels")

    if not session_id or not editor_state:
        raise HTTPException(
            status_code=400, detail="session_id and editor_state required"
        )

    await asyncio.to_thread(
        database.save_session,
        user_id,
        session_id,
        editor_state,
        name,
        labels=labels,
    )
    asyncio.create_task(
        session_event_bus.publish(
            EditSessionEvent(
                type="session_updated",
                session_id=session_id,
                user_id=str(user_id),
                source="api",
            )
        )
    )

    return {"success": True}


@router.get("/api/sessions/events")
async def session_events(current_user: dict = Depends(get_current_user)):
    """Stream authenticated Edit Session persistence events for the current user."""

    user_id = str(current_user["user_id"])
    return StreamingResponse(
        session_event_bus.read(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/sessions")
def list_sessions(
    timezone: str = "Asia/Shanghai", current_user: dict = Depends(get_current_user)
):
    """
    List all sessions for current user.
    Returns: Array of session metadata (without full editor state) plus local day key + first line.
    """
    return list_sessions_with_range(None, None, timezone, current_user)


@router.get("/api/sessions/range")
def list_sessions_with_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "Asia/Shanghai",
    current_user: dict = Depends(get_current_user),
):
    """
    List sessions within an optional date range.
    """
    user_id = current_user["user_id"]
    start_date = _validate_date_str(start_date)
    end_date = _validate_date_str(end_date)
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    if start_date or end_date:
        sessions = database.list_sessions_in_range(user_id, start_date, end_date)
    else:
        sessions = database.list_sessions(user_id)

    enriched = []
    for s in sessions:
        dt = _clean_timestamp(s.get("created_at") or s.get("updated_at"))
        date_key = dt.astimezone(tz).strftime("%Y-%m-%d") if dt else None
        enriched.append({**s, "date_key": date_key})

    return {"sessions": enriched}


@router.post("/api/sessions/batch")
def get_sessions_batch(
    payload: SessionBatchRequest, current_user: dict = Depends(get_current_user)
):
    """
    Fetch multiple sessions (with editor_state) in a single request.
    """
    user_id = current_user["user_id"]
    session_ids = payload.ids or []

    if not session_ids:
        return {"sessions": []}

    sessions = database.get_sessions_batch(user_id, session_ids)
    return {"sessions": sessions}


@router.get("/api/sessions/aggregate")
def get_sessions_aggregate(
    timezone: str = "Asia/Shanghai", current_user: dict = Depends(get_current_user)
):
    """
    Aggregate stats across all sessions for the user.
    Returns stats only (no concatenated text) and per-session summaries.
    """
    user_id = current_user["user_id"]
    sessions = database.get_all_sessions_with_text(user_id)

    total_entries = 0
    total_words = 0
    days = set()

    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    for s in sessions:
        text = s.get("text", "") or ""
        if text.strip():
            total_entries += 1
            total_words += _count_mixed_words(text)
        ts_raw = s.get("updated_at") or s.get("created_at")
        if ts_raw:
            try:
                cleaned = ts_raw.replace("Z", "+00:00")
                if "T" not in cleaned and " " in cleaned:
                    cleaned = cleaned.replace(" ", "T")
                dt = datetime.fromisoformat(cleaned)
                local_dt = dt.astimezone(tz)
                days.add(local_dt.strftime("%Y-%m-%d"))
            except Exception:
                continue

    stats = {
        "total_days": len(days),
        "total_entries": total_entries,
        "total_words": total_words,
    }

    summaries = [
        {
            "id": s["id"],
            "name": s.get("name"),
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at"),
            "has_text": bool((s.get("text") or "").strip()),
            "word_count": len((s.get("text") or "").split()) if s.get("text") else 0,
        }
        for s in sessions
    ]

    return {
        "stats": stats,
        "sessions": summaries,
        "timezone": timezone,
    }


@router.get("/api/sessions/{session_id}")
def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get a specific session by ID.

    Returns: Full session including editor_state
    """
    user_id = current_user["user_id"]
    session = database.get_session(user_id, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a session."""
    user_id = current_user["user_id"]
    await asyncio.to_thread(database.delete_session, user_id, session_id)
    asyncio.create_task(
        session_event_bus.publish(
            EditSessionEvent(
                type="session_deleted",
                session_id=session_id,
                user_id=str(user_id),
                source="api",
            )
        )
    )
    return {"success": True}
