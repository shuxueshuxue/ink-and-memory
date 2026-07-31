# [Input] Consume ClaudeAgentContextBuilder from backend/claude_agent/context_builder.py.
#         Mock database.list_sessions_in_range to provide writing session fixtures.
# [Output] Verify system_prompt assembly: header, recent sessions block, runtime context,
#          session count cap, empty-sessions fallback, and DB error graceful degradation.
# [Pos] test node in backend/tests
# [Sync] 2026-05-22: fresh implementation for Ink & Memory writing-session context.
#                    (Pawkeyland's context_builder tested pet persona / sticker / necklace —
#                     all removed; replaced with writing-session-based context.)
# [Sync] 2026-06-01: cover escaped literal JSON in the system prompt template so
#                    switch_editor guidance cannot break str.format rendering;
#                    align system-prompt fixtures with list_sessions_in_range.
# [Sync] 2026-06-06: run coroutine tests with explicit per-call event loops.
# [Sync] 2026-06-09: cover Planning Prompt Optimization workflow and escaped
#                    {{task}} placeholder in the system prompt.
# [Sync] 2026-06-16: cover fuzzy query guidance in Session Retrieval Workflow.
# [Sync] 2026-06-22: cover Settings SYSTEM_PROMPT rendering as a lower-priority
#                    configurable prompt block and empty-config fallback.

"""Unit tests for ClaudeAgentContextBuilder (Ink & Memory writing context)."""
from __future__ import annotations

import asyncio
import sys
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub claude_agent_sdk before libs.claude_agent_kit

