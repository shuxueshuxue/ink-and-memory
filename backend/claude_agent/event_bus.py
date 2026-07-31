# [Input] None — standalone EventBus Port/Adapter.
# [Output] IEventBus (Port), InMemoryEventBus (Adapter), BusProxyQueue, create_event_bus
#          consumed by thread_factory.py and service.py.
# [Pos] event-bus node in backend/claude_agent
# [Sync] 2026-06-09: initial implementation — Port/Adapter pattern for SSE broadcast.
#                    IEventBus defines publish/subscribe/unsubscribe/read.
#                    InMemoryEventBus: asyncio-based, supports replay buffer + fan-out.
#                    BusProxyQueue: adapts IEventBus.publish to asyncio.Queue.put interface
#                    so execute_session callbacks require zero changes.
#                    create_event_bus: factory selecting backend via INK_AGENT_EVENT_BUS_BACKEND.

"""Claude Agent SSE EventBus — Port/Adapter implementation.

Port
----
``IEventBus`` — stable broadcast interface used by thread_factory and service.
  publish(frame)   — push an SSE frame string (None = sentinel, stream done).
  subscribe()      — return an opaque token; internally replays history buffer
                     then live-delivers subsequent frames.
  unsubscribe(tok) — remove a consumer (does not cancel the producer task).
  read(tok)        — async-iterate frames until sentinel.
  is_done          — True after sentinel has been published.

Adapters
--------
``InMemoryEventBus``  — asyncio asyncio.Queue fan-out with replay buffer.
                        Default backend for single-process deployment.
``RedisStreamEventBus``  — imported lazily from event_bus_redis when
                           INK_AGENT_EVENT_BUS_BACKEND=redis.

Proxy
-----
``BusProxyQueue``  — wraps IEventBus.publish() as an asyncio.Queue-like .put()
                     so ClaudeAgentService.execute_session needs no changes.

Factory
-------
``create_event_bus(session_id, turn_id)``  — selects implementation from env.
"""
from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# SSE keepalive comment sent when no event arrives within _READ_TIMEOUT_S.
_READ_TIMEOUT_S: float = 15.0


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------


class IEventBus(ABC):
    """Stable broadcast interface — does not depend on any queue implementation.

    Contract
    --------
    - ``publish(None)`` is the sentinel that marks the stream as complete.
    - ``publish`` is idempotent after the sentinel: subsequent calls are no-ops.
    - ``subscribe`` replays the history buffer *then* registers for live events.
    - ``unsubscribe`` removes a consumer but does not affect the producer.
    - ``read`` is an async generator; it finishes when the sentinel is received.
    """

    @abstractmethod
    async def publish(self, frame: Optional[str]) -> None:
        """Emit one SSE frame. Pass ``None`` to signal stream completion."""
        ...

    @abstractmethod
    async def subscribe(self) -> object:
        """Register a new consumer. Returns an opaque subscription token."""
        ...

    @abstractmethod
    async def unsubscribe(self, token: object) -> None:
        """Deregister a consumer. Safe to call multiple times."""
        ...

    @abstractmethod
    def read(self, token: object) -> AsyncIterator[str]:
        """Async-iterate SSE frames until sentinel. Emits keepalives on idle."""
        ...

    @property
    @abstractmethod
    def is_done(self) -> bool:
        """True once the sentinel has been published."""
        ...


# ---------------------------------------------------------------------------
# Adapter A: InMemoryEventBus (default, single-process)
# ---------------------------------------------------------------------------


class InMemoryEventBus(IEventBus):
    """asyncio-based fan-out bus with replay buffer.

    - Replay buffer: every frame (including sentinel) is appended to
      ``_buffer``.  New subscribers receive the full history immediately.
    - Fan-out: each subscriber gets its own ``asyncio.Queue`` so one slow
      consumer cannot block another.
    - Idempotent sentinel: once ``done=True``, further ``publish`` calls
      are silently ignored.
    - Thread-safe within a single asyncio event loop (uses asyncio.Lock).
    """

    def __init__(self) -> None:
        self._buffer: list[Optional[str]] = []
        self._subscribers: list[asyncio.Queue] = []
        self._done: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # IEventBus
    # ------------------------------------------------------------------

    async def publish(self, frame: Optional[str]) -> None:
        async with self._lock:
            if self._done:
                return  # idempotent after sentinel
            self._buffer.append(frame)
            if frame is None:
                self._done = True
            for q in list(self._subscribers):
                await q.put(frame)

    async def subscribe(self) -> asyncio.Queue:
        """Return a new queue pre-loaded with the replay buffer."""
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            for frame in self._buffer:       # replay history
                await q.put(frame)
            if not self._done:               # register for live events
                self._subscribers.append(q)
        return q

    async def unsubscribe(self, token: object) -> None:
        q = token
        async with self._lock:
            try:
                self._subscribers.remove(q)  # type: ignore[arg-type]
            except ValueError:
                pass

    async def read(self, token: object) -> AsyncIterator[str]:  # type: ignore[override]
        q: asyncio.Queue = token  # type: ignore[assignment]
        while True:
            try:
                frame = await asyncio.wait_for(q.get(), timeout=_READ_TIMEOUT_S)
                if frame is None:
                    break
                yield frame
            except asyncio.TimeoutError:
                # No event within timeout window — emit SSE keepalive comment.
                if self._done:
                    break
                yield ": keepalive\n\n"
            except asyncio.CancelledError:
                break

    @property
    def is_done(self) -> bool:
        return self._done


# ---------------------------------------------------------------------------
# Proxy: asyncio.Queue-compatible shim for execute_session
# ---------------------------------------------------------------------------


class BusProxyQueue:
    """Adapts IEventBus.publish() to the asyncio.Queue.put() interface.

    ``ClaudeAgentService.execute_session`` and its streaming callbacks call
    ``await queue.put(frame)`` throughout.  Replacing ``_TurnContext.queue``
    with a ``BusProxyQueue`` forwards every ``put`` to ``bus.publish``,
    routing SSE frames to the EventBus without changing any callback code.
    """

    __slots__ = ("_bus",)

    def __init__(self, bus: IEventBus) -> None:
        self._bus = bus

    async def put(self, frame: Optional[str]) -> None:
        await self._bus.publish(frame)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_event_bus(session_id: str, turn_id: str) -> IEventBus:
    """Return an IEventBus implementation selected by environment variable.

    INK_AGENT_EVENT_BUS_BACKEND
        ``memory`` (default) — InMemoryEventBus (single-process, zero deps)
        ``redis``            — RedisStreamEventBus (multi-process, requires Redis)
    """
    backend = (os.getenv("INK_AGENT_EVENT_BUS_BACKEND") or "memory").strip().lower()
    if backend == "redis":
        try:
            from claude_agent.event_bus_redis import RedisStreamEventBus  # noqa: PLC0415
            logger.debug(
                "EventBus backend=redis session_id=%s turn_id=%s", session_id, turn_id
            )
            return RedisStreamEventBus(session_id, turn_id)
        except ImportError:
            logger.warning(
                "redis backend requested but redis-py is not installed; "
                "falling back to memory backend"
            )
    logger.debug(
        "EventBus backend=memory session_id=%s turn_id=%s", session_id, turn_id
    )
    return InMemoryEventBus()
