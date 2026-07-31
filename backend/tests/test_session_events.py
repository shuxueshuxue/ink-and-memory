# [Input] Consume backend/session_events.py and backend/routers/sessions.py.
# [Output] Verify Edit Session event bus user isolation, browser SSE payloads, and route event publication.
# [Pos] test node in backend/tests
# [Sync] 2026-06-14: add tests for Edit Session event-driven sync bus.

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from session_events import EditSessionEvent, SessionEventBus
from routers import sessions as sessions_router


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


class TestSessionEventBus(unittest.TestCase):
    def test_publish_is_user_scoped(self):
        async def scenario():
            bus = SessionEventBus()
            user_one = await bus.subscribe("1")
            user_two = await bus.subscribe("2")

            await bus.publish(
                EditSessionEvent(
                    type="session_updated",
                    session_id="session-1",
                    user_id="1",
                    source="agent",
                    tool_call_id="tool-1",
                )
            )

            event = await asyncio.wait_for(user_one.get(), timeout=1.0)
            self.assertEqual(event.session_id, "session-1")
            self.assertTrue(user_two.empty())

            await bus.unsubscribe("1", user_one)
            await bus.unsubscribe("2", user_two)

        _run(scenario())

    def test_sse_frame_uses_browser_field_names(self):
        event = EditSessionEvent(
            type="session_updated",
            session_id="session-1",
            user_id="1",
            source="agent",
            tool_call_id="tool-1",
            tool_name="mcp__editor__write_segment",
            timestamp="2026-06-14T00:00:00Z",
        )

        frame = event.to_sse_frame()

        self.assertTrue(frame.startswith("event: session_updated\n"))
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line[len("data: "):])
        self.assertEqual(payload["type"], "session_updated")
        self.assertEqual(payload["sessionId"], "session-1")
        self.assertEqual(payload["toolCallId"], "tool-1")
        self.assertEqual(payload["toolName"], "mcp__editor__write_segment")
        self.assertNotIn("user_id", payload)
        self.assertNotIn("session_id", payload)


class TestSessionRouteEvents(unittest.TestCase):
    def test_save_session_publishes_api_update_event(self):
        async def scenario():
            subscription = await sessions_router.session_event_bus.subscribe("9")
            try:
                with unittest.mock.patch.object(
                    sessions_router.database,
                    "save_session",
                    return_value=None,
                ) as save_session:
                    result = await sessions_router.save_session(
                        {
                            "session_id": "session-api",
                            "name": "Session API",
                            "editor_state": {"id": "session-api", "cells": []},
                        },
                        {"user_id": 9},
                    )

                event = await asyncio.wait_for(subscription.get(), timeout=1.0)
            finally:
                await sessions_router.session_event_bus.unsubscribe("9", subscription)

            self.assertEqual(result, {"success": True})
            self.assertEqual(
                save_session.call_args.args[:4],
                (9, "session-api", {"id": "session-api", "cells": []}, "Session API"),
            )
            self.assertEqual(event.type, "session_updated")
            self.assertEqual(event.session_id, "session-api")
            self.assertEqual(event.source, "api")

        _run(scenario())


if __name__ == "__main__":
    unittest.main()