from claude_agent.context_builder import (
    ClaudeAgentContextBuilder,
    _NO_SESSIONS_TEXT,
    _SESSIONS_HEADER,
    _render_session_entry,
)
from claude_agent.workspace_context import (
    WORKSPACE_CONTEXT_TEMPLATE,
    build_workspace_context_block,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _fake_sessions(n: int = 3) -> list[dict]:
    return [
        {
            "id": f"s{i}",
            "name": f"Session {i}",
            "updated_at": f"2026-05-{10 + i:02d}T10:00:00",
            "first_line": f"Today I thought about {'loneliness' if i % 2 == 0 else 'joy'}.",
        }
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# render_session_entry
# ---------------------------------------------------------------------------

class TestRenderSessionEntry(unittest.TestCase):
    def test_includes_date_from_updated_at(self):
        row = {"name": "Test", "updated_at": "2026-05-20T09:00:00", "first_line": "hello"}
        rendered = _render_session_entry(row)
        self.assertIn("2026-05-20", rendered)

    def test_includes_name_as_title(self):
        row = {"name": "My Journal", "updated_at": "2026-05-20", "first_line": "text"}
        rendered = _render_session_entry(row)
        self.assertIn("My Journal", rendered)

    def test_includes_first_line_as_excerpt(self):
        row = {"name": "X", "updated_at": "2026-05-20", "first_line": "I felt calm today."}
        rendered = _render_session_entry(row)
        self.assertIn("I felt calm today.", rendered)

    def test_empty_first_line_uses_placeholder(self):
        row = {"name": "X", "updated_at": "2026-05-20", "first_line": ""}
        rendered = _render_session_entry(row)
        self.assertIn("Empty entry", rendered)

    def test_missing_name_uses_untitled(self):
        row = {"name": None, "updated_at": "2026-05-20", "first_line": "text"}
        rendered = _render_session_entry(row)
        self.assertIn("Untitled", rendered)

    def test_falls_back_to_created_at_when_no_updated_at(self):
        row = {"name": "X", "created_at": "2026-04-01", "first_line": "text"}
        rendered = _render_session_entry(row)
        self.assertIn("2026-04-01", rendered)


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt(unittest.TestCase):
    def _builder(self, n: int = 5) -> ClaudeAgentContextBuilder:
        return ClaudeAgentContextBuilder(context_session_count=n)

    def _mock_db(self, sessions):
        """Return a patcher that makes database.list_sessions_in_range return sessions."""
        import database as _db  # noqa: PLC0415 — local import, backend path
        return unittest.mock.patch.object(_db, "list_sessions_in_range", return_value=sessions)

    def test_prompt_contains_sessions_header(self):
        with self._mock_db(_fake_sessions(2)):
            prompt = _run(self._builder().build_system_prompt("1"))
        self.assertIn(_SESSIONS_HEADER.strip(), prompt)

    def test_prompt_contains_session_names(self):
        sessions = _fake_sessions(2)
        with self._mock_db(sessions):
            prompt = _run(self._builder().build_system_prompt("1"))
        for s in sessions:
            self.assertIn(s["name"], prompt)

    def test_prompt_contains_writing_assistant_role(self):
        with self._mock_db([]):
            prompt = _run(self._builder().build_system_prompt("1"))
        self.assertIn("writing assistant", prompt.lower())

    def test_empty_sessions_uses_fallback(self):
        with self._mock_db([]):
            prompt = _run(self._builder().build_system_prompt("1"))
        self.assertIn(_NO_SESSIONS_TEXT.strip(), prompt)

    def test_respects_context_session_count_cap(self):
        sessions = _fake_sessions(10)
        with self._mock_db(sessions):
            prompt = _run(ClaudeAgentContextBuilder(context_session_count=3).build_system_prompt("1"))
        # Only first 3 session names should appear
        for s in sessions[:3]:
            self.assertIn(s["name"], prompt)
        for s in sessions[3:]:
            self.assertNotIn(s["name"], prompt)

    def test_db_error_gracefully_degrades_to_no_sessions(self):
        import database as _db
        with unittest.mock.patch.object(_db, "list_sessions_in_range", side_effect=RuntimeError("db down")):
            prompt = _run(self._builder().build_system_prompt("1"))
        self.assertIn(_NO_SESSIONS_TEXT.strip(), prompt)
        # Prompt should still be a valid string (not raise)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 50)

    def test_switch_editor_json_example_survives_template_formatting(self):
        with self._mock_db([]):
            prompt = _run(self._builder().build_system_prompt("1"))

        self.assertIn('returns {"ok": true}', prompt)
        self.assertIn(_NO_SESSIONS_TEXT.strip(), prompt)

    def test_planning_prompt_architect_template_survives_formatting(self):
        with self._mock_db([]):
            prompt = _run(self._builder().build_system_prompt("1"))

        self.assertIn("You are an Expert Prompt Architect.", prompt)
        self.assertIn("Optimized Prompt:", prompt)
        self.assertIn("USER REQUIREMENT: {{task}}", prompt)

    def test_session_retrieval_workflow_mentions_fuzzy_query(self):
        with self._mock_db([]):
            prompt = _run(self._builder().build_system_prompt("1"))

        self.assertIn('query="<topic or memory>"', prompt)
        self.assertIn("Default retrieval is character fuzzy matching", prompt)
        self.assertIn('retrieval_mode="vector"', prompt)

    def test_configured_system_prompt_is_lower_priority_block(self):
        with self._mock_db([]):
            prompt = _run(
                self._builder().build_system_prompt(
                    "1",
                    configured_system_prompt="Always answer with terse bullet points.",
                )
            )

        self.assertIn("## Configurable Page System Prompt (Lower Priority)", prompt)
        self.assertIn("Settings SYSTEM_PROMPT was loaded from system_config", prompt)
        self.assertIn("<settings_system_prompt>", prompt)
        self.assertIn("Always answer with terse bullet points.", prompt)
        self.assertIn("follow the system template", prompt)
        self.assertLess(
            prompt.index("Principles:"),
            prompt.index("## Configurable Page System Prompt"),
        )

    def test_empty_configured_system_prompt_is_omitted(self):
        with self._mock_db([]):
            prompt = _run(
                self._builder().build_system_prompt(
                    "1",
                    configured_system_prompt="  \n  ",
                )
            )

        self.assertNotIn("## Configurable Page System Prompt", prompt)
        self.assertNotIn("<settings_system_prompt>", prompt)


# ---------------------------------------------------------------------------
# build_user_message
# ---------------------------------------------------------------------------

class TestBuildUserMessage(unittest.TestCase):
    def setUp(self):
        self.builder = ClaudeAgentContextBuilder()

    def _text_blocks(self, blocks):
        """Return the concatenated text of all text-type blocks."""
        return "\n".join(b["text"] for b in blocks if b.get("type") == "text")

    def _parts(self, text: str) -> list:
        """Wrap plain text as a minimal AI-SDK UIMessage parts list."""
        return [{"type": "text", "text": text}]

    def test_returns_list_of_content_blocks(self):
        blocks = self.builder.build_user_message(self._parts("Hello there"))
        self.assertIsInstance(blocks, list)
        self.assertTrue(all(isinstance(b, dict) for b in blocks))

    def test_includes_runtime_context_block(self):
        blocks = self.builder.build_user_message(self._parts("Hello there"))
        combined = self._text_blocks(blocks)
        self.assertIn("<runtime_context>", combined)
        self.assertIn("Date:", combined)

    def test_user_text_is_last_block(self):
        blocks = self.builder.build_user_message(self._parts("My message"))
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        self.assertEqual(last["text"], "My message")

    def test_runtime_context_block_before_user_text(self):
        blocks = self.builder.build_user_message(self._parts("My message"))
        # At least two text blocks: runtime_context and user text
        self.assertGreaterEqual(len(blocks), 2)
        # runtime_context block appears before the final user text block
        runtime_idx = next(
            i for i, b in enumerate(blocks) if "<runtime_context>" in b.get("text", "")
        )
        user_idx = len(blocks) - 1
        self.assertLess(runtime_idx, user_idx)

    def test_includes_local_timezone(self):
        blocks = self.builder.build_user_message(self._parts("x"), local_timezone="Asia/Shanghai")
        combined = self._text_blocks(blocks)
        self.assertIn("Asia/Shanghai", combined)

    def test_no_timezone_by_default(self):
        blocks = self.builder.build_user_message(self._parts("x"))
        combined = self._text_blocks(blocks)
        # No Timezone line when local_timezone is not provided
        self.assertNotIn("Timezone:", combined)

    def test_empty_message_still_has_runtime_block(self):
        blocks = self.builder.build_user_message(self._parts(""))
        combined = self._text_blocks(blocks)
        self.assertIn("<runtime_context>", combined)

    def test_none_message_parts_still_has_runtime_block(self):
        blocks = self.builder.build_user_message(None)
        combined = self._text_blocks(blocks)
        self.assertIn("<runtime_context>", combined)

    def test_include_runtime_context_false_skips_block(self):
        blocks = self.builder.build_user_message(
            self._parts("hello"), include_runtime_context=False
        )
        combined = self._text_blocks(blocks)
        self.assertNotIn("<runtime_context>", combined)
        self.assertIn("hello", combined)

    def test_image_attachment_becomes_image_block(self):
        from dataclasses import dataclass

        @dataclass
        class _Att:
            name: str
            media_type: str
            data: str

        att = _Att(name="photo.jpg", media_type="image/jpeg", data="abc123")
        blocks = self.builder.build_user_message(self._parts("see image"), attachments=[att])
        image_blocks = [b for b in blocks if b.get("type") == "image"]
        self.assertEqual(len(image_blocks), 1)
        self.assertEqual(image_blocks[0]["source"]["data"], "abc123")

    def test_unsupported_attachment_is_skipped(self):
        from dataclasses import dataclass

        @dataclass
        class _Att:
            name: str
            media_type: str
            data: str

        att = _Att(name="doc.pdf", media_type="application/pdf", data="abc")
        blocks = self.builder.build_user_message(self._parts("see doc"), attachments=[att])
        image_blocks = [b for b in blocks if b.get("type") == "image"]
        self.assertEqual(len(image_blocks), 0)

    def test_model_and_thread_id_in_runtime_context(self):
        blocks = self.builder.build_user_message(
            self._parts("hi"), model="claude-3-5-sonnet", thread_id="sess-abc", max_turns=50
        )
        combined = self._text_blocks(blocks)
        self.assertIn("claude-3-5-sonnet", combined)
        self.assertIn("sess-abc", combined)
        self.assertIn("50", combined)

    def test_resume_flag_in_runtime_context(self):
        blocks = self.builder.build_user_message(self._parts("hi"), resume=True)
        combined = self._text_blocks(blocks)
        self.assertIn("Resumed conversation: yes", combined)

    def test_multiple_text_parts_concatenated(self):
        parts = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "world"}]
        blocks = self.builder.build_user_message(parts, include_runtime_context=False)
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        self.assertIn("Hello", last["text"])
        self.assertIn("world", last["text"])

    def test_file_part_rendered_as_metadata(self):
        parts = [
            {
                "type": "file",
                "url": "https://example.com/report.pdf",
                "filename": "report.pdf",
                "mediaType": "application/pdf",
                "size": 2048,
            }
        ]
        blocks = self.builder.build_user_message(parts, include_runtime_context=False)
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        text = last["text"]
        self.assertIn("report.pdf", text)
        self.assertIn("application/pdf", text)
        self.assertIn("2.0 KB", text)
        self.assertIn("https://example.com/report.pdf", text)

    def test_source_url_part_rendered_as_metadata(self):
        parts = [
            {
                "type": "source-url",
                "url": "https://example.com/article",
                "title": "My Article",
                "mediaType": "text/html",
            }
        ]
        blocks = self.builder.build_user_message(parts, include_runtime_context=False)
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        text = last["text"]
        self.assertIn("My Article", text)
        self.assertIn("https://example.com/article", text)
        self.assertIn("text/html", text)

    def test_workspace_file_part_rendered_as_metadata(self):
        parts = [
            {
                "type": "workspace-file",
                "fileName": "notes.md",
                "workspacePath": "/workspace/notes.md",
                "mimeType": "text/markdown",
                "size": 512,
                "savedAt": "2026-01-01T00:00:00Z",
                "hash": "abc123",
            }
        ]
        blocks = self.builder.build_user_message(parts, include_runtime_context=False)
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        text = last["text"]
        self.assertIn("notes.md", text)
        self.assertIn("/workspace/notes.md", text)
        self.assertIn("text/markdown", text)
        self.assertIn("512", text)
        self.assertIn("abc123", text)

    def test_mixed_text_and_file_parts(self):
        parts = [
            {"type": "text", "text": "Please review this file:"},
            {
                "type": "file",
                "url": "https://example.com/data.csv",
                "filename": "data.csv",
                "mediaType": "text/csv",
                "size": 1024,
            },
        ]
        blocks = self.builder.build_user_message(parts, include_runtime_context=False)
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        text = last["text"]
        self.assertIn("Please review this file:", text)
        self.assertIn("data.csv", text)
        self.assertIn("text/csv", text)


