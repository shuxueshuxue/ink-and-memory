#!/usr/bin/env python3
# [Input] Consume database analysis report APIs and shared auth dependency.
# [Output] Register /api/reports endpoints.
# [Pos] report route node in backend/routers
# [Sync] 2026-05-25: extracted report routes from backend/server.py.

from fastapi import APIRouter, Depends, HTTPException

import database

from .deps import get_current_user

router = APIRouter()


@router.get("/api/reports")
def get_reports(limit: int = 10, current_user: dict = Depends(get_current_user)):
    """Get recent analysis reports."""
    user_id = current_user["user_id"]
    reports = database.get_analysis_reports(user_id, limit)
    return {"reports": reports}


@router.post("/api/reports")
def save_report(request: dict, current_user: dict = Depends(get_current_user)):
    """
    Save an analysis report.

    Request body:
    {
        "report_type": "echoes" | "traits" | "patterns",
        "report_data": {...},
        "all_notes_text": "optional text"
    }
    """
    user_id = current_user["user_id"]
    report_type = request.get("report_type")
    report_data = request.get("report_data")
    all_notes_text = request.get("all_notes_text", "")

    if not report_type or not report_data:
        raise HTTPException(
            status_code=400, detail="report_type and report_data required"
        )

    database.save_analysis_report(user_id, report_type, report_data, all_notes_text)
    return {"success": True}
