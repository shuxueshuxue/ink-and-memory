# [Input] Consume claude_agent.thread_retrieval with in-memory chat thread candidates.
# [Output] Verify Chat history retriever plugin behavior, fuzzy ranking, scope
#          filtering, and vector-interface boundary.
# [Pos] test node in backend/tests
# [Sync] 2026-06-27: initial coverage for Chat history search retrievers.

"""Unit tests for Claude Agent Chat history retrieval plugins."""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub SDK before importing claude_agent

from claude_agent.thread_retrieval import (
    build_chat_thread_search_config,
    search_chat_threads,
)


class TestChatThreadRetrieval(unittest.TestCase):
    def _search(self, args: dict, candidates: list[dict]):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            config = build_chat_thread_search_config(**args)
        self.assertIsNotNone(config)
        return search_chat_threads(candidates, config)  # type: ignore[arg-type]

    def test_fuzzy_search_matches_thread_title(self):
        candidates = [
            {
                "id": "t1",
                "title": "论文初筛流程",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-02",
                "messages_text": "我们聊了投稿准备。",
            },
            {
                "id": "t2",
                "title": "晚餐想法",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-01",
                "messages_text": "今晚吃什么。",
            },
        ]

        outcome = self._search({"query": "论文 初筛"}, candidates)

        self.assertTrue(outcome.ok)
        self.assertEqual([thread["id"] for thread in outcome.threads], ["t1"])
        self.assertEqual(outcome.threads[0]["match"]["fields"], ["title"])

    def test_fuzzy_search_matches_message_text(self):
        candidates = [
            {
                "id": "semantic",
                "title": "普通标题",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-02",
                "messages_text": "之前讨论过向量库先不接入，只保留接口。",
            },
            {
                "id": "unrelated",
                "title": "另一个标题",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-01",
                "messages_text": "普通聊天。",
            },
        ]

        outcome = self._search({"query": "向量库 接口"}, candidates)

        self.assertTrue(outcome.ok)
        self.assertEqual([thread["id"] for thread in outcome.threads], ["semantic"])
        self.assertEqual(outcome.threads[0]["match"]["fields"], ["messages"])
        self.assertIn("向量库", outcome.threads[0]["match"]["excerpt"])

    def test_title_scope_does_not_match_messages(self):
        candidates = [
            {
                "id": "message-only",
                "title": "普通标题",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-02",
                "messages_text": "消息里有检索器插件。",
            }
        ]

        outcome = self._search(
            {"query": "检索器插件", "search_scope": "title"},
            candidates,
        )

        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.threads, [])

    def test_auto_mode_degrades_vector_query_to_fuzzy(self):
        candidates = [
            {
                "id": "t1",
                "title": "向量检索接口",
                "created_at": "2026-06-01",
                "updated_at": "2026-06-01",
                "messages_text": "",
            }
        ]

        outcome = self._search(
            {
                "query": "向量",
                "retrieval_mode": "auto",
                "vector_query": {"text": "向量"},
            },
            candidates,
        )

        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.retrieval["mode"], "fuzzy")
        self.assertIn(
            "vector_retrieval_unconfigured_falling_back_to_fuzzy",
            outcome.warnings,
        )

    def test_vector_mode_reports_unavailable(self):
        outcome = self._search(
            {
                "retrieval_mode": "vector",
                "vector_query": {"text": "向量"},
            },
            [],
        )

        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error, "vector_retrieval_unavailable")
        self.assertEqual(outcome.threads, [])


if __name__ == "__main__":
    unittest.main()
