# [Input] Consume workspace.get_tasks_dir/read_task_items,
#         sdk_env.apply_task_v2_env_to_options, agent_runner permission lists,
#         claude_agent.service todo helpers, and routers.claude_agent todos endpoint.
# [Output] Verify claude-todo backend contracts: tasks-dir resolution (containment,
#          None cases), v2 env injection gating, read_task_items derivation,
#          v1 TodoWrite SSE frames (not collected), REST todos endpoint contract
#          (exists:false / 404 / filesystem rebuild), five-tool low-sensitivity
#          classification, and INK_AGENT_TODO_MAX_ITEMS truncation.
# [Pos] test node in backend/tests
# [Sync] 2026-07-20: initial — claude-todo §5.1/§5.4/§5.5/§5.7 backend coverage
#                    (design §9 key cases ①-⑦).
# [Sync] 2026-07-26: HOTFIX — v2 env injection semantics change: the 0.2.128
#                    bundled CLI enables task tools by default, so
#                    CLAUDE_CODE_TASK_LIST_ID=main is now ALWAYS pinned
#                    (gate-independent); the legacy gate only forces explicit
#                    CLAUDE_CODE_ENABLE_TASKS=1.

"""Tests for the claude-todo backend half (todo list capture & contracts).

Covers (claude-todo §9 key cases):
- ① v1 ``tool-input-available(TodoWrite)`` → ``todo-updated`` frame, never
  collected into ``collected_parts`` (§5.3/§5.4).
- ② v2 env injection: ``CLAUDE_CODE_TASK_LIST_ID=main`` always pinned;
  ``CLAUDE_CODE_ENABLE_TASKS=1`` only when ``INK_AGENT_TASK_V2_ENABLED`` is
  on (§5.1, 2026-07-26 semantics).
- ③ ``get_tasks_dir`` traversal / missing-workspace → ``None`` (§5.1).
- ④ ``read_task_items`` filters ``metadata._internal`` tasks and drops
  blockers that are already completed (§5.1/§5.2).
- ⑤ ``GET /api/claude-agent/threads/{thread_id}/todos`` ownership 404 and
  ``exists:false`` contract (§5.5).
- ⑥ five todo tools classified low-sensitivity → explicit allow in auto
  mode; v2 tools present in ``DEFAULT_ALLOWED_TOOLS`` (§5.7).
- ⑦ ``INK_AGENT_TODO_MAX_ITEMS`` truncation sets ``truncated:true`` (§5.4).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub claude_agent_sdk before kit imports

from libs.claude_agent_kit.server import sdk_env as sdk_env_module
from libs.claude_agent_kit.server.agent_runner import (
    DEFAULT_ALLOWED_TOOLS,
    _LOW_SENSITIVITY_QUERY_TOOL_NAMES,
    _apply_low_sensitivity_query_permission,
)
from libs.claude_agent_kit.server.sdk_env import apply_task_v2_env_to_options
from libs.claude_agent_kit.server.workspace import get_tasks_dir, read_task_items
from libs.claude_agent_kit.types import ToolEventPayload

import claude_agent.service as service_module
from claude_agent.service import (
    ClaudeAgentService,
    TodoState,
    _TurnContext,
    build_thread_todos_payload,
)
from claude_agent.thread_pool import AgentRunState
from claude_agent.tool_confirmation_store import ToolConfirmationStore


def _make_options(env: dict | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(env=dict(env or {}))


def _write_task(tasks_dir: Path, name: str, data: dict) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# get_tasks_dir (claude-todo §5.1) — ③
# ---------------------------------------------------------------------------


class TestGetTasksDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _workspace(self, session_id: str = "thread-todo") -> Path:
        ws = self.root / session_id
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def test_tasks_main_dir_returned(self):
        ws = self._workspace()
        tasks = ws / ".claude-home" / "tasks" / "main"
        tasks.mkdir(parents=True)
        self.assertEqual(get_tasks_dir("thread-todo"), tasks.resolve())

    def test_none_when_tasks_dir_missing(self):
        self._workspace()
        self.assertIsNone(get_tasks_dir("thread-todo"))

    def test_none_when_workspace_missing(self):
        self.assertIsNone(get_tasks_dir("thread-never-ran"))

    def test_none_for_traversal_session_id(self):
        for bad in ("../escape", "a/b", "a\\b", ".."):
            with self.subTest(session_id=bad):
                self.assertIsNone(get_tasks_dir(bad))

    def test_none_when_tasks_dir_is_escape_symlink(self):
        ws = self._workspace()
        outside = self.root / "outside-tasks"
        outside.mkdir()
        claude_home = ws / ".claude-home" / "tasks"
        claude_home.mkdir(parents=True)
        try:
            (claude_home / "main").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        self.assertIsNone(get_tasks_dir("thread-todo"))


# ---------------------------------------------------------------------------
# apply_task_v2_env_to_options (claude-todo §5.1) — ②
# ---------------------------------------------------------------------------


class TestApplyTaskV2EnvToOptions(unittest.TestCase):
    def test_task_list_id_pinned_when_gate_unset(self):
        """2026-07-26 fix: CLAUDE_CODE_TASK_LIST_ID=main is always pinned —
        the new CLI enables task tools by default, so an unpinned run writes
        tasks to a per-session list dir the panel never finds."""
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INK_AGENT_TASK_V2_ENABLED", None)
            options = _make_options({"ANTHROPIC_AUTH_TOKEN": "tok"})
            result = apply_task_v2_env_to_options(options)
        self.assertIs(result, options)
        self.assertNotIn("CLAUDE_CODE_ENABLE_TASKS", options.env)
        self.assertEqual(options.env["CLAUDE_CODE_TASK_LIST_ID"], "main")
        self.assertEqual(options.env["ANTHROPIC_AUTH_TOKEN"], "tok")

    def test_task_list_id_pinned_when_gate_falsey(self):
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_TASK_V2_ENABLED": "0"}
        ):
            options = _make_options()
            apply_task_v2_env_to_options(options)
        self.assertNotIn("CLAUDE_CODE_ENABLE_TASKS", options.env)
        self.assertEqual(options.env["CLAUDE_CODE_TASK_LIST_ID"], "main")

    def test_injects_env_when_gate_on(self):
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_TASK_V2_ENABLED": "1"}
        ):
            options = _make_options()
            apply_task_v2_env_to_options(options)
        self.assertEqual(options.env["CLAUDE_CODE_ENABLE_TASKS"], "1")
        self.assertEqual(options.env["CLAUDE_CODE_TASK_LIST_ID"], "main")

    def test_lowest_priority_preserves_explicit_values(self):
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_TASK_V2_ENABLED": "true"}
        ):
            options = _make_options(
                {"CLAUDE_CODE_ENABLE_TASKS": "0", "CLAUDE_CODE_TASK_LIST_ID": "custom"}
            )
            apply_task_v2_env_to_options(options)
        self.assertEqual(options.env["CLAUDE_CODE_ENABLE_TASKS"], "0")
        self.assertEqual(options.env["CLAUDE_CODE_TASK_LIST_ID"], "custom")

    def test_task_v2_keys_not_in_dotenv_allowlist(self):
        self.assertNotIn(
            "CLAUDE_CODE_ENABLE_TASKS",
            sdk_env_module._PROJECT_DOTENV_SDK_ENV_NAMES,
        )
        self.assertNotIn(
            "CLAUDE_CODE_TASK_LIST_ID",
            sdk_env_module._PROJECT_DOTENV_SDK_ENV_NAMES,
        )


# ---------------------------------------------------------------------------
# read_task_items (claude-todo §5.1/§5.2) — ④
# ---------------------------------------------------------------------------


class TestReadTaskItems(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tasks_dir = Path(self._tmp.name).resolve() / "tasks" / "main"

    def test_derives_items_and_filters_internal_and_resolved_blockers(self):
        _write_task(
            self.tasks_dir,
            "1.json",
            {
                "id": "1",
                "subject": "设计文档",
                "status": "completed",
                "activeForm": "正在编写设计文档",
                "owner": "claude",
                "blockedBy": [],
            },
        )
        _write_task(
            self.tasks_dir,
            "2.json",
            {
                "id": "2",
                "subject": "实现捕获逻辑",
                "status": "in_progress",
                "activeForm": "正在实现捕获逻辑",
                "blockedBy": ["1", "3"],  # 1 completed → dropped; 3 kept
            },
        )
        _write_task(
            self.tasks_dir,
            "3.json",
            {"id": "3", "subject": "联调", "status": "pending"},
        )
        # Internal task filtered out.
        _write_task(
            self.tasks_dir,
            "99.json",
            {"id": "99", "subject": "internal", "status": "pending",
             "metadata": {"_internal": True}},
        )
        # Dotfiles and non-JSON ignored.
        (self.tasks_dir / ".highwatermark").write_text("99", encoding="utf-8")
        (self.tasks_dir / "notes.txt").write_text("ignore", encoding="utf-8")
        # Broken JSON skipped without aborting the whole read.
        (self.tasks_dir / "50.json").write_text("{broken", encoding="utf-8")

        items, newest_mtime = read_task_items(self.tasks_dir)

        self.assertEqual([item["id"] for item in items], ["1", "2", "3"])
        first = items[0]
        self.assertEqual(first["content"], "设计文档")
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["active_form"], "正在编写设计文档")
        self.assertEqual(first["owner"], "claude")
        self.assertEqual(first["blocked_by"], [])
        second = items[1]
        self.assertEqual(second["blocked_by"], ["3"])
        self.assertIsNotNone(newest_mtime)

    def test_empty_dir_returns_empty(self):
        self.tasks_dir.mkdir(parents=True)
        items, newest_mtime = read_task_items(self.tasks_dir)
        self.assertEqual(items, [])
        self.assertIsNone(newest_mtime)


# ---------------------------------------------------------------------------
# v1 TodoWrite SSE capture (claude-todo §5.3/§5.4) — ①⑦
# ---------------------------------------------------------------------------


class TestTodoWriteSseFrames(unittest.IsolatedAsyncioTestCase):
    def _make_cb(self, state: AgentRunState):
        queue: asyncio.Queue = asyncio.Queue()
        turn_ctx = _TurnContext(queue=queue, confirmation_store=ToolConfirmationStore())
        cb = ClaudeAgentService._make_tool_event_cb(queue, turn_ctx, state)
        return queue, turn_ctx, cb

    @staticmethod
    def _drain(queue: asyncio.Queue) -> list[dict]:
        frames = []
        while not queue.empty():
            raw = queue.get_nowait()
            assert raw.startswith("data: ") and raw.endswith("\n\n")
            frames.append(json.loads(raw[len("data: "):-2]))
        return frames

    async def test_todo_write_emits_todo_updated_not_collected(self):
        state = AgentRunState(session_id="thread-todo-sse")
        queue, turn_ctx, cb = self._make_cb(state)

        await cb(
            ToolEventPayload(
                type="tool_use",
                tool_call_id="call-todo-1",
                tool_name="TodoWrite",
                input={
                    "todos": [
                        {"content": "设计文档", "status": "completed",
                         "activeForm": "正在编写设计文档"},
                        {"content": "实现捕获逻辑", "status": "in_progress"},
                    ]
                },
            )
        )

        frames = self._drain(queue)
        todo_frames = [f for f in frames if f["type"] == "todo-updated"]
        self.assertEqual(len(todo_frames), 1)
        frame = todo_frames[0]
        self.assertEqual(frame["source"], "todo_write")
        self.assertFalse(frame["truncated"])
        self.assertTrue(frame["updatedAt"].endswith("Z"))
        todos = frame["todos"]
        self.assertEqual(len(todos), 2)
        # id = 1-based array index; content/status/activeForm direct mapping;
        # owner/blocked_by always empty for v1 (§5.2).
        self.assertEqual(
            todos[0],
            {
                "id": "1",
                "content": "设计文档",
                "status": "completed",
                "active_form": "正在编写设计文档",
                "owner": None,
                "blocked_by": [],
            },
        )
        self.assertEqual(todos[1]["id"], "2")
        self.assertIsNone(todos[1]["active_form"])
        # Memory state updated.
        self.assertEqual(state.todo_state.source, "todo_write")
        self.assertEqual(len(state.todo_state.todos), 2)
        # Lifecycle frame — never collected into collected_parts.
        self.assertNotIn(
            "todo-updated",
            {evt.get("type") for evt in turn_ctx.collected_parts},
        )

    async def test_todo_write_schema_mismatch_skips_emission(self):
        state = AgentRunState(session_id="thread-todo-bad")
        queue, turn_ctx, cb = self._make_cb(state)

        with self.assertLogs(service_module.logger, level="WARNING"):
            await cb(
                ToolEventPayload(
                    type="tool_use",
                    tool_call_id="call-todo-bad",
                    tool_name="TodoWrite",
                    input={"todos": "not-a-list"},
                )
            )

        frames = self._drain(queue)
        self.assertNotIn("todo-updated", {f["type"] for f in frames})
        # Schema mismatch: memory state is never created.
        self.assertIsNone(state.todo_state)

    async def test_tasks_changed_callback_emits_task_v2_frame(self):
        state = AgentRunState(session_id="thread-todo-v2cb")
        queue: asyncio.Queue = asyncio.Queue()
        cb = ClaudeAgentService._make_tasks_changed_cb(queue, state)

        await cb(
            [
                {
                    "id": "1",
                    "content": "设计文档",
                    "status": "pending",
                    "active_form": None,
                    "owner": None,
                    "blocked_by": [],
                }
            ]
        )

        frames = self._drain(queue)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["type"], "todo-updated")
        self.assertEqual(frames[0]["source"], "task_v2")
        self.assertEqual(len(frames[0]["todos"]), 1)
        self.assertEqual(state.todo_state.source, "task_v2")

    async def test_max_items_truncation_sets_truncated_true(self):  # ⑦
        state = AgentRunState(session_id="thread-todo-cap")
        queue: asyncio.Queue = asyncio.Queue()
        todo_state = TodoState(
            source="todo_write",
            todos=[
                {
                    "id": str(i),
                    "content": f"任务{i}",
                    "status": "pending",
                    "active_form": None,
                    "owner": None,
                    "blocked_by": [],
                }
                for i in range(1, 5)
            ],
            updated_at="2026-07-20T06:30:00.000Z",
        )
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_TODO_MAX_ITEMS": "2"}
        ):
            await service_module._emit_todo_updated(queue, todo_state)

        frames = self._drain(queue)
        self.assertEqual(len(frames), 1)
        self.assertTrue(frames[0]["truncated"])
        self.assertEqual(len(frames[0]["todos"]), 2)
        self.assertEqual(frames[0]["todos"][0]["id"], "1")


# ---------------------------------------------------------------------------
# build_thread_todos_payload (claude-todo §5.5) — ⑤⑦
# ---------------------------------------------------------------------------


class TestBuildThreadTodosPayload(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_exists_false_when_workspace_missing(self):
        payload = build_thread_todos_payload("thread-ghost")
        self.assertEqual(payload["thread_id"], "thread-ghost")
        self.assertFalse(payload["exists"])
        self.assertIsNone(payload["source"])
        self.assertEqual(payload["todos"], [])
        self.assertIsNone(payload["updated_at"])
        self.assertFalse(payload["truncated"])

    def test_memory_state_returned_when_no_task_files(self):
        (self.root / "thread-v1").mkdir()
        memory = TodoState(
            source="todo_write",
            todos=[
                {
                    "id": "1",
                    "content": "设计文档",
                    "status": "pending",
                    "active_form": None,
                    "owner": None,
                    "blocked_by": [],
                }
            ],
            updated_at="2026-07-20T06:30:00.000Z",
        )
        payload = build_thread_todos_payload("thread-v1", todo_state=memory)
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["source"], "todo_write")
        self.assertEqual(len(payload["todos"]), 1)
        self.assertEqual(payload["updated_at"], "2026-07-20T06:30:00.000Z")

    def test_filesystem_wins_and_corrects_memory_state(self):
        session_id = "thread-v2"
        tasks_dir = self.root / session_id / ".claude-home" / "tasks" / "main"
        _write_task(
            tasks_dir,
            "1.json",
            {"id": "1", "subject": "文件任务", "status": "in_progress"},
        )
        memory = TodoState(
            source="todo_write",
            todos=[{"id": "9", "content": "陈旧", "status": "pending",
                    "active_form": None, "owner": None, "blocked_by": []}],
            updated_at="2026-07-20T01:00:00.000Z",
        )
        payload = build_thread_todos_payload(session_id, todo_state=memory)
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["source"], "task_v2")
        self.assertEqual(payload["todos"][0]["content"], "文件任务")
        self.assertTrue(payload["updated_at"].endswith("Z"))
        # Memory state corrected to the filesystem truth (§5.5).
        self.assertEqual(memory.source, "task_v2")
        self.assertEqual(memory.todos[0]["content"], "文件任务")

    def test_memory_truncation_sets_truncated_true(self):  # ⑦
        (self.root / "thread-cap").mkdir()
        memory = TodoState(
            source="todo_write",
            todos=[
                {"id": str(i), "content": f"任务{i}", "status": "pending",
                 "active_form": None, "owner": None, "blocked_by": []}
                for i in range(1, 4)
            ],
            updated_at="2026-07-20T06:30:00.000Z",
        )
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_TODO_MAX_ITEMS": "2"}
        ):
            payload = build_thread_todos_payload("thread-cap", todo_state=memory)
        self.assertTrue(payload["exists"])
        self.assertTrue(payload["truncated"])
        self.assertEqual(len(payload["todos"]), 2)


# ---------------------------------------------------------------------------
# GET /api/claude-agent/threads/{thread_id}/todos (claude-todo §5.5) — ⑤
# ---------------------------------------------------------------------------


class TestThreadTodosEndpoint(unittest.IsolatedAsyncioTestCase):
    """Endpoint contract tests calling the route handler directly.

    Skipped when routers.claude_agent cannot be imported in a minimal env.
    """

    _router_module = None
    _skip_reason = None

    @classmethod
    def setUpClass(cls):
        try:
            import routers.claude_agent as router_module  # noqa: E402

            cls._router_module = router_module
        except Exception as exc:  # noqa: BLE001
            cls._skip_reason = f"routers.claude_agent not importable: {exc}"

    def setUp(self):
        if self._skip_reason:
            self.skipTest(self._skip_reason)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    async def _call(self, thread_id: str):
        return await self._router_module.claude_agent_thread_todos(
            thread_id, current_user={"user_id": 1}
        )

    async def test_404_when_thread_not_owned(self):
        with unittest.mock.patch.object(
            self._router_module.database, "get_chat_thread", return_value=None
        ):
            with self.assertRaises(self._router_module.HTTPException) as ctx:
                await self._call("thread-nope")
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_exists_false_contract(self):
        with (
            unittest.mock.patch.object(
                self._router_module.database,
                "get_chat_thread",
                return_value={"thread_id": "thread-rest"},
            ),
            unittest.mock.patch.object(
                self._router_module.claude_agent_thread_factory,
                "session_snapshot",
                return_value=None,
            ),
        ):
            payload = await self._call("thread-rest")
        self.assertEqual(payload["thread_id"], "thread-rest")
        self.assertFalse(payload["exists"])
        self.assertIsNone(payload["source"])
        self.assertEqual(payload["todos"], [])
        self.assertIsNone(payload["updated_at"])
        self.assertFalse(payload["truncated"])

    async def test_v2_filesystem_rebuild_via_endpoint(self):
        session_id = "thread-rest-v2"
        tasks_dir = self.root / session_id / ".claude-home" / "tasks" / "main"
        _write_task(
            tasks_dir,
            "1.json",
            {"id": "1", "subject": "文件任务", "status": "pending",
             "blockedBy": ["2"]},
        )
        _write_task(
            tasks_dir,
            "2.json",
            {"id": "2", "subject": "前置任务", "status": "completed"},
        )

        with (
            unittest.mock.patch.object(
                self._router_module.database,
                "get_chat_thread",
                return_value={"thread_id": session_id},
            ),
            unittest.mock.patch.object(
                self._router_module.claude_agent_thread_factory,
                "session_snapshot",
                return_value={"lifecycle": "running", "todo_state": None},
            ),
        ):
            payload = await self._call(session_id)

        self.assertTrue(payload["exists"])
        self.assertEqual(payload["source"], "task_v2")
        self.assertEqual(len(payload["todos"]), 2)
        # Resolved blocker (task 2 completed) dropped from blocked_by.
        self.assertEqual(payload["todos"][0]["blocked_by"], [])
        self.assertTrue(payload["updated_at"].endswith("Z"))


# ---------------------------------------------------------------------------
# Todo tool low-sensitivity classification (claude-todo §5.7) — ⑥
# ---------------------------------------------------------------------------


class TestTodoToolPermission(unittest.TestCase):
    _FIVE_TOOLS = ("TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet")

    def test_five_tools_in_low_sensitivity_set(self):
        for tool in self._FIVE_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, _LOW_SENSITIVITY_QUERY_TOOL_NAMES)

    def test_five_tools_get_explicit_allow_in_auto_mode(self):
        for tool in self._FIVE_TOOLS:
            with self.subTest(tool=tool):
                result = _apply_low_sensitivity_query_permission(tool, {})
                self.assertIsNotNone(result)
                specific = (result.get("hookSpecificOutput", {}) if isinstance(result, dict) else getattr(result, "hookSpecificOutput", {}))
                self.assertEqual(specific.get("hookEventName"), "PreToolUse")
                self.assertEqual(specific.get("permissionDecision"), "allow")

    def test_v2_tools_in_default_allowed_tools(self):
        for tool in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet"):
            with self.subTest(tool=tool):
                self.assertIn(tool, DEFAULT_ALLOWED_TOOLS)


if __name__ == "__main__":
    unittest.main()
