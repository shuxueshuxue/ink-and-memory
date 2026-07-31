#!/usr/bin/env python3
# [Input] Consume auth/database modules and shared current-user dependency.
# [Output] Register authentication, logout, current-user, and first-login
#          import routes.
# [Pos] auth route node in backend/routers
# [Sync] 2026-05-25: extracted auth and migration endpoints from backend/server.py.
# [Sync] 2026-06-23: add /auth/me and /auth/logout aliases for OAuth and
#                    Device Flow token clients while keeping /api/me.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import auth
import database

from .deps import get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str


class ImportDataRequest(BaseModel):
    currentSession: Optional[str] = None
    calendarEntries: Optional[str] = None
    dailyPictures: Optional[str] = None
    voiceCustomizations: Optional[str] = None
    metaPrompt: Optional[str] = None
    stateConfig: Optional[str] = None
    selectedState: Optional[str] = None
    analysisReports: Optional[str] = None
    oldDocument: Optional[str] = None


@router.post("/api/register", response_model=TokenResponse)
def register(request: RegisterRequest):
    """
    Register a new user.

    Returns JWT token and user info.
    """
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Email and password required")

    if len(request.password) < 6:
        raise HTTPException(
            status_code=400, detail="Password must be at least 6 characters"
        )

    password_hash = auth.hash_password(request.password)

    try:
        user_id = database.create_user(
            request.email, password_hash, request.display_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    database.auto_fork_system_decks(user_id)
    token = auth.create_access_token(user_id, request.email)

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": request.email,
            "display_name": request.display_name,
        },
    }


