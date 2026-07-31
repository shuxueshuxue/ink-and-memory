# [Input] Consume create_editor_mcp_server from editor_mcp_server.py and MCP stdio transport.
#         Tool mapping traces: editor_mcp_server → editor_tool → editor_index.EDITOR_RESOURCES.
# [Output] Run the editor MCP namespace as a standalone stdio server for Claude Code CLI.
# [Pos] stdio-mcp-entrypoint node in libs/claude_agent_kit/server
# [Sync] 2026-05-28: initial implementation — EditorState read-only tools over stdio MCP.
# [Sync] 2026-05-29: update [Input] header to trace mapping origin through editor_index.py.

from __future__ import annotations

import asyncio

from mcp.server.stdio import stdio_server

from .editor_mcp_server import create_editor_mcp_server


async def main() -> None:
    """Start the editor MCP server on stdin/stdout."""

    server = create_editor_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