# ---------------------------------------------------------------------------
# build_workspace_context_block (standalone)
# ---------------------------------------------------------------------------

class TestBuildWorkspaceContextBlock(unittest.TestCase):
    def test_returns_empty_string_for_empty_cwd(self):
        self.assertEqual(build_workspace_context_block(""), "")

    def test_returns_empty_string_for_empty_string(self):
        # build_workspace_context_block treats "" as falsy → returns ""
        self.assertEqual(build_workspace_context_block(""), "")

    def test_substitutes_cwd_in_output(self):
        block = build_workspace_context_block("/workspaces/sess-abc")
        self.assertIn("/workspaces/sess-abc", block)

    def test_block_has_opening_tag(self):
        block = build_workspace_context_block("/some/path")
        self.assertTrue(block.startswith("<workspace_context>"))

    def test_block_has_closing_tag(self):
        block = build_workspace_context_block("/some/path")
        self.assertTrue(block.endswith("</workspace_context>"))

    def test_editor_virtual_index_described(self):
        block = build_workspace_context_block("/some/path")
        self.assertIn(".editor/", block)
        self.assertIn("cells.json", block)

    def test_constraint_line_present(self):
        block = build_workspace_context_block("/some/path")
        self.assertIn("CONSTRAINT", block)

    def test_no_leftover_braces(self):
        block = build_workspace_context_block("/workspaces/sess-xyz")
        # Only {{ }} escapes (rendered as { }) should remain, not {cwd}
        self.assertNotIn("{cwd}", block)


