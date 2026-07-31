# [Input] Consume sessions_tool.handle_get_sessions_range with mocked database rows.
# [Output] Verify Agent session retrieval tool compatibility, fuzzy query ranking,
#          label filters, and vector-interface boundary behavior.
# [Pos] test node in backend/tests
# [Sync] 2026-06-16: add coverage for configurable get_sessions_range retrieval.

"""Unit tests for the Claude Agent user MCP session retrieval tool."""
from __future__ import annotations

import json
import os
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub SDK before importing kit package

import database
from libs.claude_agent_kit.server.sessions_tool import handle_get_sessions_range


class TestGetSessionsRangeTool(unittest.TestCase):
    def _call(self, args: dict) -> dict:
        with unittest.mock.patch.dict(os.environ, {"INK_AGENT_USER_ID": "42"}):
            return json.loads(handle_get_sessions_range(args))

    def test_date_only_call_keeps_range_listing_compatibility(self):
        rows = [
            {
                "id": "s1",
                "name": "Old note",
                "labels": ["成长"],
                "updated_at": "2026-01-02T10:00:00",
                "first_line": "A lightweight preview.",
            }
        ]
        with unittest.mock.patch.object(
            database, "list_sessions_in_range", return_value=rows
        ) as query:
            data = self._call({"start_date": "2026-01-01", "end_date": "2026-01-31"})

        self.assertTrue(data["ok"])
        self.assertEqual(data["sessions"][0]["sessionId"], "s1")
        self.assertNotIn("match", data["sessions"][0])
        query.assert_called_once_with(
            42, "2026-01-01", "2026-01-31", include_text=False
        )

    def test_query_uses_full_text_fuzzy_match_and_filters_irrelevant_rows(self):
        rows = [
            {
                "id": "semantic",
                "name": "普通标题",
                "labels": [],
                "updated_at": "2026-02-02T10:00:00",
                "first_line": "今天我很累。",
                "text": "今天我很累。\n\n后来写到一次孤独的夜间散步。",
            },
            {
                "id": "unrelated",
                "name": "快乐晚餐",
                "labels": ["社交"],
                "updated_at": "2026-02-01T10:00:00",
                "first_line": "和朋友吃饭。",
                "text": "和朋友吃饭，心情很好。",
            },
        ]
        with unittest.mock.patch.object(
            database, "list_sessions_in_range", return_value=rows
        ) as query:
            data = self._call(
                {
                    "start_date": "2026-02-01",
                    "end_date": "2026-02-28",
                    "query": "孤独 散步",
                }
            )

        self.assertTrue(data["ok"])
        self.assertEqual([s["sessionId"] for s in data["sessions"]], ["semantic"])
        self.assertEqual(data["sessions"][0]["match"]["fields"], ["text"])
        query.assert_called_once_with(
            42, "2026-02-01", "2026-02-28", include_text=True
        )

    def test_labels_support_all_match_filter(self):
        rows = [
            {
                "id": "both",
                "name": "A",
                "labels": ["孤独", "成长"],
                "updated_at": "2026-03-02",
                "first_line": "match",
            },
            {
                "id": "one",
                "name": "B",
                "labels": ["孤独"],
                "updated_at": "2026-03-01",
                "first_line": "partial",
            },
        ]
        with unittest.mock.patch.object(
            database, "list_sessions_in_range", return_value=rows
        ):
            data = self._call(
                {
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-31",
                    "labels": ["孤独", "成长"],
                    "label_match": "all",
                }
            )

        self.assertTrue(data["ok"])
        self.assertEqual([s["sessionId"] for s in data["sessions"]], ["both"])
        self.assertEqual(data["sessions"][0]["match"]["fields"], ["labels"])

    def test_auto_mode_degrades_vector_query_to_fuzzy(self):
        rows = [
            {
                "id": "s1",
                "name": "关于孤独",
                "labels": [],
                "updated_at": "2026-04-01",
                "first_line": "孤独的一天。",
                "text": "孤独的一天。",
            }
        ]
        with unittest.mock.patch.object(
            database, "list_sessions_in_range", return_value=rows
        ):
            data = self._call(
                {
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                    "retrieval_mode": "auto",
                    "query": "孤独",
                    "vector_query": {"text": "孤独"},
                }
            )

        self.assertTrue(data["ok"])
        self.assertEqual(data["retrieval"]["mode"], "fuzzy")
        self.assertIn("vector_retrieval_unconfigured_falling_back_to_fuzzy", data["warnings"])

    def test_vector_mode_reports_unavailable_without_db_query(self):
        with unittest.mock.patch.object(database, "list_sessions_in_range") as query:
            data = self._call(
                {
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                    "retrieval_mode": "vector",
                    "vector_query": {"text": "孤独"},
                }
            )

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "vector_retrieval_unavailable")
        query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
