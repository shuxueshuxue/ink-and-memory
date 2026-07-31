#!/usr/bin/env python3
# [Input] Consume config/default voice values, database preferences APIs, and shared auth dependency.
# [Output] Register preferences and default-voice endpoints.
# [Pos] preferences route node in backend/routers
# [Sync] 2026-05-25: extracted preference routes from backend/server.py.

from fastapi import APIRouter, Depends

import config
import database

from .deps import get_current_user

router = APIRouter()


@router.get("/api/preferences")
def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get user preferences."""
    user_id = current_user["user_id"]
    preferences = database.get_preferences(user_id)
    return preferences or {}


@router.post("/api/preferences")
def save_preferences_endpoint(
    request: dict, current_user: dict = Depends(get_current_user)
):
    """
    Save user preferences.

    Request body can contain any of:
    - voice_configs: dict
    - meta_prompt: str
    - state_config: dict
    - selected_state: str
    """
    user_id = current_user["user_id"]

    database.save_preferences(
        user_id,
        voice_configs=request.get("voice_configs"),
        meta_prompt=request.get("meta_prompt"),
        state_config=request.get("state_config"),
        selected_state=request.get("selected_state"),
        timezone=request.get("timezone"),
    )

    return {"success": True}


@router.get("/api/default-voices")
def get_default_voices():
    """Get default voice configurations"""
    return config.VOICE_ARCHETYPES
