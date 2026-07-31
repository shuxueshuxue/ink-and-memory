# [Input] Consume AgentRunOptions, AgentStreamingCallbacks from libs/claude_agent_kit/types.py.
# [Output] Provide AgentRunLifecycle, AgentRunState, AgentRunStatePool,
#          AgentRunStateSweeper to ClaudeAgentThreadFactory.
# [Pos] flyweight-state node in backend/claude_agent
# [Sync] 2026-05-22: migration from Pawkeyland application/claude_agent/thread_pool.py.
#                    Removed pet/persona/mem0/resolved_identity intrinsic fields.
#                    Renamed env prefix PAWKEYLAND_* → INK_AGENT_*.
#                    Inlined state_builder (was 111 lines) into AgentRunState.
# [Sync] 2026-05-29: add editor_state (soft-cached EditorState dict) and editor_user_id
#                    to AgentRunState intrinsic state so the session flyweight survives
#                    across turns and MCP write-tool results can refresh in-place.
#                    Added with_editor_state() builder helper.
# [Sync] 2026-06-09: add event_bus (IEventBus), current_turn_id (str), bg_task (asyncio.Task)
#                    extrinsic fields to AgentRunState for EventBus reconnect support.
#                    mark_destroyed now cancels bg_task and clears event_bus.
# [Sync] 2026-06-22: track the Settings SYSTEM_PROMPT value used to build cached
#                    system_prompt so Phase 1 can rebuild when page configuration
#                    changes during a live Thread Session.
# [Sync] 2026-07-20: add plan_state (claude-plan §5.2 PlanState, memory-only) to
#                    AgentRunState intrinsic state; snapshot() exposes plan_mode
#                    for the GET /threads/{id}/plan endpoint.
# [Sync] 2026-07-20: add todo_state (claude-todo §5.2 TodoState, memory-only) to
#                    AgentRunState intrinsic state; snapshot() exposes the live
#                    object for the GET /threads/{id}/todos endpoint.

