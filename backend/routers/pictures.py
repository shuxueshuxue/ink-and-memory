#!/usr/bin/env python3
# [Input] Consume picture_service generation helper, database picture APIs, and shared auth/date helpers.
# [Output] Register /api/pictures* endpoints.
# [Pos] picture route node in backend/routers
# [Sync] 2026-05-25: extracted picture routes from backend/server.py.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database
from picture_service import _generate_picture_for_date

from .deps import _validate_date_str, get_current_user

router = APIRouter()


class GeneratePictureRequest(BaseModel):
    target_date: Optional[str] = None
    notes_override: Optional[str] = None
    dry_run: bool = False
    skip_if_exists: bool = False
    timezone: Optional[str] = "Asia/Shanghai"


@router.get("/api/pictures")
def get_pictures(limit: int = 30, current_user: dict = Depends(get_current_user)):
    """
    Get recent daily pictures for current user (thumbnails only for fast loading).

    Query params:
    - limit: Max number of pictures to return (default 30)
    """
    user_id = current_user["user_id"]
    pictures = database.get_daily_pictures(user_id, limit)
    return {"pictures": pictures}


@router.post("/api/pictures/generate")
def generate_picture_endpoint(
    request: GeneratePictureRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a picture for a specific date.
    - If dry_run=True, returns the image but does not save.
    - If skip_if_exists=True, returns existing image without regenerating.
    """
    user_id = current_user["user_id"]
    tz = request.timezone or "Asia/Shanghai"
    result = _generate_picture_for_date(
        user_id=user_id,
        target_date=request.target_date,
        timezone=tz,
        notes_override=request.notes_override,
        skip_if_exists=request.skip_if_exists,
        dry_run=request.dry_run,
    )
    return result


@router.get("/api/pictures/range")
def get_pictures_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    """
    Get daily pictures within an optional date range.
    """
    user_id = current_user["user_id"]
    start_date = _validate_date_str(start_date)
    end_date = _validate_date_str(end_date)
    pictures = database.get_daily_pictures_range(user_id, start_date, end_date, limit)
    return {"pictures": pictures}


@router.get("/api/pictures/{date}/full")
def get_picture_full(date: str, current_user: dict = Depends(get_current_user)):
    """
    Get full resolution image for a specific date (on-demand loading).

    Path params:
    - date: Date in YYYY-MM-DD format
    """
    user_id = current_user["user_id"]
    full_image = database.get_daily_picture_full(user_id, date)

    if not full_image:
        raise HTTPException(status_code=404, detail="Picture not found for this date")

    return {"image_base64": full_image}


@router.post("/api/pictures")
def save_picture(request: dict, current_user: dict = Depends(get_current_user)):
    """
    Save a daily picture.

    Request body:
    {
        "date": "YYYY-MM-DD",
        "image_base64": "base64 string",
        "prompt": "optional prompt"
    }
    """
    user_id = current_user["user_id"]
    date = request.get("date")
    image_base64 = request.get("image_base64")
    thumbnail_base64 = request.get("thumbnail_base64")
    prompt = request.get("prompt", "")

    if not date or not image_base64:
        raise HTTPException(status_code=400, detail="date and image_base64 required")

    database.save_daily_picture(user_id, date, image_base64, prompt, thumbnail_base64)
    return {"success": True}
