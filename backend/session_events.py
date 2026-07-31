#!/usr/bin/env python3
# [Input] Edit Session write/delete callers in routers/sessions.py and claude_agent/service.py.
# [Output] User-scoped SSE events for /api/sessions/events consumers.
# [Pos] edit-session event bus node in backend
# [Sync] 2026-06-14: add authenticated Edit Session update/delete event fan-out so
#                    Agent MCP writes can notify the frontend after DB writes complete.

"""Edit Session event fan-out.

This bus is intentionally separate from ``claude_agent.event_bus``.  Claude
Agent streams carry per-turn model output; this module carries user-scoped
writing-session persistence notifications.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
from dataclasses import asdict, dataclass, field
from typing import AsyncIterator, Literal, Optional

EditSessionEventType = Literal["session_updated", "session_deleted"]
EditSessionEventSource = Literal["api", "agent"]


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _keepalive_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("INK_SESSION_EVENT_KEEPALIVE_S", "15") or "15"))
    except (TypeError, ValueError):
        return 15.0


@dataclass(frozen=True)
class EditSessionEvent:
    """A single Edit Session persistence event.

    ``user_id`` stays server-side and is not serialized to the browser.  It is
    used only for subscriber isolation.
    """

    type: EditSessionEventType
    session_id: str
    user_id: str
    source: EditSessionEventSource = "api"
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: str = field(default_factory=_utc_timestamp)

    def to_browser_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("user_id", None)
        payload["sessionId"] = payload.pop("session_id")
        if payload.get("tool_call_id") is not None:
            payload["toolCallId"] = payload.pop("tool_call_id")
        else:
            payload.pop("tool_call_id", None)
        if payload.get("tool_name") is not None:
            payload["toolName"] = payload.pop("tool_name")
        else:
            payload.pop("tool_name", None)
        return payload

    def to_sse_frame(self) -> str:
        return (
            f"event: {self.type}\n"
            f"data: {json.dumps(self.to_browser_payload(), ensure_ascii=False)}\n\n"
        )


class SessionEventBus:
    """In-process, user-scoped fan-out for Edit Session events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[EditSessionEvent]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: str) -> asyncio.Queue[EditSessionEvent]:
        queue: asyncio.Queue[EditSessionEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(str(user_id), set()).add(queue)
        return queue

    async def unsubscribe(
        self, user_id: str, queue: asyncio.Queue[EditSessionEvent]
    ) -> None:
        async with self._lock:
            queues = self._subscribers.get(str(user_id))
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._subscribers.pop(str(user_id), None)

    async def publish(self, event: EditSessionEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(str(event.user_id), set()))
        for queue in queues:
            await queue.put(event)

    async def read(self, user_id: str) -> AsyncIterator[str]:
        queue = await self.subscribe(str(user_id))
        keepalive_s = _keepalive_seconds()
        try:
            yield "event: connected\ndata: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=keepalive_s)
                    yield event.to_sse_frame()
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            await self.unsubscribe(str(user_id), queue)


session_event_bus = SessionEventBus()
