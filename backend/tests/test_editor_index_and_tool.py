# [Input] Consume editor_index.py, editor_tool.py helpers.
# [Output] Unit tests for editor virtual index read helpers and MCP write tool handlers.
# [Sync] 2026-05-28: initial test suite — editor_index and editor_tool.
# [Sync] 2026-05-29: add SDK stub import; add boundary-path tests for is_editor_index_path
#                    (sub-path, unknown stem, README, deep absolute path) and degraded-state
#                    tests for get_editor_resource_data (missing fields → empty list / None).
# [Sync] 2026-05-29: update TestHandleEditorReadToolDispatch to use INK_EDITOR_STATE_JSON
#                    (session-inline env var) as the primary data source; legacy
#                    INK_EDITOR_STATE_FILE fallback also verified.
# [Sync] 2026-05-29: replace read-tool tests with write-tool tests; data source now comes
#                    from database (INK_AGENT_EDITOR_SESSION_ID / INK_AGENT_USER_ID) not file IPC;
#                    mock database.get_session / database.save_session for isolation.
# [Sync] 2026-05-29: session_id flows via MCP tool arguments from agent prompt context;
#                    remove all os.environ patching; mock database.get_db for SQL path.

"""Unit tests for the .editor/ virtual index and EditorEngine MCP write tools."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Adjust PYTHONPATH so we can import from the libs tree when running from
# the backend/ root via ``python3 -m pytest tests/``.
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import tests._sdk_stubs  # noqa: F401 — must precede any libs.claude_agent_kit import

from libs.claude_agent_kit.server.editor_index import (
    EDITOR_RESOURCES,
    get_editor_resource_data,
    is_editor_index_path,
    resolve_editor_resource,
)
from libs.claude_agent_kit.server.editor_tool import (
    _delete_segment,
    _insert_widget,
    _reply_to_comment,
    _write_segment,
    allowed_editor_tool_names,
    handle_editor_write_tool,
)


# ---------------------------------------------------------------------------
# editor_index tests (unchanged — virtual index is still used for reading)
# ---------------------------------------------------------------------------


class TestIsEditorIndexPath(unittest.TestCase):
    def test_recognises_dot_editor_prefix(self):
        self.assertTrue(is_editor_index_path(".editor/cells.json"))

    def test_recognises_absolute_path_under_editor(self):
        self.assertTrue(is_editor_index_path("/workspace/.editor/session.json"))

    def test_false_for_unrelated_path(self):
        self.assertFalse(is_editor_index_path("src/main.py"))

    def test_false_for_none_like_empty(self):
        self.assertFalse(is_editor_index_path(""))

    def test_false_for_sub_path_under_editor(self):
        """Only top-level .editor/ files are virtual; subdirectories are not."""
        self.assertFalse(is_editor_index_path(".editor/subdir/cells.json"))

    def test_false_for_unknown_stem_in_editor(self):
        self.assertFalse(is_editor_index_path(".editor/unknown_resource.json"))

    def test_true_for_full_state_resource(self):
        self.assertTrue(is_editor_index_path(".editor/full_state.json"))

    def test_true_for_commentors_resource(self):
        self.assertTrue(is_editor_index_path(".editor/commentors.json"))

    def test_true_for_tasks_resource(self):
        self.assertTrue(is_editor_index_path(".editor/tasks.json"))

    def test_false_for_readme_in_editor(self):
        """README.md is not a virtual resource."""
        self.assertFalse(is_editor_index_path(".editor/README.md"))

    def test_recognises_deep_absolute_path(self):
        """Absolute path with multiple parent directories must still match."""
        self.assertTrue(
            is_editor_index_path("/some/deep/workspace/sess-abc/.editor/full_state.json")
        )


class TestResolveEditorResource(unittest.TestCase):
    def test_resolves_cells(self):
        self.assertEqual(resolve_editor_resource(".editor/cells.json"), "cells")

    def test_resolves_session(self):
        self.assertEqual(resolve_editor_resource(".editor/session.json"), "session")

    def test_unknown_returns_none(self):
        self.assertIsNone(resolve_editor_resource(".editor/unknown.json"))

    def test_non_editor_path_returns_none(self):
        self.assertIsNone(resolve_editor_resource("README.md"))


class TestGetEditorResourceData(unittest.TestCase):
    _STATE = {
        "id": "sess-1",
        "cells": [{"id": "c1", "type": "text", "content": "Hello"}],
        "commentors": [{"id": "cm1", "phrase": "Hello"}],
        "tasks": [{"id": "t1", "title": "Do stuff"}],
        "selectedState": "neutral",
        "createdAt": "2026-01-01T00:00:00Z",
    }

    def test_full_state_returns_whole_dict(self):
        result = get_editor_resource_data(".editor/full_state.json", self._STATE)
        self.assertEqual(result, self._STATE)

    def test_cells_slice(self):
        result = get_editor_resource_data(".editor/cells.json", self._STATE)
        self.assertEqual(result, {"cells": self._STATE["cells"]})

    def test_session_slice(self):
        result = get_editor_resource_data(".editor/session.json", self._STATE)
        self.assertIn("id", result)
        self.assertIn("selectedState", result)
        self.assertNotIn("cells", result)

    def test_commentors_slice(self):
        result = get_editor_resource_data(".editor/commentors.json", self._STATE)
        self.assertEqual(result, {"commentors": self._STATE["commentors"]})

    def test_unknown_resource_returns_empty(self):
        result = get_editor_resource_data(".editor/unknown.json", self._STATE)
        self.assertEqual(result, {})

    def test_cells_missing_from_state_returns_empty_list(self):
        """When editor_state lacks 'cells', the slice returns an empty list."""
        result = get_editor_resource_data(".editor/cells.json", {})
        self.assertEqual(result, {"cells": []})

    def test_tasks_missing_from_state_returns_empty_list(self):
        result = get_editor_resource_data(".editor/tasks.json", {})
        self.assertEqual(result, {"tasks": []})

    def test_session_missing_fields_returns_none_values(self):
        """Partial editor_state → session slice fills missing fields with None."""
        result = get_editor_resource_data(".editor/session.json", {})
        self.assertIsNone(result.get("id"))
        self.assertIsNone(result.get("selectedState"))
        self.assertIsNone(result.get("createdAt"))

    def test_full_state_with_empty_dict(self):
        """full_state.json with empty state returns the same empty dict."""
        result = get_editor_resource_data(".editor/full_state.json", {})
        self.assertEqual(result, {})

    def test_non_editor_path_returns_empty(self):
        result = get_editor_resource_data("files/other.txt", self._STATE)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# editor_tool write-tool tests
# ---------------------------------------------------------------------------

_SAMPLE_STATE = {
    "id": "session-abc",
    "selectedState": "happy",
    "createdAt": "2026-05-01T10:00:00Z",
    "cells": [
        {"id": "c1", "type": "text", "content": "Once upon a time"},
        {"id": "c2", "type": "widget", "widgetType": "image", "data": {"voiceId": "v1"}},
        {"id": "c3", "type": "text", "content": "The end."},
    ],
    "commentors": [
        {
            "id": "cm1",
            "phrase": "Once upon",
            "voiceId": "v1",
            "appliedAt": "2026-05-01T11:00:00Z",
            "feedback": "starred",
            "text": "Great opening",
            "conversation": [],
        },
    ],
}

_EDITOR_SESSION_ID = "sess-api-abc"   # user_sessions.id from /api/sessions
_WORKSPACE_ID = "workspace-thread-xyz"  # cwd basename — intentionally different


class TestAllowedEditorToolNames(unittest.TestCase):
    def test_returns_mcp_prefixed_names(self):
        names = allowed_editor_tool_names()
        self.assertIn("mcp__editor__write_segment", names)
        self.assertIn("mcp__editor__delete_segment", names)
        self.assertIn("mcp__editor__insert_widget", names)
        self.assertIn("mcp__editor__reply_to_comment", names)

    def test_write_tools_match_expected_set(self):
        # switch_editor was added to EDITOR_WRITE_TOOL_SPECS by the
        # workspace-switch feature (editor_tool.py:200).  Assert the full
        # name set instead of a bare count so future additions fail with a
        # meaningful diff rather than "6 != 5".
        self.assertEqual(
            set(allowed_editor_tool_names()),
            {
                "mcp__editor__write_segment",
                "mcp__editor__delete_segment",
                "mcp__editor__insert_widget",
                "mcp__editor__reply_to_comment",
                "mcp__editor__switch_editor",
            },
        )

    def test_no_read_tools_present(self):
        names = allowed_editor_tool_names()
        self.assertNotIn("mcp__editor__list_segments", names)
        self.assertNotIn("mcp__editor__read_segment", names)
        self.assertNotIn("mcp__editor__read_session_meta", names)
        self.assertNotIn("mcp__editor__list_comments", names)
        self.assertNotIn("mcp__editor__read_comment", names)


def _make_db_mock(state: dict) -> MagicMock:
    """Create a mock ``database`` module with a get_db returning a SQLite-like conn."""
    import copy
    mock_db = MagicMock()

    # Mock the get_db() → connection → execute/commit/close flow.
    mock_conn = MagicMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: json.dumps(copy.deepcopy(state)) if key == "editor_state_json" else None
    mock_conn.execute.return_value.fetchone.return_value = mock_row
    mock_conn.commit.return_value = None
    mock_conn.close.return_value = None
    mock_db.get_db.return_value = mock_conn

    return mock_db


class TestWriteSegment(unittest.TestCase):
    def test_replaces_text_cell_content(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_write_segment(_EDITOR_SESSION_ID, "c1", "New text", "test"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["cellId"], "c1")
        # Verify save was called (UPDATE executed)
        self.assertTrue(mock_db.get_db.return_value.execute.called)

    def test_missing_cell_id_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_write_segment(_EDITOR_SESSION_ID, "", "text", "reason"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cellId_required")

    def test_cell_not_found_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_write_segment(_EDITOR_SESSION_ID, "nonexistent", "x", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cell_not_found")

    def test_non_text_cell_returns_error(self):
        """write_segment must reject widget cells."""
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_write_segment(_EDITOR_SESSION_ID, "c2", "text", "reason"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cell_not_text_type")

    def test_db_save_failure_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        mock_db.get_db.return_value.commit.side_effect = RuntimeError("db error")
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_write_segment(_EDITOR_SESSION_ID, "c1", "text", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "save_failed")


class TestDeleteSegment(unittest.TestCase):
    def test_removes_cell_by_id(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_delete_segment(_EDITOR_SESSION_ID, "c1", "reason"))
        self.assertTrue(result["ok"])

    def test_missing_cell_id_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_delete_segment(_EDITOR_SESSION_ID, "", "reason"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cellId_required")

    def test_cell_not_found_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_delete_segment(_EDITOR_SESSION_ID, "no-such", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cell_not_found")


class TestInsertWidget(unittest.TestCase):
    def test_appends_to_end_when_no_after_cell_id(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_insert_widget(
                _EDITOR_SESSION_ID, "chat", {"voiceId": "v2"}, "", "add chat"
            ))
        self.assertTrue(result["ok"])
        self.assertEqual(result["widgetType"], "chat")

    def test_inserts_after_specified_cell(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_insert_widget(
                _EDITOR_SESSION_ID, "image", {}, "c1", "add image"
            ))
        self.assertTrue(result["ok"])

    def test_missing_widget_type_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_insert_widget(_EDITOR_SESSION_ID, "", {}, "", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "widgetType_required")

    def test_after_cell_not_found_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_insert_widget(
                _EDITOR_SESSION_ID, "chat", {}, "nonexistent", "r"
            ))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "after_cell_not_found")

    def test_new_cell_has_uuid_id(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_insert_widget(_EDITOR_SESSION_ID, "chat", {}, "", "r"))
        self.assertTrue(result["ok"])
        cell_id = result["cellId"]
        self.assertEqual(len(cell_id.replace("-", "")), 32)


class TestReplyToComment(unittest.TestCase):
    def test_appends_agent_reply(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_reply_to_comment(
                _EDITOR_SESSION_ID, "cm1", "Interesting point!", "reply"
            ))
        self.assertTrue(result["ok"])

    def test_missing_comment_id_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_reply_to_comment(_EDITOR_SESSION_ID, "", "text", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "commentId_required")

    def test_missing_content_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_reply_to_comment(_EDITOR_SESSION_ID, "cm1", "", "r"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "content_required")

    def test_comment_not_found_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(_reply_to_comment(
                _EDITOR_SESSION_ID, "no-such-comment", "text", "r"
            ))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "comment_not_found")


class TestHandleEditorWriteToolDispatch(unittest.TestCase):
    """Integration tests for handle_editor_write_tool.

    editor_session_id (user_sessions.id from /api/sessions) is passed via tool
    arguments — distinct from the workspace directory name and Claude thread ID.
    No os.environ patching required.
    """

    def test_write_segment_dispatches_correctly(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "write_segment",
                {"editor_session_id": _EDITOR_SESSION_ID, "cellId": "c1", "text": "Updated text", "reason": "test"},
            ))
        self.assertTrue(result["ok"])

    def test_delete_segment_dispatches_correctly(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "delete_segment",
                {"editor_session_id": _EDITOR_SESSION_ID, "cellId": "c3", "reason": "cleanup"},
            ))
        self.assertTrue(result["ok"])

    def test_insert_widget_dispatches_correctly(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "insert_widget",
                {"editor_session_id": _EDITOR_SESSION_ID, "widgetType": "chat", "data": {}, "reason": "add widget"},
            ))
        self.assertTrue(result["ok"])

    def test_reply_to_comment_dispatches_correctly(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "reply_to_comment",
                {"editor_session_id": _EDITOR_SESSION_ID, "commentId": "cm1", "content": "Great!", "reason": "reply"},
            ))
        self.assertTrue(result["ok"])

    def test_unknown_tool_returns_error(self):
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "no_such_tool",
                {"editor_session_id": _EDITOR_SESSION_ID},
            ))
        self.assertFalse(result["ok"])
        self.assertIn("unknown_tool", result["error"])

    def test_missing_session_id_in_arguments_returns_error(self):
        """When editor_session_id is absent from arguments, all write tools return an error."""
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool(
                "write_segment",
                {"cellId": "c1", "text": "x", "reason": "r"},  # no editor_session_id
            ))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "editor_session_id_required")

    def test_empty_arguments_returns_error(self):
        """Empty arguments dict → editor_session_id missing → error."""
        mock_db = _make_db_mock(_SAMPLE_STATE)
        with patch.dict("sys.modules", {"database": mock_db}):
            result = json.loads(handle_editor_write_tool("write_segment", {}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "editor_session_id_required")


if __name__ == "__main__":
    unittest.main()
