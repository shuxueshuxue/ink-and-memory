# [Input] Consume workspace.get_plans_dir, sdk_env.apply_plan_mode_env_to_options,
#         claude_agent.service plan helpers, and routers.claude_agent plan endpoint.
# [Output] Verify claude-plan backend contracts: plans-dir resolution (containment,
#          None cases), CLAUDE_CONFIG_DIR injection priority, plan-mode SSE frames
#          (not collected), REST plan endpoint contract (exists:false / 404 /
#          truncation).
# [Pos] test node in backend/tests
# [Sync] 2026-07-20: initial — claude-plan §5.1/§5.4/§5.5/§5.7 backend coverage.

"""Tests for the claude-plan backend half (Plan Mode capture & contracts).

Covers:
- ``get_plans_dir()`` primary/fallback resolution, traversal + symlink
  containment, and None cases (claude-plan §5.1).
- ``apply_plan_mode_env_to_options()`` lowest-priority CLAUDE_CONFIG_DIR
  injection (claude-plan §5.1).
- SSE ``plan-mode-changed`` / ``plan-updated`` frames: emitted on
  EnterPlanMode/ExitPlanMode tool-input-available, never collected into
  ``collected_parts`` (claude-plan §5.4).
- ``GET /api/claude-agent/threads/{thread_id}/plan``: ownership 404,
  exists:false contract, newest-file selection, truncation flag (§5.5).
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
from libs.claude_agent_kit.server import workspace as workspace_module
from libs.claude_agent_kit.server.sdk_env import apply_plan_mode_env_to_options
from libs.claude_agent_kit.server.workspace import get_plans_dir
from libs.claude_agent_kit.types import ToolEventPayload

import claude_agent.service as service_module
from claude_agent.service import (
    ClaudeAgentService,
    PlanState,
    _TurnContext,
    build_thread_plan_payload,
)
from claude_agent.thread_pool import AgentRunState
from claude_agent.tool_confirmation_store import ToolConfirmationStore


class _FakeContextBuilder:
    async def build_system_prompt(self, user_id: str, **kwargs) -> str:
        return f"system-prompt:{user_id}"

    def build_user_message(self, message_parts, **kwargs):
        return [{"type": "text", "text": "assembled"}]


def _make_options(env: dict | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(env=dict(env or {}))


# ---------------------------------------------------------------------------
# get_plans_dir (claude-plan §5.1)
# ---------------------------------------------------------------------------


class TestGetPlansDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _workspace(self, session_id: str = "thread-plan") -> Path:
        ws = self.root / session_id
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def test_primary_claude_home_plans_dir_returned(self):
        ws = self._workspace()
        primary = ws / ".claude-home" / "plans"
        primary.mkdir(parents=True)
        self.assertEqual(get_plans_dir("thread-plan"), primary.resolve())

    def test_fallback_plans_dir_probed_when_primary_missing(self):
        ws = self._workspace()
        fallback = ws / "plans"
        fallback.mkdir()
        self.assertEqual(get_plans_dir("thread-plan"), fallback.resolve())

    def test_primary_wins_over_fallback(self):
        ws = self._workspace()
        primary = ws / ".claude-home" / "plans"
        primary.mkdir(parents=True)
        (ws / "plans").mkdir()
        self.assertEqual(get_plans_dir("thread-plan"), primary.resolve())

    def test_none_when_no_plans_dir(self):
        self._workspace()
        self.assertIsNone(get_plans_dir("thread-plan"))

    def test_none_when_workspace_missing(self):
        self.assertIsNone(get_plans_dir("thread-never-ran"))

    def test_none_for_traversal_session_id(self):
        for bad in ("../escape", "a/b", "a\\b", ".."):
            with self.subTest(session_id=bad):
                self.assertIsNone(get_plans_dir(bad))

    def test_none_when_plans_dir_is_escape_symlink(self):
        ws = self._workspace()
        outside = self.root / "outside-plans"
        outside.mkdir()
        claude_home = ws / ".claude-home"
        claude_home.mkdir()
        try:
            (claude_home / "plans").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        self.assertIsNone(get_plans_dir("thread-plan"))


# ---------------------------------------------------------------------------
# apply_plan_mode_env_to_options (claude-plan §5.1)
# ---------------------------------------------------------------------------


class TestApplyPlanModeEnvToOptions(unittest.TestCase):
    def test_sets_claude_config_dir_under_cwd(self):
        options = _make_options({"ANTHROPIC_AUTH_TOKEN": "tok"})
        result = apply_plan_mode_env_to_options(options, "/tmp/ws/thread-1")
        self.assertIs(result, options)
        self.assertEqual(
            options.env["CLAUDE_CONFIG_DIR"],
            str(Path("/tmp/ws/thread-1") / ".claude-home"),
        )
        # Existing keys preserved.
        self.assertEqual(options.env["ANTHROPIC_AUTH_TOKEN"], "tok")

    def test_lowest_priority_preserves_explicit_value(self):
        options = _make_options({"CLAUDE_CONFIG_DIR": "/explicit/home"})
        apply_plan_mode_env_to_options(options, "/tmp/ws/thread-1")
        self.assertEqual(options.env["CLAUDE_CONFIG_DIR"], "/explicit/home")

    def test_noop_when_cwd_falsy(self):
        for cwd in (None, ""):
            with self.subTest(cwd=cwd):
                options = _make_options()
                apply_plan_mode_env_to_options(options, cwd)
                self.assertNotIn("CLAUDE_CONFIG_DIR", options.env)

    def test_claude_config_dir_not_in_dotenv_allowlist(self):
        self.assertNotIn(
            "CLAUDE_CONFIG_DIR",
            sdk_env_module._PROJECT_DOTENV_SDK_ENV_NAMES,
        )


# ---------------------------------------------------------------------------
# SSE plan frames (claude-plan §5.4)
# ---------------------------------------------------------------------------


class TestPlanModeSseFrames(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

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

    async def test_enter_plan_mode_emits_plan_mode_changed_not_collected(self):
        state = AgentRunState(session_id="thread-plan-sse")
        queue, turn_ctx, cb = self._make_cb(state)

        await cb(
            ToolEventPayload(
                type="tool_use",
                tool_call_id="call-enter-1",
                tool_name="EnterPlanMode",
                input={},
            )
        )

        frames = self._drain(queue)
        plan_frames = [f for f in frames if f["type"] == "plan-mode-changed"]
        self.assertEqual(len(plan_frames), 1)
        self.assertEqual(plan_frames[0]["planMode"], "planning")
        self.assertEqual(plan_frames[0]["toolCallId"], "call-enter-1")
        self.assertEqual(state.plan_state.plan_mode, "planning")
        # Lifecycle frame — never collected into collected_parts.
        self.assertNotIn(
            "plan-mode-changed",
            {evt.get("type") for evt in turn_ctx.collected_parts},
        )

    async def test_exit_plan_mode_emits_changed_and_final_plan_updated(self):
        session_id = "thread-plan-exit"
        plans_dir = self.root / session_id / ".claude-home" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "amber-churn-otter.md").write_text("# 计划\n步骤一\n", encoding="utf-8")

        state = AgentRunState(session_id=session_id)
        queue, turn_ctx, cb = self._make_cb(state)

        await cb(
            ToolEventPayload(
                type="tool_use",
                tool_call_id="call-exit-1",
                tool_name="ExitPlanMode",
                input={},
            )
        )

        frames = self._drain(queue)
        types_seen = [f["type"] for f in frames]
        self.assertIn("plan-mode-changed", types_seen)
        self.assertIn("plan-updated", types_seen)
        changed = frames[types_seen.index("plan-mode-changed")]
        self.assertEqual(changed["planMode"], "exited")
        updated = frames[types_seen.index("plan-updated")]
        self.assertEqual(updated["slug"], "amber-churn-otter")
        self.assertEqual(updated["fileName"], "amber-churn-otter.md")
        self.assertEqual(updated["content"], "# 计划\n步骤一\n")
        self.assertFalse(updated["truncated"])
        self.assertGreater(updated["contentBytes"], 0)
        self.assertTrue(updated["updatedAt"].endswith("Z"))
        self.assertEqual(state.plan_state.plan_mode, "exited")
        self.assertEqual(state.plan_state.slug, "amber-churn-otter")
        # Neither plan frame is collected into collected_parts.
        collected_types = {evt.get("type") for evt in turn_ctx.collected_parts}
        self.assertNotIn("plan-mode-changed", collected_types)
        self.assertNotIn("plan-updated", collected_types)

    async def test_exit_plan_mode_without_plans_dir_still_emits_changed(self):
        state = AgentRunState(session_id="thread-no-plans")
        queue, turn_ctx, cb = self._make_cb(state)

        await cb(
            ToolEventPayload(
                type="tool_use",
                tool_call_id="call-exit-2",
                tool_name="ExitPlanMode",
                input={},
            )
        )

        frames = self._drain(queue)
        types_seen = [f["type"] for f in frames]
        self.assertIn("plan-mode-changed", types_seen)
        self.assertNotIn("plan-updated", types_seen)
        self.assertEqual(state.plan_state.plan_mode, "exited")

    async def test_plan_file_changed_callback_emits_plan_updated(self):
        session_id = "thread-plan-cb"
        plans_dir = self.root / session_id / ".claude-home" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "brisk-dune-finch.md"
        plan_file.write_text("# Plan v1\n", encoding="utf-8")

        state = AgentRunState(session_id=session_id)
        queue: asyncio.Queue = asyncio.Queue()
        cb = ClaudeAgentService._make_plan_file_changed_cb(queue, state)

        await cb(str(plan_file))

        frames = self._drain(queue)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["type"], "plan-updated")
        self.assertEqual(frames[0]["slug"], "brisk-dune-finch")
        self.assertEqual(frames[0]["content"], "# Plan v1\n")
        self.assertEqual(state.plan_state.slug, "brisk-dune-finch")

    async def test_plan_file_changed_callback_skips_missing_file(self):
        state = AgentRunState(session_id="thread-plan-missing")
        queue: asyncio.Queue = asyncio.Queue()
        cb = ClaudeAgentService._make_plan_file_changed_cb(queue, state)

        with self.assertLogs(service_module.logger, level="WARNING"):
            await cb(str(self.root / "does-not-exist.md"))
        self.assertTrue(queue.empty())


# ---------------------------------------------------------------------------
# build_thread_plan_payload (claude-plan §5.5)
# ---------------------------------------------------------------------------


class TestBuildThreadPlanPayload(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self._env = unittest.mock.patch.dict(
            os.environ, {"AGENT_CWD": str(self.root)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _write_plan(self, session_id: str, name: str, body: bytes, mtime: float) -> Path:
        plans_dir = self.root / session_id / ".claude-home" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        path = plans_dir / name
        path.write_bytes(body)
        os.utime(path, (mtime, mtime))
        return path

    def test_exists_false_when_workspace_missing(self):
        payload = build_thread_plan_payload("thread-ghost", plan_mode="planning")
        self.assertEqual(payload["thread_id"], "thread-ghost")
        self.assertFalse(payload["exists"])
        # Workspace disabled/missing → fixed plan_mode "none".
        self.assertEqual(payload["plan_mode"], "none")
        self.assertIsNone(payload["slug"])
        self.assertIsNone(payload["file_name"])
        self.assertIsNone(payload["content"])
        self.assertIsNone(payload["content_bytes"])
        self.assertIsNone(payload["updated_at"])
        self.assertFalse(payload["truncated"])

    def test_exists_false_keeps_memory_plan_mode_when_workspace_exists(self):
        (self.root / "thread-idle").mkdir()
        payload = build_thread_plan_payload("thread-idle", plan_mode="planning")
        self.assertFalse(payload["exists"])
        self.assertEqual(payload["plan_mode"], "planning")

    def test_newest_md_file_wins(self):
        session_id = "thread-multi"
        self._write_plan(session_id, "old-plan.md", b"old", mtime=1000.0)
        self._write_plan(session_id, "new-plan.md", b"# newest\n", mtime=2000.0)
        # Non-markdown files are ignored.
        self._write_plan(session_id, "notes.txt", b"ignore me", mtime=3000.0)

        payload = build_thread_plan_payload(session_id, plan_mode="exited")
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["slug"], "new-plan")
        self.assertEqual(payload["file_name"], "new-plan.md")
        self.assertEqual(payload["content"], "# newest\n")
        self.assertEqual(payload["content_bytes"], len(b"# newest\n"))
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["plan_mode"], "exited")
        self.assertTrue(payload["updated_at"].endswith("Z"))

    def test_truncated_flag_when_over_cap(self):
        session_id = "thread-big"
        body = b"x" * 100
        self._write_plan(session_id, "big-plan.md", body, mtime=1000.0)
        with unittest.mock.patch.dict(
            os.environ, {"INK_AGENT_PLAN_MAX_CONTENT_BYTES": "16"}
        ):
            payload = build_thread_plan_payload(session_id)
        self.assertTrue(payload["exists"])
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["content"], "x" * 16)
        # contentBytes reports the full on-disk size.
        self.assertEqual(payload["content_bytes"], 100)


# ---------------------------------------------------------------------------
# GET /api/claude-agent/threads/{thread_id}/plan (claude-plan §5.5)
# ---------------------------------------------------------------------------


class TestThreadPlanEndpoint(unittest.IsolatedAsyncioTestCase):
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
        return await self._router_module.claude_agent_thread_plan(
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
        self.assertEqual(payload["plan_mode"], "none")
        self.assertIsNone(payload["slug"])
        self.assertIsNone(payload["file_name"])
        self.assertIsNone(payload["content"])
        self.assertIsNone(payload["content_bytes"])
        self.assertIsNone(payload["updated_at"])

    async def test_running_thread_plan_from_workspace(self):
        session_id = "thread-running"
        plans_dir = self.root / session_id / ".claude-home" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "amber-churn-otter.md").write_text(
            "# 计划\n第一步\n", encoding="utf-8"
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
                return_value={"lifecycle": "running", "plan_mode": "planning"},
            ),
        ):
            payload = await self._call(session_id)

        self.assertTrue(payload["exists"])
        self.assertEqual(payload["plan_mode"], "planning")
        self.assertEqual(payload["slug"], "amber-churn-otter")
        self.assertEqual(payload["file_name"], "amber-churn-otter.md")
        self.assertEqual(payload["content"], "# 计划\n第一步\n")
        self.assertFalse(payload["truncated"])
        self.assertGreater(payload["content_bytes"], 0)
        self.assertTrue(payload["updated_at"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
