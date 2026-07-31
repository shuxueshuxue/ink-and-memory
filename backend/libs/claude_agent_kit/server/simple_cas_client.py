# [Input] Consume IClaudeAgentSDKClient contract from libs/claude_agent_kit/types.py.
# [Output] Provide SimpleClaudeAgentSDKClient backed by ClaudeSDKClient.
# [Pos] adapter node in libs/claude_agent_kit/server
# [Sync] 2026-05-08: always use ClaudeSDKClient so permission and SDK MCP control responses keep stdin open.
# [Sync] 2026-05-08: merge project .env into ClaudeAgentOptions.env before starting ClaudeSDKClient.
# [Sync] 2026-05-08: force Claude Code settings source to project via Python SDK extra_args.
# [Sync] 2026-07-26: SDK migration claude-code-sdk → claude-agent-sdk 0.2.128;
#                    ClaudeSDKClient query/receive_response semantics unchanged.

"""Simple Claude Agent SDK Client.

Python translation of TypeScript:
  server/server/simple-cas-client.ts

Thin adapter over the Claude Code SDK.  It defaults to ``ClaudeSDKClient`` so
stdin remains open for the bidirectional control protocol used by permission
callbacks and in-process MCP servers.
"""
from __future__ import annotations

import sys
from collections.abc import AsyncIterable
from collections.abc import AsyncIterator
from typing import Any, Optional

from claude_agent_sdk import ClaudeSDKClient  # type: ignore[import-untyped]
from claude_agent_sdk.types import ClaudeAgentOptions  # type: ignore[import-untyped]

from ..types import IClaudeAgentSDKClient
from .sdk_env import apply_project_sdk_runtime_options
from .session_files import (
    get_projects_root,
    locate_session_file,
    normalize_session_id,
    read_session_messages,
)


class SimpleClaudeAgentSDKClient(IClaudeAgentSDKClient):
    """Minimal Claude Agent SDK client.

    Delegates query streaming to :class:`claude_agent_sdk.ClaudeSDKClient` and
    message loading to the JSONL session-file utilities.  ``ClaudeSDKClient``
    keeps stdin open long enough for bidirectional control messages, which is
    required by permission callbacks and SDK MCP servers.

    Maps to TypeScript ``SimpleClaudeAgentSDKClient`` in
    server/server/simple-cas-client.ts.
    """

    async def query_stream(
        self,
        prompt: Any,
        options: Optional[ClaudeAgentOptions] = None,
    ) -> AsyncIterator[Any]:
        """Stream messages from the Claude agent subprocess."""
        effective_options = apply_project_sdk_runtime_options(
            options or ClaudeAgentOptions()
        )
        async with ClaudeSDKClient(options=effective_options) as client:
            if isinstance(prompt, AsyncIterable) or isinstance(prompt, str):
                await client.query(prompt)
            else:
                raise TypeError(
                    "ClaudeSDKClient requires a string or async iterable prompt"
                )
            async for message in client.receive_response():
                yield message

    async def load_messages(
        self,
        session_id: Optional[str],
    ) -> dict[str, list[Any]]:
        """Load message history for a given session ID.

        Returns ``{"messages": [...]}`` so callers can destructure the same
        way as the TypeScript version.
        """
        if not session_id:
            return {"messages": []}

        projects_root = get_projects_root()
        if not projects_root:
            return {"messages": []}

        normalized_session_id = normalize_session_id(session_id)

        try:
            file_path = await locate_session_file(
                projects_root=projects_root,
                session_id=normalized_session_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"Failed to locate session '{normalized_session_id}': {exc}",
                file=sys.stderr,
            )
            return {"messages": []}

        if not file_path:
            return {"messages": []}

        try:
            messages = await read_session_messages(file_path)
            return {"messages": messages}
        except Exception as exc:  # noqa: BLE001
            print(
                f"Failed to read session file '{file_path}': {exc}",
                file=sys.stderr,
            )
            return {"messages": []}
