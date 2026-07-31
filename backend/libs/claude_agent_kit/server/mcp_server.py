# [Input] Consume mcp.server.Server, mcp.types; TouchAnimationInput,
#         AnimationInteraction, touch_animation_handler from touch_animation_tool.py.
# [Output] Provide create_user_mcp_server() to the stdio MCP entrypoint and application layers.
# [Pos] mcp-server node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: share touch_animation registration with the external stdio MCP entrypoint.
# [Sync] 2026-05-10: remove stale unused animation enum formatting local.
# [Sync] 2026-05-10: expose interaction.type=text for Agent text-triggered animation inputs instead of tap.
# [Sync] 2026-05-10: accept legacy interaction.type=none as auto-only compatibility while keeping text as the preferred Agent input.

"""MCP server factory for the 'user' namespace tools.

Registers MCP tools that the LLM can call to interact with the user/frontend
outside of the normal text-response channel.

Current tools
-------------
touch_animation  (mcp__user__touch_animation)
    Triggers a pet/character animation state on the frontend.  The LLM
    specifies the act, duration, and interaction strategy; the frontend plays
    the animation and returns the result via ``/api/claude-agent/tool-confirm``.

    At server creation time, ``animation_event_dictionary.json`` is loaded and
    its act list (with default_duration and interaction presets) is embedded
    directly into the tool description and input schema, so the LLM always
    sees the authoritative, up-to-date act catalogue.

Usage
-----
Run the shared server through the stdio entrypoint and register it in
``ClaudeAgentOptions.mcp_servers`` as an external server::

    from claude_agent_sdk.types import McpStdioServerConfig

    sdk_options = ClaudeAgentOptions(
        mcp_servers={
            "user": McpStdioServerConfig(
                type="stdio",
                command="/path/to/python",
                args=["-m", "libs.claude_agent_kit.server.user_mcp_stdio"],
            )
        },
        ...
    )

References
----------
- ``docs/app/design/LLM驱动动画事件图设计方案.md`` §9.4 MCP 服务器注册
- https://oneryalcin.medium.com/when-claude-cant-ask-building-interactive-tools-for-the-agent-sdk-64ccc89558fa
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mcp import types as mcp_types
from mcp.server import Server as McpServer

from .touch_animation_tool import AnimationInteraction, TouchAnimationInput, touch_animation_handler
from .sessions_tool import (
    GET_SESSIONS_RANGE_TOOL_NAME,
    GET_SESSIONS_RANGE_TOOL_SPEC,
    handle_get_sessions_range,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Animation event dictionary — loaded once at module import
# ---------------------------------------------------------------------------

# Path: libs/claude_agent_kit/server/ → up 3 dirs → repo root → prompts/policies/
_POLICIES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "policies"
_ANIMATION_DICT_PATH = _POLICIES_DIR / "animation_event_dictionary.json"


def _load_animation_dict() -> dict[str, Any]:
    """Load animation_event_dictionary.json from the prompts/policies/ directory.

    Returns an empty dict on any I/O or parse error so that MCP server
    creation degrades gracefully rather than crashing at startup.
    """
    try:
        return json.loads(_ANIMATION_DICT_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not load animation_event_dictionary.json from %s — "
            "tool description will fall back to minimal defaults.",
            _ANIMATION_DICT_PATH,
        )
        return {}


def _build_act_catalogue_text(events: list[dict[str, Any]]) -> str:
    """Render the act list from the dictionary into a human-readable block.

    Example output line:
        "playing"（玩耍）| 默认时长：6300ms | 交互：text（Agent 文本回复触发）
    """
    lines: list[str] = []
    for ev in events:
        act = ev.get("act", "")
        label = ev.get("label", "")
        default_duration = ev.get("default_duration", "")
        interaction = ev.get("interaction") or {}
        itype = interaction.get("type", "text")
        interaction_desc = (
            "text（Agent 文本回复触发）"
            if itype == "text"
            else f"{itype or 'text'}（非当前 Agent 协议；请修正 animation_event_dictionary.json）"
        )

        lines.append(
            f'  "{act}"（{label}）| 默认时长：{default_duration}ms | 交互：{interaction_desc}'
        )
    return "\n".join(lines)


def _build_act_enum(events: list[dict[str, Any]]) -> list[str]:
    """Return the list of valid act strings from the dictionary."""
    return [ev["act"] for ev in events if ev.get("act")]


# ---------------------------------------------------------------------------
# JSON Schema builder (动态，从字典构建)
# ---------------------------------------------------------------------------


def _build_input_schema(
    act_enum: list[str],
    act_catalogue_text: str,
) -> dict[str, Any]:
    """Build the JSON Schema for the touch_animation input, embedding the act list.

    Parameters
    ----------
    act_enum:
        Valid act strings (used as the JSON Schema ``enum`` for the act field).
    act_catalogue_text:
        Human-readable act catalogue injected into the act field description.
    """
    act_description = (
        f"动画动作名称。必须使用以下有效值（来自 animation_event_dictionary.json）：\n"
        f"{act_catalogue_text}\n"
        f"直接使用字典中该 act 的 default_duration 作为 duration 初始值，"
        f"并使用对应的 interaction 预设。"
    )

    schema: dict[str, Any] = {
        "type": "object",
        "required": ["act", "duration", "interaction"],
        "properties": {
            "act": {
                "type": "string",
                "description": act_description,
            },
            "duration": {
                "type": "integer",
                "description": (
                    "动画播放时长（毫秒）。"
                    "应使用上方 act 清单中该 act 的 default_duration 值作为起点。"
                    "合法范围：500–30000 ms。"
                ),
                "minimum": 500,
                "maximum": 30000,
            },
            "interaction": {
                "type": "object",
                "required": ["type"],
                "description": (
                    "交互策略配置。"
                    "当前 Agent 动画工具调用统一使用 interaction.type=\"text\"，"
                    "表示动画来源于 Agent 文本回复。历史 interaction.type=\"none\" "
                    "兼容为自动等待动画结束。"
                ),
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["text", "none"],
                        "description": (
                            '"text" = Agent 根据文本回复触发动画；'
                            '"none" = 历史 auto-only 动画事件，等待视频 ended 或 duration 兜底'
                        ),
                    },
                },
            },
            "answers": {
                "type": "object",
                "description": "前端动画层结束后回填的结果（LLM 调用时留空）",
                "nullable": True,
            },
        },
    }
    # If we have a valid enum, constrain the act field
    if act_enum:
        schema["properties"]["act"]["enum"] = act_enum  # type: ignore[index]
    return schema


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------


def create_user_mcp_server() -> McpServer:
    """Create and return a configured 'user' MCP server instance.

    Loads ``animation_event_dictionary.json`` at call time to embed the
    authoritative act catalogue into the ``touch_animation`` tool description
    and input schema.

    The returned server has the ``touch_animation`` tool registered under
    the ``user`` namespace.  When Claude Code loads this server through the
    stdio entrypoint, the tool is available as ``mcp__user__touch_animation``
    in the allowed-tools list.

    Returns
    -------
    McpServer
        A ``mcp.server.Server`` instance ready to be served through stdio.
    """
    # ---- Load and process the animation event dictionary ----
    anim_dict = _load_animation_dict()
    events: list[dict[str, Any]] = anim_dict.get("events") or []

    act_enum = _build_act_enum(events)
    act_catalogue_text = _build_act_catalogue_text(events)
    input_schema = _build_input_schema(act_enum, act_catalogue_text)

    # Build the tool description that the LLM sees — embeds the full act list.
    tool_description = (
        "触发宠物/角色动画状态的专属工具。\n"
        "LLM 通过此工具发出动画指令（act + duration + interaction 策略），"
        "前端动画层播放动画，结束后通过 /api/claude-agent/tool-confirm 回传触发方式和用户互动结果。\n"
        "请优先使用此工具代替 AskUserQuestion 来触发动画事件。\n\n"
        "【可用动作清单（animation_event_dictionary.json）】\n"
        f"{act_catalogue_text}\n\n"
        "【interaction.type 语义说明】\n"
        "  text = Agent 根据文本回复触发动画；当前所有 act 都使用 text，不使用 tap。\n\n"
        "【调用建议】\n"
        "  1. 从上方清单选取 act 并使用其 default_duration 作为 duration 初始值。\n"
        "  2. 使用 interaction: {\"type\":\"text\"}；不要传 choices。\n"
        "  3. answers 字段由前端回填，LLM 调用时留空。\n"
        "  4. 工具返回后根据 trigger 决定下一步回应。"
    )

    # ---- Build the server ----
    server = McpServer("user")

    @server.list_tools()  # type: ignore[misc]
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="touch_animation",
                description=tool_description,
                inputSchema=input_schema,
            ),
            mcp_types.Tool(
                name=GET_SESSIONS_RANGE_TOOL_NAME,
                description=GET_SESSIONS_RANGE_TOOL_SPEC.description,
                inputSchema=GET_SESSIONS_RANGE_TOOL_SPEC.input_schema,
            ),
        ]

    @server.call_tool()  # type: ignore[misc]
    async def call_tool(
        name: str, arguments: Optional[dict[str, Any]]
    ) -> list[mcp_types.TextContent]:
        if name == "touch_animation":
            args: dict[str, Any] = arguments or {}
            try:
                input_data = TouchAnimationInput(
                    act=args.get("act", ""),
                    duration=int(args.get("duration", 3000)),
                    interaction=AnimationInteraction.model_validate(
                        args.get("interaction", {"type": "text"})
                    ),
                    answers=args.get("answers"),
                )
            except (ValueError, TypeError, Exception) as exc:  # noqa: BLE001  # pydantic raises generic ValueError/ValidationError
                logger.warning("touch_animation: input validation failed: %s", exc)
                # Return a graceful error to the LLM rather than raising
                return [
                    mcp_types.TextContent(
                        type="text",
                        text=f"动画工具输入格式错误：{exc}。请检查 act、duration 和 interaction 字段。",
                    )
                ]

            result_text = await touch_animation_handler(input_data)
            return [mcp_types.TextContent(type="text", text=result_text)]

        if name == GET_SESSIONS_RANGE_TOOL_NAME:
            result_text = handle_get_sessions_range(arguments)
            return [mcp_types.TextContent(type="text", text=result_text)]

        raise ValueError(f"Unknown tool: {name!r}")

    return server
