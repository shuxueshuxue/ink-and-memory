# [Input] Consume create_necklace_mcp_server from necklace_mcp_server.py and MCP stdio transport.
# [Output] Run the necklace MCP namespace as a standalone stdio server for Claude Code CLI.
# [Pos] stdio-mcp-entrypoint node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: expose read-only necklace live-context tool over stdio MCP.

from __future__ import annotations

import asyncio

from mcp.server.stdio import stdio_server

from .necklace_mcp_server import create_necklace_mcp_server


async def main() -> None:
    """Start the necklace MCP server on stdin/stdout."""

    server = create_necklace_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
