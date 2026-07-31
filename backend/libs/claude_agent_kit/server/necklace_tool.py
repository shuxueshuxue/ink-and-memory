# [Input] Consume infrastructure.necklace_gateway and Agent-selected necklace tool names.
# [Output] Provide zero-argument handlers for read-only necklace live_context access.
# [Pos] tool-definition node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: split necklace access into zero-argument intent tools so server scripts own all API parameters.
# [Sync] 2026-05-10: remove stale unused typing import.
# [Sync] 2026-05-11: add previous-day activity intent with server-owned reference-date resolution.
# [Sync] 2026-05-11: keep Agent-facing tool descriptions semantic instead of example-phrase based.

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict

# from infrastructure.necklace_gateway import fetch_necklace_live_context


@dataclass(frozen=True)
class NecklaceToolSpec:
    """Server-owned field bundle for one Agent-selectable necklace tool."""

    fields: tuple[str, ...]
    description: str
    date_offset_days: int | None = None


NECKLACE_TOOL_SPECS: dict[str, NecklaceToolSpec] = {
    "get_pet_location": NecklaceToolSpec(
        fields=("last_location",),
        description="查询当前聊天宠物最后定位、安全区域状态、地址、气压、信号和电量等只读位置事实。",
    ),
    "get_pet_recent_activity": NecklaceToolSpec(
        fields=("last_location", "recent_actions"),
        description="查询当前聊天宠物当前时间附近短窗口内的主/次动作，并顺手查询位置安全状态。",
    ),
    "get_pet_today_activity": NecklaceToolSpec(
        fields=("last_location", "recent_actions", "day_stat"),
        description="查询当前聊天宠物当前自然日的动作摘要，并补充最近动作和位置安全状态。",
    ),
    "get_pet_yesterday_activity": NecklaceToolSpec(
        fields=("day_stat", "location_track"),
        description="查询当前聊天宠物前一自然日的动作摘要和当天定位轨迹。",
        date_offset_days=-1,
    ),
    "get_pet_month_activity": NecklaceToolSpec(
        fields=("month_stat",),
        description="查询当前聊天宠物当前自然月的动作摘要。",
    ),
    "get_pet_today_location_track": NecklaceToolSpec(
        fields=("location_track",),
        description="查询当前聊天宠物当前自然日的定位轨迹列表。",
    ),
    "get_pet_month_location_days": NecklaceToolSpec(
        fields=("location_days",),
        description="查询当前聊天宠物当前自然月中哪些日期有定位记录。",
    ),
}


class NecklaceNoInput(BaseModel):
    """No Agent-facing parameters; tool name is the query intent."""

    model_config = ConfigDict(extra="forbid")


def allowed_necklace_tool_names() -> list[str]:
    """Return fully-qualified allowed tool names for Claude Code options."""

    return [f"mcp__necklace__{name}" for name in NECKLACE_TOOL_SPECS]


def _reference_date_from_env() -> date:
    raw_date = str(os.getenv("PAWKEYLAND_NECKLACE_REFERENCE_DATE", "")).strip()
    if raw_date:
        try:
            return date.fromisoformat(raw_date[:10])
        except ValueError:
            pass

    raw_time = str(os.getenv("PAWKEYLAND_NECKLACE_REFERENCE_TIME", "")).strip()
    if raw_time:
        normalized = raw_time.replace(",", " ", 1)
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            pass

    return datetime.now(timezone.utc).astimezone().date()


def _date_for_spec(spec: NecklaceToolSpec) -> str | None:
    if spec.date_offset_days is None:
        return None
    return (_reference_date_from_env() + timedelta(days=spec.date_offset_days)).isoformat()


async def get_pet_live_context_handler(tool_name: str) -> str:
    """Fetch necklace live_context and return compact JSON text to Claude."""

    spec = NECKLACE_TOOL_SPECS.get(tool_name)
    if spec is None:
        return json.dumps(
            {"ok": False, "error": f"unknown_tool:{tool_name}", "live_context": {}},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    pet_id = str(os.getenv("PAWKEYLAND_AGENT_PET_ID", "")).strip()
    pet_species = str(os.getenv("PAWKEYLAND_AGENT_PET_SPECIES", "")).strip()
    pet_type = int(os.getenv("PAWKEYLAND_AGENT_PET_TYPE", "0") or 0)
    query_date = _date_for_spec(spec)
    fetch_kwargs: dict[str, object] = {
        "pet_id": pet_id,
        "pet_type": pet_type,
        "pet_species": pet_species,
        "fields": list(spec.fields),
    }
    if query_date:
        fetch_kwargs["date"] = query_date
    # result = await fetch_necklace_live_context(
    #     **fetch_kwargs,
    # )
    # result["tool_intent"] = tool_name
    # if query_date:
    #     result["query_date"] = query_date
    # return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    
