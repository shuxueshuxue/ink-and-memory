# [Input] Consume ClaudeAgentThreadFactory, AgentRunStatePool, AgentRunLifecycle,
#         ClaudeAgentRunRequest from backend/claude_agent/.
# [Output] Verify Phase 2 runner flyweight cache, TTL eviction, close_thread,
#          observer hooks, Phase 1/4 extrinsic/intrinsic state contracts,
#          per-session lock serialisation.
# [Pos] test node in backend/tests
# [Sync] 2026-05-22: migrated from Pawkeyland scripts/test_claude_agent_thread_factory.py.
#                    Removed: pet/persona/mem0/IdentityService stubs.
#                    ENV: PAWKEYLAND_RUNNER_TTL_S → INK_AGENT_TTL_S.
# [Sync] 2026-06-06: align session_id expectations with current thread_id
#                    strategy and ClaudeAgentRunRequest.message_parts.
# [Sync] 2026-06-25: cover frontend stop flow cancelling a running background turn.

"""Unit tests for ClaudeAgentThreadFactory.

Stubs out ClaudeAgentService and ClaudeAgentRunner so the SDK runtime is
never invoked during unit testing.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
import unittest
import unittest.mock
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub claude_agent_sdk before libs.claude_agent_kit

# Additional stubs already handled by _sdk_stubs; this comment left for clarity.
if "claude_agent_sdk" not in sys.modules:
    _sdk_stub = types.ModuleType("claude_agent_sdk")
    sys.modules["claude_agent_sdk"] = _sdk_stub
    sys.modules["claude_agent_sdk.types"] = types.ModuleType("claude_agent_sdk.types")

from claude_agent.thread_factory import ClaudeAgentThreadFactory, build_session_id
from claude_agent.thread_pool import (
    AgentRunLifecycle,
    AgentRunState,
    AgentRunStatePool,
    AgentRunStateSweeper,
)
from claude_agent.service import ClaudeAgentRunRequest, ClaudeAgentService
from claude_agent.observer import LoggingObserver, SessionObserverRegistry


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


def _make_request(user_id: str = "user_1", message: str = "hello", thread_id: Optional[str] = None) -> ClaudeAgentRunRequest:
    return ClaudeAgentRunRequest(
        user_id=user_id,
        thread_id=thread_id or f"thread_{user_id}",
        message_parts=[{"type": "text", "text": message}],
    )


def _make_factory() -> ClaudeAgentThreadFactory:
    """Return a factory with Service and Runner stubbed out."""
    factory = ClaudeAgentThreadFactory()
    return factory


# ---------------------------------------------------------------------------
# build_session_id
# ---------------------------------------------------------------------------

class TestBuildSessionId(unittest.TestCase):
    def test_returns_thread_id(self):
        req = _make_request(user_id="alice", thread_id="thread_alice")
        self.assertEqual(build_session_id(req), "thread_alice")

    def test_rejects_slash_in_thread_id(self):
        req = _make_request(thread_id="a/b")
        with self.assertRaises(ValueError):
            build_session_id(req)

    def test_rejects_double_dot_in_thread_id(self):
        req = _make_request(thread_id="..evil")
        with self.assertRaises(ValueError):
            build_session_id(req)

    def test_different_threads_get_different_ids(self):
        r1 = _make_request(user_id="alice", thread_id="thread_alice")
        r2 = _make_request(user_id="alice", thread_id="thread_bob")
        self.assertNotEqual(build_session_id(r1), build_session_id(r2))


# ---------------------------------------------------------------------------
# AgentRunStatePool — basic
# ---------------------------------------------------------------------------

class TestAgentRunStatePool(unittest.TestCase):
    def setUp(self):
        self.pool = AgentRunStatePool()

    def test_get_or_create_returns_new_state(self):
        state = self.pool.get_or_create("u1")
        self.assertIsInstance(state, AgentRunState)
        self.assertEqual(state.session_id, "u1")

    def test_get_or_create_returns_same_state_on_repeat(self):
        s1 = self.pool.get_or_create("u1")
        s2 = self.pool.get_or_create("u1")
        self.assertIs(s1, s2)

    def test_different_sessions_are_isolated(self):
        s1 = self.pool.get_or_create("u1")
        s2 = self.pool.get_or_create("u2")
        self.assertIsNot(s1, s2)

    def test_destroy_marks_state_destroyed(self):
        self.pool.get_or_create("u1")
        self.pool.destroy("u1")
        state = self.pool._states["u1"]
        self.assertEqual(state.lifecycle, AgentRunLifecycle.DESTROYED)

    def test_get_returns_none_for_destroyed(self):
        self.pool.get_or_create("u1")
        self.pool.destroy("u1")
        self.assertIsNone(self.pool.get("u1"))

    def test_get_or_create_rebuilds_after_destroy(self):
        self.pool.get_or_create("u1").mark_running()
        self.pool.destroy("u1")
        new_state = self.pool.get_or_create("u1")
        self.assertEqual(new_state.lifecycle, AgentRunLifecycle.IDLE)

    def test_each_session_gets_own_lock(self):
        lock1 = self.pool.get_lock("u1")
        lock2 = self.pool.get_lock("u2")
        self.assertIsNot(lock1, lock2)

    def test_same_session_always_gets_same_lock(self):
        lock1 = self.pool.get_lock("u1")
        lock2 = self.pool.get_lock("u1")
        self.assertIs(lock1, lock2)

    def test_destroy_all_destroys_all(self):
        self.pool.get_or_create("u1")
        self.pool.get_or_create("u2")
        destroyed = self.pool.destroy_all()
        self.assertCountEqual(destroyed, ["u1", "u2"])

    def test_snapshot_session_returns_dict(self):
        state = self.pool.get_or_create("u1")
        state.is_context_initialized = True
        snap = self.pool.snapshot_session("u1")
        self.assertIsInstance(snap, dict)
        self.assertEqual(snap["session_id"], "u1")
        self.assertTrue(snap["context_initialized"])

    def test_snapshot_session_returns_none_for_unknown(self):
        self.assertIsNone(self.pool.snapshot_session("unknown"))


# ---------------------------------------------------------------------------
# AgentRunState — lifecycle transitions
# ---------------------------------------------------------------------------

class TestAgentRunState(unittest.TestCase):
    def _state(self, sid="s1"):
        return AgentRunState(session_id=sid)

    def test_initial_lifecycle_is_idle(self):
        self.assertEqual(self._state().lifecycle, AgentRunLifecycle.IDLE)

    def test_mark_running_transitions_to_running(self):
        s = self._state()
        s.mark_running()
        self.assertEqual(s.lifecycle, AgentRunLifecycle.RUNNING)

    def test_mark_idle_from_running_increments_turn_count(self):
        s = self._state()
        s.mark_running()
        s.mark_idle()
        self.assertEqual(s.turn_count, 1)
        self.assertEqual(s.lifecycle, AgentRunLifecycle.IDLE)

    def test_mark_destroyed_clears_runner(self):
        s = self._state()
        s.runner = object()
        s.mark_destroyed()
        self.assertIsNone(s.runner)
        self.assertEqual(s.lifecycle, AgentRunLifecycle.DESTROYED)

    def test_cannot_mark_destroyed_state_running(self):
        s = self._state()
        s.mark_destroyed()
        with self.assertRaises(RuntimeError):
            s.mark_running()

    def test_is_expired_false_for_fresh_state(self):
        s = self._state()
        self.assertFalse(s.is_expired)

    def test_is_expired_true_when_idle_beyond_ttl(self):
        s = self._state()
        s._last_active_ts = time.monotonic() - 700  # > default 600s TTL
        self.assertTrue(s.is_expired)

    def test_is_expired_false_while_running(self):
        s = self._state()
        s.mark_running()
        s._last_active_ts = time.monotonic() - 700
        self.assertFalse(s.is_expired)  # only IDLE states expire

    def test_snapshot_contains_required_keys(self):
        s = self._state()
        snap = s.snapshot()
        for key in ("session_id", "lifecycle", "turn_count", "idle_seconds",
                    "remaining_seconds", "ttl_seconds", "runner_present",
                    "context_initialized"):
            self.assertIn(key, snap)

    def test_with_system_prompt_sets_field(self):
        s = self._state()
        s.with_system_prompt("You are a writer's assistant.")
        self.assertEqual(s.system_prompt, "You are a writer's assistant.")

    def test_with_runner_sets_field(self):
        s = self._state()
        sentinel = object()
        s.with_runner(sentinel)
        self.assertIs(s.runner, sentinel)


# ---------------------------------------------------------------------------
# AgentRunStateSweeper — TTL eviction
# ---------------------------------------------------------------------------

class TestAgentRunStateSweeper(unittest.TestCase):
    def setUp(self):
        self.pool = AgentRunStatePool()
        self.evicted_calls: list = []
        async def _on_evicted(sids, reason):
            self.evicted_calls.append((sids, reason))
        self.sweeper = AgentRunStateSweeper(self.pool, interval_s=9999, on_evicted=_on_evicted)

    def _expire(self, sid: str):
        state = self.pool.get_or_create(sid)
        state._last_active_ts = time.monotonic() - 700

    def test_sweep_once_evicts_expired_sessions(self):
        self._expire("u1")
        self.pool.get_or_create("u2")  # fresh — not expired
        evicted = _run(self.sweeper.sweep_once())
        self.assertIn("u1", evicted)
        self.assertNotIn("u2", evicted)

    def test_sweep_once_fires_callback(self):
        self._expire("u1")
        _run(self.sweeper.sweep_once())
        self.assertEqual(len(self.evicted_calls), 1)
        self.assertEqual(self.evicted_calls[0][1], "ttl_expired")

    def test_sweep_skips_locked_sessions(self):
        self._expire("u1")
        lock = self.pool.get_lock("u1")

        async def _hold_and_sweep():
            async with lock:
                return await self.sweeper.sweep_once()

        evicted = _run(_hold_and_sweep())
        self.assertNotIn("u1", evicted)

    def test_sweep_stats_contains_expected_keys(self):
        stats = self.sweeper.sweep_stats()
        self.assertIn("ttl_seconds", stats)
        self.assertIn("sweep_interval_seconds", stats)
        self.assertIn("active_sessions", stats)

    def test_stop_does_not_raise_when_not_started(self):
        _run(self.sweeper.stop())  # should not raise


# ---------------------------------------------------------------------------
# ClaudeAgentThreadFactory — runner flyweight (Phase 2)
# ---------------------------------------------------------------------------

class TestFactoryRunnerFlyweight(unittest.TestCase):
    """Runner is created once per session_id and reused across turns."""

    def setUp(self):
        self.factory = ClaudeAgentThreadFactory()
        # Stub service to avoid real SDK calls
        self._patch_service()

    def _patch_service(self):
        """Replace service methods with stubs that emit a minimal SSE stream."""
        async def _assemble(req, *, state, bus, runner):
            from claude_agent.event_bus import BusProxyQueue
            from claude_agent.service import _TurnExecution, _TurnContext
            from libs.claude_agent_kit.types import AgentRunOptions
            state.is_context_initialized = True
            state.system_prompt = "stub"
            text_parts = [
                part.get("text", "")
                for part in (req.message_parts or [])
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            opts = AgentRunOptions(thread_id=state.session_id, user_message="".join(text_parts))
            turn_ctx = _TurnContext(
                queue=BusProxyQueue(bus),
                confirmation_store=unittest.mock.MagicMock(),
            )
            state.turn_context = turn_ctx
            return _TurnExecution(
                request=req, state=state, runner=runner,
                run_options=opts, turn_context=turn_ctx,
            )

        async def _execute(execution):
            await execution.turn_context.queue.put('data: {"type":"finish","reason":"success"}\n\n')
            await execution.turn_context.queue.put(None)

        self.factory._service.assemble_context = _assemble
        self.factory._service.execute_session = _execute

        # Stub ClaudeAgentRunner to avoid real SDK
        self._runner_instances: list = []
        factory = self.factory

        class _FakeRunner:
            # Original ClaudeAgentRunner.__init__ takes optional sdk_client only
            def __init__(self, sdk_client=None):
                self.session_id = None  # set after creation in factory
                factory._test_runner_instances = getattr(factory, "_test_runner_instances", [])
                factory._test_runner_instances.append(self)

        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", _FakeRunner):
            self._FakeRunner = _FakeRunner

    def _drain(self, req: ClaudeAgentRunRequest) -> list[str]:
        async def _collect():
            frames = []
            async for frame in self.factory.run_streaming(req):
                frames.append(frame)
            return frames
        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
            return _run(_collect())

    def test_runner_created_on_first_turn(self):
        req = _make_request("user_runner_1")
        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
            _run(self._collect_gen(req))
        self.assertEqual(len(getattr(self.factory, "_test_runner_instances", [])), 1)

    def test_runner_reused_on_second_turn(self):
        req = _make_request("user_runner_2")
        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
            _run(self._collect_gen(req))
            _run(self._collect_gen(req))
        instances = getattr(self.factory, "_test_runner_instances", [])
        self.assertEqual(len(instances), 1, "Runner should be created only once within TTL")

    async def _collect_gen(self, req):
        async for _ in self.factory.run_streaming(req):
            pass

    def test_different_sessions_get_different_runners(self):
        req1 = _make_request("user_a")
        req2 = _make_request("user_b")
        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
            _run(self._collect_gen(req1))
            _run(self._collect_gen(req2))
        instances = getattr(self.factory, "_test_runner_instances", [])
        self.assertEqual(len(instances), 2)
        # Different runner instances (by identity) for different sessions
        self.assertIsNot(instances[0], instances[1])

    def test_close_thread_destroys_session(self):
        req = _make_request("user_close", thread_id="thread_close")

        async def _run_and_close():
            with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
                await self._collect_gen(req)
            self.factory.close_thread("thread_close")

        _run(_run_and_close())
        state = self.factory._pool._states.get("thread_close")
        self.assertEqual(state.lifecycle, AgentRunLifecycle.DESTROYED)

    def test_session_snapshot_returns_dict(self):
        req = _make_request("user_snap", thread_id="thread_snap")
        with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
            _run(self._collect_gen(req))
        snap = self.factory.session_snapshot("thread_snap")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["session_id"], "thread_snap")

    def test_session_snapshot_none_for_unknown(self):
        self.assertIsNone(self.factory.session_snapshot("nonexistent"))

    def test_stop_thread_cancels_running_turn(self):
        req = _make_request("user_stop", thread_id="thread_stop")

        async def _execute_until_cancel(execution):
            await execution.turn_context.queue.put(
                'data: {"type":"text-start","id":"text-0"}\n\n'
            )
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await execution.turn_context.queue.put(
                    'data: {"type":"finish","finishReason":"stop"}\n\n'
                )
                await execution.turn_context.queue.put(None)
                raise

        async def _scenario():
            self.factory._service.execute_session = _execute_until_cancel
            frames: list[str] = []

            with unittest.mock.patch("claude_agent.thread_factory.ClaudeAgentRunner", self._FakeRunner):
                consumer = asyncio.create_task(self._collect_frames(req, frames))
                for _ in range(100):
                    snapshot = self.factory.session_snapshot("thread_stop")
                    if snapshot and snapshot.get("lifecycle") == "running":
                        break
                    await asyncio.sleep(0.01)

                result = await self.factory.stop_thread("thread_stop")
                await asyncio.wait_for(consumer, timeout=1.0)
                return result, frames, self.factory.session_snapshot("thread_stop")

        result, frames, snapshot = _run(_scenario())

        self.assertTrue(result["stop_requested"])
        self.assertFalse(result["running"])
        self.assertEqual(result["lifecycle"], "idle")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["lifecycle"], "idle")
        self.assertTrue(any('"finishReason":"stop"' in frame for frame in frames))

    async def _collect_frames(self, req, frames):
        async for frame in self.factory.run_streaming(req):
            frames.append(frame)


# ---------------------------------------------------------------------------
# Observer registration
# ---------------------------------------------------------------------------

class TestObserverRegistration(unittest.TestCase):
    def test_register_and_unregister(self):
        factory = ClaudeAgentThreadFactory()
        obs = LoggingObserver()
        factory.register_observer(obs)
        factory.unregister_observer(obs)
        # No error = pass

    def test_logging_observer_registered_by_default(self):
        factory = ClaudeAgentThreadFactory()
        observers = factory._observers._observers
        self.assertTrue(
            any(isinstance(o, LoggingObserver) for o in observers),
            "LoggingObserver should be registered at factory creation",
        )


# ---------------------------------------------------------------------------
# Factory aclose
# ---------------------------------------------------------------------------

class TestFactoryAclose(unittest.TestCase):
    def test_aclose_destroys_all_sessions(self):
        factory = ClaudeAgentThreadFactory()
        factory._pool.get_or_create("u1")
        factory._pool.get_or_create("u2")
        _run(factory.aclose())
        for sid in ("u1", "u2"):
            state = factory._pool._states.get(sid)
            self.assertEqual(state.lifecycle, AgentRunLifecycle.DESTROYED)


if __name__ == "__main__":
    unittest.main()