"""Claude Agent Thread Session Pool.

Implements the **Flyweight + State** pattern for cross-turn session management.

``AgentRunLifecycle``
    Three states: ``IDLE``, ``RUNNING``, ``DESTROYED``.

``AgentRunState``
    Flyweight body with intrinsic state (session_id, cwd, system_prompt, runner,
    system_config_system_prompt, is_context_initialized) cached across turns,
    and extrinsic state (user_message, callbacks, run_options, turn_context)
    refreshed each turn.

``AgentRunStatePool``
    In-process registry keyed by session_id.  Each session gets one
    ``asyncio.Lock`` that serializes concurrent ``run_streaming`` calls.

``AgentRunStateSweeper``
    Background task that periodically evicts expired sessions.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import uuid4

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from libs.claude_agent_kit.types import AgentRunOptions, AgentStreamingCallbacks
    from libs.claude_agent_kit.server.agent_runner import ClaudeAgentRunner
    from claude_agent.event_bus import IEventBus


# ---------------------------------------------------------------------------
# TTL constants (configurable via env)
# ---------------------------------------------------------------------------


def _runner_ttl_seconds() -> int:
    try:
        return max(1, int(os.getenv("INK_AGENT_TTL_S", "600") or "600"))
    except (ValueError, TypeError):
        return 600


def _runner_sweep_interval_seconds() -> float:
    try:
        raw = os.getenv("INK_AGENT_SWEEP_INTERVAL_S", "60") or "60"
        return max(1.0, float(raw))
    except (ValueError, TypeError):
        return 60.0


_RUNNER_TTL_SECONDS: int = _runner_ttl_seconds()
_RUNNER_SWEEP_INTERVAL_SECONDS: float = _runner_sweep_interval_seconds()


# ---------------------------------------------------------------------------
# Safety helper
# ---------------------------------------------------------------------------


def _validate_session_id(session_id: str) -> None:
    """Reject session identifiers that could escape the workspace root."""
    for bad in ("/", "\\", ".."):
        if bad in session_id:
            raise ValueError(
                f"session_id must not contain {bad!r}: {session_id!r}"
            )


# ---------------------------------------------------------------------------
# Lifecycle enum
# ---------------------------------------------------------------------------


class AgentRunLifecycle(str, Enum):
    """Lifecycle states for a Thread Session flyweight.

    Valid transitions::

        IDLE  →  RUNNING   (Factory acquires lock before calling runner)
        RUNNING  →  IDLE   (runner completes; turn_count incremented)
        IDLE  →  DESTROYED  (Factory.close_thread / TTL eviction)
        RUNNING  →  DESTROYED  (abnormal abort)
    """

    IDLE = "idle"
    RUNNING = "running"
    DESTROYED = "destroyed"


# ---------------------------------------------------------------------------
# Flyweight body
# ---------------------------------------------------------------------------


@dataclass
class AgentRunState:
    """Per-session flyweight combining Flyweight and State patterns.

    **Intrinsic state** (set once per session, reused across turns):
        session_id, cwd, system_prompt, system_config_system_prompt,
        is_context_initialized, runner.

    **Extrinsic state** (refreshed every turn by the Factory):
        user_message, callbacks, run_options, turn_context.

    **Lifecycle state**: lifecycle, turn_count, _last_active_ts.
    """

    # ------------------------------------------------------------------
    # Intrinsic state
    # ------------------------------------------------------------------
    session_id: str
    cwd: str = ""
    system_prompt: str = ""
    system_config_system_prompt: str = ""
    is_context_initialized: bool = False
    runner: Optional[Any] = field(default=None, repr=False)
    # Soft-cached EditorState dict.  Updated by assemble_context on each turn
    # that carries an editor_state snapshot, and refreshed in-place by the
    # tool-event callback after a confirmed MCP write-tool result.
    # None means no editor context has been established yet for this session.
    editor_state: Optional[Any] = field(default=None, repr=False)
    # DB user_id needed to reload editor_state after write-tool execution.
    editor_user_id: int = 0
    # In-memory Plan Mode state (claude-plan §5.2 PlanState from service.py;
    # typed Any to avoid a circular import).  Memory-only — the workspace
    # plans directory is the sole persistent layer.  None until the first
    # plan-mode transition or plan-file write of this session.
    plan_state: Optional[Any] = field(default=None, repr=False)
    # In-memory todo list state (claude-todo §5.2 TodoState from service.py;
    # typed Any to avoid a circular import).  Memory-only — v2 rebuilds from
    # the workspace tasks directory, v1 has no persistent layer.  None until
    # the first TodoWrite / TaskCreate / TaskUpdate of this session.
    todo_state: Optional[Any] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Extrinsic state (refreshed each turn)
    # ------------------------------------------------------------------
    user_message: str = ""
    callbacks: Optional[Any] = field(default=None, repr=False)
    run_options: Optional[Any] = field(default=None, repr=False)
    turn_context: Optional[Any] = field(default=None, repr=False)
    # EventBus for the current turn — set at Phase 3 start, cleared on mark_idle.
    # Type is IEventBus but imported lazily to avoid circular imports.
    event_bus: Optional[Any] = field(default=None, repr=False)
    # Stable ID for the current inference turn (used as Redis Stream key suffix).
    current_turn_id: str = field(default_factory=lambda: str(uuid4()), repr=False)
    # Background asyncio.Task running execute_session for this turn.
    # Used by close_thread to cancel in-flight inference.
    bg_task: Optional[Any] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Lifecycle state
    # ------------------------------------------------------------------
    lifecycle: AgentRunLifecycle = AgentRunLifecycle.IDLE
    turn_count: int = 0
    _last_active_ts: float = field(default_factory=time.monotonic, repr=False)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def mark_running(self) -> None:
        if self.lifecycle == AgentRunLifecycle.DESTROYED:
            raise RuntimeError(f"Cannot mark DESTROYED session {self.session_id!r} as RUNNING")
        self.lifecycle = AgentRunLifecycle.RUNNING
        self._last_active_ts = time.monotonic()

    def mark_idle(self) -> None:
        if self.lifecycle == AgentRunLifecycle.RUNNING:
            self.turn_count += 1
        self.lifecycle = AgentRunLifecycle.IDLE
        self._last_active_ts = time.monotonic()

    def mark_destroyed(self) -> None:
        self.lifecycle = AgentRunLifecycle.DESTROYED
        self.runner = None
        self.turn_context = None
        self.callbacks = None
        self.run_options = None
        self.event_bus = None
        self.plan_state = None
        self.todo_state = None
        bg_task = self.bg_task
        self.bg_task = None
        if bg_task is not None and not bg_task.done():
            bg_task.cancel()

    def touch(self) -> None:
        """Refresh the keepalive timestamp without changing lifecycle state."""
        self._last_active_ts = time.monotonic()

    # ------------------------------------------------------------------
    # Read-only derived properties
    # ------------------------------------------------------------------

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_active_ts

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, _RUNNER_TTL_SECONDS - self.idle_seconds)

    @property
    def is_expired(self) -> bool:
        return (
            self.lifecycle == AgentRunLifecycle.IDLE
            and self.idle_seconds >= _RUNNER_TTL_SECONDS
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return a read-only diagnostic dict for the HTTP session-status endpoint."""
        return {
            "session_id": self.session_id,
            "lifecycle": self.lifecycle.value,
            "turn_count": self.turn_count,
            "idle_seconds": round(self.idle_seconds, 1),
            "remaining_seconds": round(self.remaining_seconds, 1),
            "ttl_seconds": _RUNNER_TTL_SECONDS,
            "runner_present": self.runner is not None,
            "context_initialized": self.is_context_initialized,
            "plan_mode": (
                self.plan_state.plan_mode if self.plan_state is not None else "none"
            ),
            # Live TodoState object for the GET /threads/{id}/todos endpoint
            # (internal consumer only; not a JSON-diagnostic field).
            "todo_state": self.todo_state,
        }

    # ------------------------------------------------------------------
    # Inlined AgentRunStateBuilder helpers
    # ------------------------------------------------------------------

    def with_system_prompt(
        self,
        system_prompt: str,
        *,
        system_config_system_prompt: str = "",
    ) -> "AgentRunState":
        self.system_prompt = system_prompt
        self.system_config_system_prompt = system_config_system_prompt
        return self

    def with_cwd(self, cwd: str) -> "AgentRunState":
        self.cwd = cwd
        return self

    def with_runner(self, runner: Any) -> "AgentRunState":
        self.runner = runner
        return self

    def with_editor_state(self, editor_state: Optional[Any], user_id: int) -> "AgentRunState":
        """Update the soft-cached editor state.

        Only overwrites when *editor_state* is not None so that pure-chat turns
        (editor_state=None) don't erase a previously established document context.
        *user_id* is always stored so DB-reload calls in the write-tool callback
        can reference the correct user row.
        """
        if editor_state is not None:
            self.editor_state = editor_state
        self.editor_user_id = user_id
        return self


# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------


class AgentRunStatePool:
    """In-process registry of AgentRunState flyweights keyed by session_id.

    Each session gets one ``asyncio.Lock`` that serializes concurrent
    ``run_streaming`` calls (single-consumer guarantee).
    """

    def __init__(self) -> None:
        self._states: Dict[str, AgentRunState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._order: deque[str] = deque()

    def get_or_create(self, session_id: str) -> AgentRunState:
        """Return existing state or create a fresh IDLE state."""
        _validate_session_id(session_id)
        if session_id not in self._states:
            self._states[session_id] = AgentRunState(session_id=session_id)
            self._locks[session_id] = asyncio.Lock()
            self._order.append(session_id)
        state = self._states[session_id]
        if state.lifecycle == AgentRunLifecycle.DESTROYED:
            new_state = AgentRunState(session_id=session_id)
            self._states[session_id] = new_state
            return new_state
        return state

    def get(self, session_id: str) -> Optional[AgentRunState]:
        """Return state if it exists and is not DESTROYED, else None."""
        state = self._states.get(session_id)
        if state is None or state.lifecycle == AgentRunLifecycle.DESTROYED:
            return None
        return state

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def destroy(self, session_id: str) -> Optional[AgentRunState]:
        """Mark a session as DESTROYED and return it (or None if not found)."""
        state = self._states.get(session_id)
        if state is None:
            return None
        state.mark_destroyed()
        return state

    def evict_expired(
        self,
        *,
        reason: str = "ttl_expired",
        on_evicted: Optional[Callable[[list[str], str], Awaitable[None]]] = None,
    ) -> list[str]:
        """Evict all IDLE sessions whose TTL has elapsed.

        Skips sessions whose per-session lock is currently held to avoid racing
        with in-flight Phase 1 work.

        Returns the list of evicted session_ids.
        """
        evicted: list[str] = []
        for sid, state in list(self._states.items()):
            if state.lifecycle != AgentRunLifecycle.IDLE:
                continue
            if not state.is_expired:
                continue
            lock = self._locks.get(sid)
            if lock is not None and lock.locked():
                logger.debug("Skipping eviction of locked session %s", sid)
                continue
            state.mark_destroyed()
            evicted.append(sid)
        return evicted

    def snapshot_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        state = self.get(session_id)
        return state.snapshot() if state else None

    def snapshot_all(self) -> list[Dict[str, Any]]:
        return [s.snapshot() for s in self._states.values()]

    def list_session_ids(self) -> list[str]:
        return [
            sid
            for sid, s in self._states.items()
            if s.lifecycle != AgentRunLifecycle.DESTROYED
        ]

    def destroy_all(self) -> list[str]:
        """Destroy all sessions (called during factory shutdown)."""
        destroyed = []
        for sid, state in self._states.items():
            if state.lifecycle != AgentRunLifecycle.DESTROYED:
                state.mark_destroyed()
                destroyed.append(sid)
        return destroyed


# ---------------------------------------------------------------------------
# Sweeper
# ---------------------------------------------------------------------------


class AgentRunStateSweeper:
    """Background asyncio task that periodically evicts expired sessions.

    Eviction fires the ``on_evicted(session_ids, reason)`` callback so the
    Factory can relay Phase 4 (Session End) observer hooks at the real State
    destruction boundary.
    """

    def __init__(
        self,
        pool: AgentRunStatePool,
        *,
        interval_s: float = _RUNNER_SWEEP_INTERVAL_SECONDS,
        on_evicted: Optional[Callable[[list[str], str], Awaitable[None]]] = None,
    ) -> None:
        self._pool = pool
        self._interval_s = interval_s
        self._on_evicted = on_evicted
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="agent-run-sweeper")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def sweep_once(self) -> list[str]:
        """Run one eviction pass and fire the callback if sessions were evicted."""
        evicted = self._pool.evict_expired(reason="ttl_expired")
        if evicted and self._on_evicted:
            try:
                await self._on_evicted(evicted, "ttl_expired")
            except Exception:  # noqa: BLE001
                logger.exception("on_evicted callback raised in AgentRunStateSweeper")
        return evicted

    def sweep_stats(self) -> Dict[str, Any]:
        return {
            "ttl_seconds": _RUNNER_TTL_SECONDS,
            "sweep_interval_seconds": self._interval_s,
            "active_sessions": len(self._pool.list_session_ids()),
        }

    async def _run(self) -> None:
        logger.debug(
            "AgentRunStateSweeper started: interval=%.0fs ttl=%ds",
            self._interval_s,
            _RUNNER_TTL_SECONDS,
        )
        while True:
            try:
                await asyncio.sleep(self._interval_s)
                evicted = await self.sweep_once()
                if evicted:
                    logger.info(
                        "Sweeper evicted %d expired session(s): %s",
                        len(evicted),
                        evicted,
                    )
            except asyncio.CancelledError:
                logger.debug("AgentRunStateSweeper cancelled")
                break
            except Exception:  # noqa: BLE001
                logger.exception("AgentRunStateSweeper encountered an unexpected error")
