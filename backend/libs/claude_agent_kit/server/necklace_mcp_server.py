# [Input] Consume NecklaceNoInput/NECKLACE_TOOL_SPECS/get_pet_live_context_handler from necklace_tool.py.
# [Output] Provide create_necklace_mcp_server() for the stdio MCP entrypoint.
# [Pos] mcp-server node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: register zero-argument necklace intent tools.

from __future__ import annotations

from typing import Any, Optional

from mcp import types as mcp_types
from mcp.server import Server as McpServer

from .necklace_tool import NECKLACE_TOOL_SPECS, NecklaceNoInput, get_pet_live_context_handler


def create_necklace_mcp_server() -> McpServer:
    """Create the read-only necklace MCP server.

    Claude sees this server under the ``necklace`` namespace, so the tools
    available in prompts/allowlists are ``mcp__necklace__{tool_name}``.
    """

    server = McpServer("necklace")
    input_schema = NecklaceNoInput.model_json_schema()
    shared_description = (
        "\n只读，不修改设备。不要传任何参数：tool name 就是查询意图；pet_id、pet_type、"
        "日期、月份、起止时间、recent window 和上游 Swagger 参数全部由服务端绑定和脚本生成。"
        "工具返回 JSON，其中 live_context 字段才是生成回复可引用的事实来源。"
        "last_location 只说明宠物是否还在家/安全区域，不能推断用户回家。"
        "如果 ok=false 或 error=no_data，表示本次没有任何可引用硬件事实；只能说摸不准/"
        "项圈没查清楚，禁止用宠物人设补写睡觉、走路、玩耍、窗台、阳光、鸟叫、位置细节"
        "或任何具体活动。如果 live_context 有位置但 unavailable 包含动作/日摘要，只能引用"
        "位置/在家事实，禁止补写动作、等待主人或场景细节。"
    )

    @server.list_tools()  # type: ignore[misc]
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=name,
                description=f"{spec.description}{shared_description}",
                inputSchema=input_schema,
            )
            for name, spec in NECKLACE_TOOL_SPECS.items()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def call_tool(
        name: str,
        arguments: Optional[dict[str, Any]],
    ) -> list[mcp_types.TextContent]:
        if name not in NECKLACE_TOOL_SPECS:
            raise ValueError(f"Unknown tool: {name!r}")
        try:
            NecklaceNoInput.model_validate(arguments or {})
        except Exception as exc:  # noqa: BLE001
            return [
                mcp_types.TextContent(
                    type="text",
                    text=f'{{"ok":false,"error":"invalid_input:{str(exc)[:160]}","live_context":{{}}}}',
                )
            ]
        result_text = await get_pet_live_context_handler(name)
        return [mcp_types.TextContent(type="text", text=result_text)]

    return server
