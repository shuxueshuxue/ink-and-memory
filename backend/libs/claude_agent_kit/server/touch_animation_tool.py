# [Input] Consume pydantic for schema validation; no external dependencies.
# [Output] Provide TouchAnimationInput, TouchAnimationOutput, AnimationInteraction,
#          and touch_animation_handler to mcp_server.py.
# [Pos] tool-definition node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: document default auto-mode stdio MCP flow and optional manual confirmation answers.
# [Sync] 2026-05-10: use interaction.type=text for Agent text-triggered animation inputs and auto-only results.
# [Sync] 2026-05-10: accept legacy interaction.type=none as an auto-only alias so old animation events do not fail validation.

"""TouchAnimationTool — Pydantic schemas and handler for pet animation events.

Corresponds to the design in:
  docs/app/design/LLM驱动动画事件图设计方案.md — §9.3 Python 工具定义

The tool gives the LLM a dedicated channel for triggering pet/character animation
states with configurable user-interaction strategies.  It replaces the overloaded
``AskUserQuestion`` pattern with a semantically precise tool that carries only the
animation-specific fields (act / duration / interaction / answers).

Interaction type
----------------
text    Agent text triggered animation — frontend plays it without touch affordance.
        Current Agent tool calls treat every act as text-sourced and do not use
        touch or choice interaction inputs.
none    Legacy auto-only animation event.  It is accepted for compatibility and
        behaves the same as text from the tool-result perspective: the frontend
        waits for video end or the duration timeout, then reports auto.

Flow
----
1. LLM issues a ``mcp__user__touch_animation`` tool call carrying
   ``TouchAnimationInput`` (act, duration, interaction).
2. In default ``tool_choice="auto"``, the runner exposes the tool through an
   external stdio MCP server and the SDK executes allowed tool calls without
   the Python SDK permission-control callback.  The service still streams the
   tool input to the frontend so it can play the animation.
3. Optional manual/debug flows can still use the runner ``PreToolUse`` hook and
   ``ToolConfirmationStore`` to merge frontend ``answers`` into the tool input.
4. The SDK invokes the MCP ``touch_animation`` handler, which calls
   ``touch_animation_handler(input_data)`` and returns a human-readable result
   string to the LLM so it can decide the next step.
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input schemas  (§2.1 AnimationEventInput in the design doc)
# ---------------------------------------------------------------------------


class AnimationInteraction(BaseModel):
    """Animation interaction strategy for Agent-triggered animation events.

    type="text"
        Agent text triggered animation.  The frontend plays the clip and
        resolves it automatically without enabling touch interruption.
        Current Agent tool calls use this value for every act.
    type="none"
        Legacy auto-only interaction.  Accepted as an alias for text so stored
        or older tool events still wait for clip completion instead of failing
        input validation.
    """

    type: Literal["text", "none"] = Field(
        description=(
            '交互类型。'
            '"text" = Agent 根据文本回复触发动画。'
            '"none" = 历史 auto-only 动画事件，兼容处理为等待动画结束。'
        )
    )

class TouchAnimationInput(BaseModel):
    """Parameters passed by the LLM when calling ``touch_animation``.

    Maps to ``AnimationEventInput`` in the design (§2.1).
    The ``answers`` field is **not** filled by the LLM; it is injected by
    ``PreToolUse`` / ``ToolConfirmationStore`` after the frontend animation
    completes and POSTs its result to ``/api/claude-agent/tool-confirm``.  In
    the default auto-mode stdio MCP path it can remain unset; the handler then
    reports an ``auto`` trigger.

    Usage guide
    -----------
    - Choose ``act`` from the list in the tool description (loaded from
      ``animation_event_dictionary.json``).
    - Use the act's ``default_duration`` as a starting value for ``duration``.
    - Use ``interaction={"type":"text"}``; current Agent animation events are
      text-sourced.  ``{"type":"none"}`` is accepted only for legacy auto-only
      events.
    """

    act: str = Field(
        description=(
            "动画动作名称。必须是工具描述中列出的有效 act 值，不得使用其他值。"
            "每个 act 有对应的默认时长（default_duration）和预设交互类型（interaction），"
            "请参考工具描述中的动作清单。"
        )
    )
    duration: int = Field(
        description=(
            "动画播放时长（毫秒）。"
            "建议直接使用工具描述中该 act 的 default_duration 值。"
            "如需调整，范围不得低于 500ms 或超过 30000ms。"
        ),
    )
    interaction: AnimationInteraction = Field(
        description=(
            "交互策略配置。"
            '当前 Agent 动画工具调用统一使用 interaction={"type":"text"}；'
            '历史 interaction={"type":"none"} 按自动播放完成兼容。'
        )
    )
    # answers is back-filled by PreToolUse after the frontend resolves the
    # tool confirmation; the LLM always leaves this field unset.
    answers: Optional[dict[str, Any]] = Field(
        default=None,
        description="前端动画层结束后回填的结果（LLM 调用时留空）",
    )


# ---------------------------------------------------------------------------
# Output schema  (§2.3 AnimationEventResult in the design doc)
# ---------------------------------------------------------------------------


class TouchAnimationOutput(BaseModel):
    """Result returned to the LLM after the animation event completes.

    Maps to ``AnimationEventResult`` in the design (§2.3).
    """

    act: str = Field(description="已播放的动画名称")
    trigger: Literal["auto"] = Field(
        description=(
            "动画结束触发方式："
            '"auto" = 当前文本触发动画自然结束或防御性归一后的结果'
        )
    )
    choice_id: Optional[str] = Field(
        default=None, description="保留历史兼容字段；当前文本触发动画不会产生 choice_id"
    )
    elapsed_ms: Optional[int] = Field(
        default=None, description="动画已播放时长（毫秒），打断时有参考价值"
    )


# ---------------------------------------------------------------------------
# Handler  (§9.3 touch_animation_handler)
# ---------------------------------------------------------------------------

_VALID_TRIGGERS = frozenset({"auto"})


async def touch_animation_handler(input_data: TouchAnimationInput) -> str:
    """MCP handler for the ``touch_animation`` tool.

    Extracts ``AnimationEventResult`` from ``input_data.answers`` (which was
    injected by optional manual confirmation after the frontend posted its
    result) and returns a human-readable summary string that the LLM can use to
    decide the next animation or conversational step.  When no answers are
    present, the default trigger is ``auto``.
    """
    answers: dict[str, Any] = input_data.answers or {}

    # Extract trigger — validate against the allowed literal values; fall back
    # to "auto" when the frontend sends an unexpected value (defensive coding).
    raw_trigger = answers.get("trigger", "auto")
    trigger: Literal["auto"] = (
        raw_trigger if raw_trigger in _VALID_TRIGGERS else "auto"
    )

    choice_id: Optional[str] = None
    elapsed_ms_raw = answers.get("elapsed_ms") or answers.get("elapsedMs")
    elapsed_ms: Optional[int] = None
    if elapsed_ms_raw is not None:
        try:
            elapsed_ms = int(elapsed_ms_raw)
        except (TypeError, ValueError):
            logger.debug("touch_animation_handler: invalid elapsed_ms value: %r", elapsed_ms_raw)

    result = TouchAnimationOutput(
        act=input_data.act,
        trigger=trigger,
        choice_id=choice_id,
        elapsed_ms=elapsed_ms,
    )

    logger.debug(
        "touch_animation_handler: act=%s trigger=%s choice_id=%s elapsed_ms=%s",
        result.act,
        result.trigger,
        result.choice_id,
        result.elapsed_ms,
    )

    # Build the human-readable result description that goes back to the LLM.
    # Mirrors AskUserQuestionTool.mapToolResultToToolResultBlockParam in TS.
    parts = [f'动画 "{result.act}" 已结束，触发方式：{result.trigger}']
    if result.elapsed_ms is not None:
        parts.append(f"已播放：{result.elapsed_ms} ms")
    parts.append("你可以根据此结果决定下一步动画或对话。")

    return "。".join(parts)