# ---------------------------------------------------------------------------
# build_user_message — workspace_context integration
# ---------------------------------------------------------------------------

class TestBuildUserMessageWorkspaceContext(unittest.TestCase):
    def setUp(self):
        self.builder = ClaudeAgentContextBuilder()

    def _parts(self, text: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": text}]

    def _text_blocks(self, blocks: list[dict[str, Any]]) -> str:
        return "\n".join(b["text"] for b in blocks if b.get("type") == "text")

    def test_no_workspace_context_when_cwd_not_provided(self):
        blocks = self.builder.build_user_message(self._parts("hello"))
        combined = self._text_blocks(blocks)
        self.assertNotIn("<workspace_context>", combined)

    def test_workspace_context_present_when_cwd_provided(self):
        blocks = self.builder.build_user_message(
            self._parts("hello"), cwd="/workspaces/sess-abc"
        )
        combined = self._text_blocks(blocks)
        self.assertIn("<workspace_context>", combined)

    def test_cwd_substituted_in_workspace_context(self):
        blocks = self.builder.build_user_message(
            self._parts("hello"), cwd="/workspaces/sess-abc"
        )
        combined = self._text_blocks(blocks)
        self.assertIn("/workspaces/sess-abc", combined)

    def test_workspace_context_after_runtime_context(self):
        blocks = self.builder.build_user_message(
            self._parts("hello"), cwd="/workspaces/sess-abc"
        )
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        runtime_idx = next(
            i for i, b in enumerate(text_blocks) if "<runtime_context>" in b["text"]
        )
        ws_idx = next(
            i for i, b in enumerate(text_blocks) if "<workspace_context>" in b["text"]
        )
        self.assertLess(runtime_idx, ws_idx)

    def test_workspace_context_before_user_text(self):
        blocks = self.builder.build_user_message(
            self._parts("user msg"), cwd="/workspaces/sess-abc"
        )
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        ws_idx = next(
            i for i, b in enumerate(text_blocks) if "<workspace_context>" in b["text"]
        )
        user_idx = len(text_blocks) - 1
        self.assertLess(ws_idx, user_idx)

    def test_user_text_still_last_when_cwd_provided(self):
        blocks = self.builder.build_user_message(
            self._parts("final text"), cwd="/workspaces/sess-abc"
        )
        last = blocks[-1]
        self.assertEqual(last["type"], "text")
        self.assertEqual(last["text"], "final text")

if __name__ == "__main__":
    unittest.main()
