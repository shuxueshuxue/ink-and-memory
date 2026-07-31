# [Input] Consume MemoryNoInput and recall_shared_stories_handler from memory_tool.py.
# [Output] Provide create_memory_mcp_server() for the stdio MCP entrypoint.
# [Pos] mcp-server node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: register zero-argument Mem0 shared-story recall tool.

from __future__ import annotations

from typing import Any, Optional

from mcp import types as mcp_types
from mcp.server import Server as McpServer

from .memory_tool import MEMORY_TOOL_NAME, MemoryNoInput, recall_shared_stories_handler


def create_memory_mcp_server() -> McpServer:
    """Create the read-only memory MCP server under the ``memory`` namespace."""

    server = McpServer("memory")
    input_schema = MemoryNoInput.model_json_schema()
    description = (
        "按需回忆当前主人和当前宠物之间的共同故事、关系事实和陪伴偏好。"
        "不要传任何参数：mem0_user_id、query、top_k 都由服务端绑定。"
        "只有当前回应需要过去共同经历时才调用。工具返回 shared_stories；"
        "如果为空或 ok=false，表示没有可引用长期记忆，禁止编造过去发生过的事。"
    )

    @server.list_tools()  # type: ignore[misc]
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=MEMORY_TOOL_NAME,
                description=description,
                inputSchema=input_schema,
            )
        ]

    @server.call_tool()  # type: ignore[misc]
    async def call_tool(
        name: str,
        arguments: Optional[dict[str, Any]],
    ) -> list[mcp_types.TextContent]:
        if name != MEMORY_TOOL_NAME:
            raise ValueError(f"Unknown tool: {name!r}")
        try:
            MemoryNoInput.model_validate(arguments or {})
        except Exception as exc:  # noqa: BLE001
            return [
                mcp_types.TextContent(
                    type="text",
                    text=f'{{"ok":false,"error":"invalid_input:{str(exc)[:160]}","shared_stories":[]}}',
                )
            ]
        result_text = await recall_shared_stories_handler()
        return [mcp_types.TextContent(type="text", text=result_text)]

    return server


__all__ = ["create_memory_mcp_server"]
