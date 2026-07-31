#!/usr/bin/env python3
# [Input] Consume scheduler module, shared auth dependency, and injected APScheduler instance.
# [Output] Register timeline-generation admin endpoint.
# [Pos] admin route node in backend/routers
# [Sync] 2026-05-25: extracted manual timeline trigger route from backend/server.py.

from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Depends

import scheduler as timeline_scheduler

from .deps import get_current_user

router = APIRouter()

_timeline_gen_scheduler: Optional[AsyncIOScheduler] = None


def set_timeline_gen_scheduler(s: AsyncIOScheduler) -> None:
    global _timeline_gen_scheduler
    _timeline_gen_scheduler = s


@router.post("/api/admin/trigger-timeline-generation")
async def trigger_timeline_generation(
    date: str = None,
    timezone: str = "Asia/Shanghai",
    current_user: dict = Depends(get_current_user),
):
    """
    Manually trigger timeline image generation for a specific date (testing/admin).

    Args:
        date: Target date in YYYY-MM-DD format (defaults to yesterday)
        timezone: Timezone name (default: Asia/Shanghai)

    Returns:
        Generation statistics: total, success, failed, skipped
    """
    del current_user

    if date is None:
        date = timeline_scheduler.get_previous_day(timezone)

    print(f"🔧 Manual trigger: Generating timeline images for {date}")

    next_run_time = None
    if _timeline_gen_scheduler is not None:
        job = _timeline_gen_scheduler.get_job("daily_timeline_generation")
        if job is not None and job.next_run_time is not None:
            next_run_time = job.next_run_time.isoformat()

    try:
        result = await timeline_scheduler.generate_timeline_images_for_date(
            date, timezone
        )
        response = {"success": True, "date": date, "timezone": timezone, **result}
        if next_run_time:
            response["next_run_time"] = next_run_time
        return response
    except Exception as e:
        import traceback

        traceback.print_exc()
        response = {"success": False, "error": str(e), "date": date, "timezone": timezone}
        if next_run_time:
            response["next_run_time"] = next_run_time
        return response
