# [Input] None — standalone async tool-confirmation store.
# [Output] Provide ToolConfirmationStore, ToolConfirmationResult to ClaudeAgentService.
# [Pos] utility node in backend/claude_agent
# [Sync] 2026-05-22: direct migration from Pawkeyland application/claude_agent/tool_confirmation_store.py.
#                    No functional changes.

"""In-memory async store for pending tool confirmations.

Uses ``asyncio.Future`` to implement the blocking pattern:

  begin_pending()   →  registers Future before any outbound SSE (avoids races)
  await_pending()   →  awaits Future (blocks callback coroutine)
  resolve()         →  sets Future result  (called from confirm endpoint)
  cancel_pending()  →  drops a Future when the requester abandons the wait

Loop / thread safety
--------------------
Every Future is created on the loop running ``begin_pending`` and tagged with
that loop reference. ``resolve`` / ``reject`` schedule ``Future.set_result``
through ``loop.call_soon_threadsafe`` when called from a different thread or
loop, so the FastAPI worker loop is never blocked.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S: float = 5.0 * 60.0  # 300 seconds


@dataclass
class ToolConfirmationResult:
    """User's decision for a pending tool call."""

    approved: bool
    reason: Optional[str] = None
    answers: Optional[dict[str, Any]] = None


class ToolConfirmationStore:
    """Async in-memory store for pending tool confirmations."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[ToolConfirmationResult]] = {}
        self._pending_loops: dict[str, asyncio.AbstractEventLoop] = {}

    def begin_pending(self, tool_call_id: str) -> None:
        """Register a Future for *tool_call_id* before emitting client-visible SSE.

        Raises:
            RuntimeError: if *tool_call_id* is already awaiting confirmation.
        """
        loop = asyncio.get_running_loop()
        existing = self._pending.get(tool_call_id)
        if existing is not None and not existing.done():
            raise RuntimeError(
                f"begin_pending: tool_call_id={tool_call_id} already has a pending Future"
            )
        if existing is not None:
            self._pending.pop(tool_call_id, None)
            self._pending_loops.pop(tool_call_id, None)
        self._pending[tool_call_id] = loop.create_future()
        self._pending_loops[tool_call_id] = loop
        logger.debug(
            "Registered pending tool confirmation: tool_call_id=%s loop=%s",
            tool_call_id,
            id(loop),
        )

    async def await_pending(
        self,
        tool_call_id: str,
        *,
        tool_name: str = "",
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> ToolConfirmationResult:
        """Await the Future registered by :meth:`begin_pending`.

        Raises:
            RuntimeError: if :meth:`begin_pending` was not called for this id.
            TimeoutError: if the user does not respond within *timeout_s*.
            asyncio.CancelledError: if the surrounding task is cancelled.
        """
        future = self._pending.get(tool_call_id)
        if future is None:
            raise RuntimeError(
                f"await_pending: no begin_pending for tool_call_id={tool_call_id}"
            )
        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(
                "Tool confirmation timeout: tool_call_id=%s tool_name=%s",
                tool_call_id,
                tool_name,
            )
            raise TimeoutError(
                f"Tool confirmation timeout for tool_call_id={tool_call_id}"
            )
        except asyncio.CancelledError:
            raise
        finally:
            if self._pending.get(tool_call_id) is future:
                self._pending.pop(tool_call_id, None)
                self._pending_loops.pop(tool_call_id, None)

    async def create_pending(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> ToolConfirmationResult:
        """Convenience wrapper: :meth:`begin_pending` then :meth:`await_pending`."""
        del tool_input
        self.begin_pending(tool_call_id)
        return await self.await_pending(
            tool_call_id, tool_name=tool_name, timeout_s=timeout_s
        )

    def resolve(
        self,
        tool_call_id: str,
        result: ToolConfirmationResult,
    ) -> bool:
        """Resolve a pending tool confirmation with the user's decision.

        Returns ``True`` if resolved; ``False`` if not found or already done.
        """
        future = self._pending.get(tool_call_id)
        if future is None or future.done():
            logger.debug(
                "resolve called for unknown/already-done tool_call_id=%s", tool_call_id
            )
            return False
        loop = self._pending_loops.get(tool_call_id)
        return self._set_future_result(future, result, loop, tool_call_id)

    def reject(self, tool_call_id: str, error: BaseException) -> bool:
        """Reject a pending tool confirmation with an error."""
        future = self._pending.get(tool_call_id)
        if future is None or future.done():
            return False
        loop = self._pending_loops.get(tool_call_id)
        try:
            if self._is_caller_on_loop(loop):
                future.set_exception(error)
            else:
                assert loop is not None
                loop.call_soon_threadsafe(self._safe_set_future_exception, future, error)
            self._pending.pop(tool_call_id, None)
            self._pending_loops.pop(tool_call_id, None)
            return True
        except (asyncio.InvalidStateError, RuntimeError):
            return False

    def cancel_pending(self, tool_call_id: str) -> bool:
        """Drop the pending Future without resolving it (on client disconnect)."""
        future = self._pending.pop(tool_call_id, None)
        loop = self._pending_loops.pop(tool_call_id, None)
        if future is None:
            return False
        if future.done():
            return True
        if self._is_caller_on_loop(loop):
            future.cancel()
            return True
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._safe_cancel_future, future)
                return True
            except RuntimeError:
                return False
        try:
            future.cancel()
        except RuntimeError:
            return False
        return True

    def has_pending(self, tool_call_id: str) -> bool:
        fut = self._pending.get(tool_call_id)
        return fut is not None and not fut.done()

    def pending_ids(self) -> list[str]:
        return [k for k, fut in self._pending.items() if not fut.done()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _running_loop_or_none() -> Optional[asyncio.AbstractEventLoop]:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    @classmethod
    def _is_caller_on_loop(cls, loop: Optional[asyncio.AbstractEventLoop]) -> bool:
        if loop is None:
            return cls._running_loop_or_none() is None
        return cls._running_loop_or_none() is loop

    @staticmethod
    def _safe_set_future_result(
        future: "asyncio.Future[ToolConfirmationResult]",
        result: ToolConfirmationResult,
    ) -> None:
        if not future.done():
            try:
                future.set_result(result)
            except asyncio.InvalidStateError:
                pass

    @staticmethod
    def _safe_set_future_exception(
        future: "asyncio.Future[ToolConfirmationResult]",
        error: BaseException,
    ) -> None:
        if not future.done():
            try:
                future.set_exception(error)
            except asyncio.InvalidStateError:
                pass

    @staticmethod
    def _safe_cancel_future(future: "asyncio.Future[ToolConfirmationResult]") -> None:
        if not future.done():
            try:
                future.cancel()
            except RuntimeError:
                pass

    def _set_future_result(
        self,
        future: "asyncio.Future[ToolConfirmationResult]",
        result: ToolConfirmationResult,
        loop: Optional[asyncio.AbstractEventLoop],
        tool_call_id: str,
    ) -> bool:
        if self._is_caller_on_loop(loop):
            try:
                future.set_result(result)
            except asyncio.InvalidStateError:
                logger.warning(
                    "Failed to set_result for tool_call_id=%s", tool_call_id
                )
                return False
            logger.debug(
                "Resolved tool confirmation in-loop: tool_call_id=%s approved=%s",
                tool_call_id,
                result.approved,
            )
            return True
        if loop is None:
            logger.warning(
                "resolve invoked off-loop without recorded owner loop for "
                "tool_call_id=%s; dropping result",
                tool_call_id,
            )
            return False
        try:
            loop.call_soon_threadsafe(self._safe_set_future_result, future, result)
        except RuntimeError:
            logger.warning(
                "Owner loop closed before resolve for tool_call_id=%s", tool_call_id
            )
            return False
        logger.debug(
            "Resolved tool confirmation cross-loop: tool_call_id=%s approved=%s",
            tool_call_id,
            result.approved,
        )
        return True
