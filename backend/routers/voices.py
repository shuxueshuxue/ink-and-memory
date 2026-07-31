#!/usr/bin/env python3
# [Input] Consume database deck/voice APIs and shared auth dependency.
# [Output] Register /api/decks* and /api/voices* endpoints.
# [Pos] deck-and-voice route node in backend/routers
# [Sync] 2026-05-25: extracted deck and voice management routes from backend/server.py.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database

from .deps import get_current_user

router = APIRouter()


class DeckCreateRequest(BaseModel):
    name: str
    description: str = None
    name_zh: str = None
    name_en: str = None
    description_zh: str = None
    description_en: str = None
    icon: str = None
    color: str = None


class DeckUpdateRequest(BaseModel):
    name: str = None
    description: str = None
    name_zh: str = None
    name_en: str = None
    description_zh: str = None
    description_en: str = None
    icon: str = None
    color: str = None
    enabled: bool = None
    order_index: int = None


class VoiceCreateRequest(BaseModel):
    deck_id: str
    name: str
    system_prompt: str
    name_zh: str = None
    name_en: str = None
    icon: str = None
    color: str = None
    memory_workspace_config: dict = None


class VoiceUpdateRequest(BaseModel):
    name: str = None
    system_prompt: str = None
    name_zh: str = None
    name_en: str = None
    icon: str = None
    color: str = None
    enabled: bool = None
    order_index: int = None
    thread_id: str = None
    memory_workspace_config: dict = None


class VoiceForkRequest(BaseModel):
    target_deck_id: str


@router.get("/api/decks")
def list_decks(published: bool = False, current_user: dict = Depends(get_current_user)):
    """Get decks - either user's own or published community decks"""
    if published:
        decks = database.get_published_decks()
    else:
        user_id = current_user["user_id"]
        decks = database.get_user_decks(user_id)
    return {"decks": decks}


@router.get("/api/decks/{deck_id}")
def get_deck(deck_id: str, current_user: dict = Depends(get_current_user)):
    """Get deck with all voices"""
    user_id = current_user["user_id"]
    deck = database.get_deck_with_voices(user_id, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@router.post("/api/decks")
def create_deck(
    request: DeckCreateRequest, current_user: dict = Depends(get_current_user)
):
    """Create a new user deck"""
    user_id = current_user["user_id"]
    deck_id = database.create_deck(
        user_id,
        name=request.name,
        description=request.description,
        name_zh=request.name_zh,
        name_en=request.name_en,
        description_zh=request.description_zh,
        description_en=request.description_en,
        icon=request.icon,
        color=request.color,
    )
    return {"deck_id": deck_id}


@router.put("/api/decks/{deck_id}")
def update_deck(
    deck_id: str,
    request: DeckUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a user deck"""
    user_id = current_user["user_id"]
    updates = {k: v for k, v in request.dict().items() if v is not None}

    success = database.update_deck(user_id, deck_id, updates)
    if not success:
        raise HTTPException(
            status_code=404, detail="Deck not found or permission denied"
        )
    return {"success": True}


@router.delete("/api/decks/{deck_id}")
def delete_deck(deck_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a user deck (cascades to voices)"""
    user_id = current_user["user_id"]
    success = database.delete_deck(user_id, deck_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Deck not found or permission denied"
        )
    return {"success": True}


@router.post("/api/decks/{deck_id}/fork")
def fork_deck(deck_id: str, current_user: dict = Depends(get_current_user)):
    """Fork a deck (system or published community deck) to create user's own copy"""
    user_id = current_user["user_id"]
    try:
        new_deck_id = database.fork_deck(user_id, deck_id)
        database.increment_deck_install_count(deck_id)
        return {"deck_id": new_deck_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/decks/{deck_id}/publish")
def publish_deck(deck_id: str, current_user: dict = Depends(get_current_user)):
    """
    Publish/unpublish a deck to community store.
    @@@ Warning: Publishing breaks parent_id chain (deck becomes standalone)
    """
    user_id = current_user["user_id"]
    try:
        deck = database.get_deck_with_voices(user_id, deck_id)
        if not deck:
            raise HTTPException(
                status_code=404, detail="Deck not found or not owned by user"
            )

        if deck.get("published"):
            database.unpublish_deck(deck_id, user_id)
            return {"success": True, "published": False}
        else:
            database.publish_deck(deck_id, user_id)
            return {"success": True, "published": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/decks/{deck_id}/sync")
def sync_deck(deck_id: str, current_user: dict = Depends(get_current_user)):
    """Sync user's forked deck with parent template (force overwrites local changes)"""
    user_id = current_user["user_id"]
    try:
        result = database.sync_deck_with_parent(user_id, deck_id, force=True)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/voices")
def create_voice(
    request: VoiceCreateRequest, current_user: dict = Depends(get_current_user)
):
    """Create a new voice in a user deck"""
    user_id = current_user["user_id"]
    try:
        voice_id = database.create_voice(
            user_id,
            deck_id=request.deck_id,
            name=request.name,
            system_prompt=request.system_prompt,
            name_zh=request.name_zh,
            name_en=request.name_en,
            icon=request.icon,
            color=request.color,
            memory_workspace_config=request.memory_workspace_config,
        )
        return {"voice_id": voice_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/voices/{voice_id}")
def update_voice(
    voice_id: str,
    request: VoiceUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a user voice"""
    user_id = current_user["user_id"]
    updates = {k: v for k, v in request.dict().items() if v is not None}

    success = database.update_voice(user_id, voice_id, updates)
    if not success:
        raise HTTPException(
            status_code=404, detail="Voice not found or permission denied"
        )
    return {"success": True}


@router.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a user voice"""
    user_id = current_user["user_id"]
    success = database.delete_voice(user_id, voice_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Voice not found or permission denied"
        )
    return {"success": True}


@router.post("/api/voices/{voice_id}/fork")
def fork_voice(
    voice_id: str,
    request: VoiceForkRequest,
    current_user: dict = Depends(get_current_user),
):
    """Fork a voice to a user deck"""
    user_id = current_user["user_id"]
    try:
        new_voice_id = database.fork_voice(user_id, voice_id, request.target_deck_id)
        return {"voice_id": new_voice_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
