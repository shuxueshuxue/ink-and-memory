# [Input] None — standalone observer protocol and registry.
# [Output] Provide SessionLifecycleObserver, SessionObserverRegistry, LoggingObserver
#          to ClaudeAgentThreadFactory and external consumers.
# [Pos] observer node in backend/claude_agent
# [Sync] 2026-05-22: direct migration from Pawkeyland application/claude_agent/observer.py.
#                    No functional changes; env-prefix references updated to INK_AGENT_*.

"""Claude Agent Session Lifecycle Observer.

Observer pattern for the 4-phase Thread Session lifecycle:

    Phase 1 — Context Assembly  (per turn — before/after)
    Phase 2 — Runner Creation   (cached — before/after)
    Phase 3 — Session Start     (per turn — before/after)
    Phase 4 — Session End       (State destruction — before/after)

Phase 4 fires on the State's terminal transition (IDLE → DESTROYED), not on
every turn boundary.  The flyweight AgentRunState survives across turns for
``INK_AGENT_TTL_S`` seconds (default 10 min); only when that window elapses
or ``ClaudeAgentThreadFactory.close_thread`` / ``aclose`` is called does the
session truly "end".

``on_after_session_ended`` receives::

    {
        "session_id": "<user_id>",
        "reason": "explicit_close" | "ttl_expired" | "factory_aclose",
        "destroyed": True,
        "turn_count": <int, when known>,
    }
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Observer interface
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionLifecycleObserver(Protocol):
    """Interface for Thread Session lifecycle observers.

    All hooks are optional; concrete classes implement only the phases they care
    about.  Both synchronous and async signatures are supported.
    """

    async def on_before_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None: ...

    async def on_after_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None: ...

    async def on_before_runner_created(self, session_id: str) -> None: ...

    async def on_after_runner_created(self, session_id: str, runner: Any) -> None: ...

    async def on_before_session_started(
        self, session_id: str, opts: dict[str, Any]
    ) -> None: ...

    async def on_after_session_started(self, session_id: str) -> None: ...

    async def on_before_session_ended(self, session_id: str) -> None: ...

    async def on_after_session_ended(
        self, session_id: str, result: dict[str, Any]
    ) -> None: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class SessionObserverRegistry:
    """Dispatches lifecycle events to all registered observers in insertion order.

    Individual observer errors are logged and swallowed; ``CancelledError``
    is always re-raised so task-cancellation is never suppressed.
    """

    def __init__(self) -> None:
        self._observers: list[SessionLifecycleObserver] = []

    def register(self, observer: SessionLifecycleObserver) -> None:
        self._observers.append(observer)

    def unregister(self, observer: SessionLifecycleObserver) -> None:
        self._observers = [o for o in self._observers if o is not observer]

    async def _emit(self, method: str, *args: Any, **kwargs: Any) -> None:
        for observer in list(self._observers):
            fn = getattr(observer, method, None)
            if not callable(fn):
                continue
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Observer %s.%s raised an unhandled error",
                    type(observer).__name__,
                    method,
                )

    async def emit_before_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        await self._emit("on_before_context_assembly", session_id, metadata)

    async def emit_after_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        await self._emit("on_after_context_assembly", session_id, metadata)

    async def emit_before_runner_created(self, session_id: str) -> None:
        await self._emit("on_before_runner_created", session_id)

    async def emit_after_runner_created(self, session_id: str, runner: Any) -> None:
        await self._emit("on_after_runner_created", session_id, runner)

    async def emit_before_session_started(
        self, session_id: str, opts: dict[str, Any]
    ) -> None:
        await self._emit("on_before_session_started", session_id, opts)

    async def emit_after_session_started(self, session_id: str) -> None:
        await self._emit("on_after_session_started", session_id)

    async def emit_before_session_ended(self, session_id: str) -> None:
        await self._emit("on_before_session_ended", session_id)

    async def emit_after_session_ended(
        self, session_id: str, result: dict[str, Any]
    ) -> None:
        await self._emit("on_after_session_ended", session_id, result)


# ---------------------------------------------------------------------------
# Built-in observers
# ---------------------------------------------------------------------------


class LoggingObserver:
    """Concrete observer that writes all lifecycle events to the logger.

    Register at startup::

        factory.register_observer(LoggingObserver())
    """

    def __init__(self, log: logging.Logger | None = None) -> None:
        self._log = log or logger

    async def on_before_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        self._log.debug("[Agent] before_context_assembly session_id=%s", session_id)

    async def on_after_context_assembly(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        self._log.debug(
            "[Agent] after_context_assembly session_id=%s keys=%s",
            session_id,
            list(metadata),
        )

    async def on_before_runner_created(self, session_id: str) -> None:
        self._log.debug("[Agent] before_runner_created session_id=%s", session_id)

    async def on_after_runner_created(self, session_id: str, runner: Any) -> None:
        self._log.debug(
            "[Agent] after_runner_created session_id=%s runner=%s",
            session_id,
            type(runner).__name__,
        )

    async def on_before_session_started(
        self, session_id: str, opts: dict[str, Any]
    ) -> None:
        self._log.debug("[Agent] before_session_started session_id=%s", session_id)

    async def on_after_session_started(self, session_id: str) -> None:
        self._log.debug("[Agent] after_session_started session_id=%s", session_id)

    async def on_before_session_ended(self, session_id: str) -> None:
        self._log.debug("[Agent] before_session_ended session_id=%s", session_id)

    async def on_after_session_ended(
        self, session_id: str, result: dict[str, Any]
    ) -> None:
        self._log.info(
            "[Agent] session_ended session_id=%s reason=%s turn_count=%s",
            session_id,
            result.get("reason"),
            result.get("turn_count"),
        )
