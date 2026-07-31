#!/usr/bin/env python3
# [Input] Consume database friend APIs and shared auth dependency.
# [Output] Register /api/friends* endpoints.
# [Pos] friend route node in backend/routers
# [Sync] 2026-05-25: extracted friend and friend-picture routes from backend/server.py.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database

from .deps import get_current_user

router = APIRouter()


class UseInviteCodeRequest(BaseModel):
    code: str


class FriendRequestActionRequest(BaseModel):
    pass


@router.get("/api/friends/{friend_id}/pictures/{date}/full")
def get_friend_picture_full_endpoint(
    friend_id: int, date: str, current_user: dict = Depends(get_current_user)
):
    """Get full resolution image for a friend's specific date (only if users are friends)."""
    user_id = current_user["user_id"]
    full_image = database.get_friend_picture_full(user_id, friend_id, date)

    if not full_image:
        raise HTTPException(
            status_code=404, detail="Picture not found or not accessible"
        )

    return {"image_base64": full_image}


@router.post("/api/friends/invite/generate")
def generate_friend_invite(current_user: dict = Depends(get_current_user)):
    """Generate a new friend invite code (6 chars, 7 days validity)"""
    user_id = current_user["user_id"]
    result = database.generate_invite_code(user_id)
    return result


@router.post("/api/friends/invite/use")
def use_friend_invite(
    request: UseInviteCodeRequest, current_user: dict = Depends(get_current_user)
):
    """Use an invite code to send a friend request"""
    user_id = current_user["user_id"]
    result = database.use_invite_code(request.code, user_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/api/friends/requests")
def get_friend_requests(current_user: dict = Depends(get_current_user)):
    """Get all pending friend requests for current user"""
    user_id = current_user["user_id"]
    requests = database.get_friend_requests(user_id)
    return {"requests": requests}


@router.post("/api/friends/requests/{request_id}/accept")
def accept_friend_request(
    request_id: int, current_user: dict = Depends(get_current_user)
):
    """Accept a friend request"""
    user_id = current_user["user_id"]
    result = database.accept_friend_request(request_id, user_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/api/friends/requests/{request_id}/reject")
def reject_friend_request(
    request_id: int, current_user: dict = Depends(get_current_user)
):
    """Reject a friend request"""
    user_id = current_user["user_id"]
    result = database.reject_friend_request(request_id, user_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/api/friends")
def get_friends(current_user: dict = Depends(get_current_user)):
    """Get all accepted friends for current user"""
    user_id = current_user["user_id"]
    friends = database.get_friends(user_id)
    return {"friends": friends}


@router.delete("/api/friends/{friend_id}")
def remove_friend(friend_id: int, current_user: dict = Depends(get_current_user)):
    """Remove a friend"""
    user_id = current_user["user_id"]
    result = database.remove_friend(user_id, friend_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/api/friends/{friend_id}/timeline")
def get_friend_timeline(
    friend_id: int, limit: int = 30, current_user: dict = Depends(get_current_user)
):
    """Get a friend's timeline pictures (only if friends)"""
    user_id = current_user["user_id"]
    timeline = database.get_friend_timeline(user_id, friend_id, limit)
    if timeline is None:
        raise HTTPException(status_code=403, detail="Not friends or friend not found")
    return {"pictures": timeline}
