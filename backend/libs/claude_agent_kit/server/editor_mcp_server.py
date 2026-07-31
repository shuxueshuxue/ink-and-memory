# [Input] Consume EDITOR_WRITE_TOOL_SPECS, handle_editor_write_tool from editor_tool.py.
#         editor_tool.py loads session context from INK_AGENT_SESSION_ID /
#         INK_AGENT_USER_ID env vars and calls database directly for state access.
# [Output] Provide create_editor_mcp_server() for the stdio MCP entrypoint.
# [Pos] mcp-server node in libs/claude_agent_kit/server
# [Sync] 2026-05-28: initial implementation — read-only EditorState MCP server.
# [Sync] 2026-05-29: update [Input] header to trace the editor_index.py mapping origin.
# [Sync] 2026-05-29: switch from read-only tools to write-only tools (EDITOR_WRITE_TOOL_SPECS /
#                    handle_editor_write_tool); reading is exclusively via .editor/ virtual
#                    index PreToolUse interception in agent_runner.py.

from __future__ import annotations

from typing import Any, Optional

from mcp import types as mcp_types
from mcp.server import Server as McpServer

from .editor_tool import EDITOR_WRITE_TOOL_SPECS, handle_editor_write_tool


def create_editor_mcp_server() -> McpServer:
    """Create the write-only editor MCP server.

    Claude sees this server under the ``editor`` namespace, so the tools
    available in prompts/allowlists are ``mcp__editor__{tool_name}``.

    All tools require human confirmation via the PreToolUse hook before
    execution (registered in ``_ALWAYS_CONFIRM_TOOL_NAMES`` in agent_runner.py).
    """

    server = McpServer("editor")

    @server.list_tools()  # type: ignore[misc]
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=name,
                description=spec.description,
                inputSchema=spec.input_schema,
            )
            for name, spec in EDITOR_WRITE_TOOL_SPECS.items()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def call_tool(
        name: str,
        arguments: Optional[dict[str, Any]],
    ) -> list[mcp_types.TextContent]:
        if name not in EDITOR_WRITE_TOOL_SPECS:
            raise ValueError(f"Unknown tool: {name!r}")
        result_text = handle_editor_write_tool(name, arguments)
        return [mcp_types.TextContent(type="text", text=result_text)]

    return server