@router.post("/api/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Login with email and password.

    Returns JWT token and user info.
    """
    user = database.get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not auth.verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_decks = database.get_user_decks(user["id"])
    if len(user_decks) == 0:
        database.auto_fork_system_decks(user["id"])

    token = auth.create_access_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
    }


def _serialize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "avatar_url": user.get("avatar_url"),
        "role": user.get("role", "user"),
        "created_at": user["created_at"],
    }


def _get_current_user_info(current_user: dict) -> dict:
    user = database.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _serialize_user(user)


@router.get("/api/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user info from token.

    Requires Authorization header or system auth cookie.
    """
    return _get_current_user_info(current_user)


@router.get("/auth/me")
def get_auth_current_user_info(current_user: dict = Depends(get_current_user)):
    """Alias for OAuth-oriented clients."""
    return _get_current_user_info(current_user)


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """Clear auth cookies and revoke refresh tokens for the current session."""

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        database.revoke_refresh_token(auth.hash_token(refresh_token))
    else:
        database.revoke_user_refresh_tokens(current_user["user_id"])

    for cookie_name in ("access_token", "refresh_token", "token"):
        response.delete_cookie(cookie_name, path="/")
    return {"success": True}


@router.post("/api/import-local-data")
def import_local_data(
    request: ImportDataRequest, current_user: dict = Depends(get_current_user)
):
    """
    Import localStorage data to database on first login.

    Extracts sessions, pictures, preferences, and reports from localStorage export.
    """
    import json

    user_id = current_user["user_id"]

    print(f"\n🔍 Migration request for user {user_id}:")
    print(
        f"  - currentSession: {len(request.currentSession) if request.currentSession else 0} chars"
    )
    print(
        f"  - calendarEntries: {len(request.calendarEntries) if request.calendarEntries else 0} chars"
    )
    print(
        f"  - dailyPictures: {len(request.dailyPictures) if request.dailyPictures else 0} chars"
    )
    print(
        f"  - oldDocument: {len(request.oldDocument) if request.oldDocument else 0} chars"
    )

    sessions = []

    if request.currentSession:
        try:
            current = json.loads(request.currentSession)
            sessions.append(
                {
                    "id": "current-session",
                    "name": "Current Session",
                    "editor_state": current,
                }
            )
            print(f"✅ Imported current session ({len(str(current))} chars)")
        except Exception as e:
            print(f"❌ Failed to parse current session: {e}")

    if request.calendarEntries:
        try:
            calendar = json.loads(request.calendarEntries)
            print(f"📅 Parsed calendar with {len(calendar)} dates")
            for date, entries in calendar.items():
                print(f"  - {date}: {len(entries)} entries")
                for entry in entries:
                    sessions.append(
                        {
                            "id": entry["id"],
                            "name": f"{date} - {entry.get('firstLine', 'Untitled')}",
                            "editor_state": entry["state"],
                        }
                    )
        except Exception as e:
            print(f"❌ Failed to parse calendar entries: {e}")
            import traceback

            traceback.print_exc()

    if request.oldDocument:
        try:
            old_doc = json.loads(request.oldDocument)
            if old_doc and old_doc.get("document"):
                sessions.append(
                    {
                        "id": "old-document",
                        "name": "Old Document (migrated)",
                        "editor_state": {
                            "cells": [{"type": "text", "content": str(old_doc)}]
                        },
                    }
                )
        except Exception:
            pass

    pictures = []
    if request.dailyPictures:
        try:
            pics = json.loads(request.dailyPictures)
            for pic in pics:
                pictures.append(
                    {
                        "date": pic["date"],
                        "image_base64": pic["base64"],
                        "prompt": pic.get("prompt", ""),
                    }
                )
        except Exception:
            pass

    preferences = {}
    if request.voiceCustomizations:
        try:
            preferences["voice_configs"] = json.loads(request.voiceCustomizations)
        except Exception:
            pass

    if request.metaPrompt:
        preferences["meta_prompt"] = request.metaPrompt

    if request.stateConfig:
        try:
            preferences["state_config"] = json.loads(request.stateConfig)
        except Exception:
            pass

    if request.selectedState:
        preferences["selected_state"] = request.selectedState

    reports = []
    if request.analysisReports:
        try:
            report_list = json.loads(request.analysisReports)
            for report in report_list:
                reports.append(
                    {
                        "type": report.get("type", "unknown"),
                        "data": report.get("data", {}),
                        "allNotes": report.get("allNotes", ""),
                        "timestamp": report.get("timestamp", ""),
                    }
                )
        except Exception:
            pass

    database.import_user_data(user_id, sessions, pictures, preferences, reports)

    return {
        "success": True,
        "imported": {
            "sessions": len(sessions),
            "pictures": len(pictures),
            "preferences": len([k for k, v in preferences.items() if v]),
            "reports": len(reports),
        },
    }


@router.post("/api/import-calendar-recovery")
def import_calendar_recovery(
    request: dict, current_user: dict = Depends(get_current_user)
):
    """
    Recovery endpoint to import calendar entries that were missed in initial migration.

    Request body:
    {
        "calendarEntries": "{\"2025-11-01\": [...]}"  # JSON string
    }
    """
    import json

    user_id = current_user["user_id"]
    calendar_json = request.get("calendarEntries")

    if not calendar_json:
        raise HTTPException(status_code=400, detail="calendarEntries required")

    sessions = []
    try:
        calendar = json.loads(calendar_json)
        print(f"📅 Recovery import: {len(calendar)} dates")
        for date, entries in calendar.items():
            print(f"  - {date}: {len(entries)} entries")
            for entry in entries:
                sessions.append(
                    {
                        "id": entry["id"],
                        "name": f"{date} - {entry.get('firstLine', 'Untitled')}",
                        "editor_state": entry["state"],
                    }
                )
    except Exception as e:
        print(f"❌ Failed to parse calendar: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=400, detail=f"Failed to parse calendar: {str(e)}"
        )

    database.import_user_data(user_id, sessions, [], {}, [])

    return {"success": True, "imported": {"sessions": len(sessions)}}


@router.post("/api/mark-first-login-completed")
def mark_first_login_completed(current_user: dict = Depends(get_current_user)):
    """
    Mark user's first login as completed.
    Called after migration dialog is shown (migrate or skip).
    """
    user_id = current_user["user_id"]
    database.set_first_login_completed(user_id)
    return {"success": True}
