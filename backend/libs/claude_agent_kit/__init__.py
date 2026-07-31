# [Input] None — top-level package re-export.
# [Output] Expose ClaudeAgentRunner, create_agent_runner, SimpleClaudeAgentSDKClient,
#          AgentRunOptions, AgentRunResult, AgentStreamingCallbacks, ToolChoiceMode,
#          ToolEventPayload, IClaudeAgentSDKClient, AttachmentPayload, RuntimeContext,
#          get_or_create_workspace, create_user_mcp_server, create_necklace_mcp_server
#          to application layers.
# [Pos] package root in libs/claude_agent_kit
# [Sync] 2026-05-09: re-export necklace live-context MCP server factory.

"""Claude Agent Kit — Python port of the TypeScript ClaudeAgentRunner module.

Provides a streaming interface for running the Claude Code agent with
tool-confirmation support, session persistence, and rich callback hooks.

Translated from TypeScript source at:
  glide-the/claude-agent-next-kit → app/lib/claude-agent-kit

Key exports
-----------
ClaudeAgentRunner
    Main runner.  Call ``runner.run_streaming(opts, callbacks)`` to start a
    streaming agent session.

create_agent_runner
    Factory shortcut for ``ClaudeAgentRunner()``.

AgentRunOptions / AgentRunResult
    Input/output dataclasses for ``run_streaming``.

AgentStreamingCallbacks
    Dataclass that groups all streaming event callbacks.

ToolEventPayload
    Payload passed to ``on_tool_event`` callbacks.

SimpleClaudeAgentSDKClient
    Thin ``claude_agent_sdk.query`` adapter.  Swap it out to inject a custom
    transport in tests.

IClaudeAgentSDKClient
    Abstract base class / interface that custom clients must implement.

create_user_mcp_server
    Factory for the 'user' MCP server that exposes the ``touch_animation``
    tool (and any future user-interaction tools) to the Claude agent runtime.

create_necklace_mcp_server
    Factory for the 'necklace' MCP server that exposes read-only live-context
    tools for current pet hardware/location/action data.
"""

from .messages import AttachmentPayload, RuntimeContext, build_user_message_content
from .server import (
    ClaudeAgentRunner,
    SimpleClaudeAgentSDKClient,
    create_agent_runner,
    create_necklace_mcp_server,
    create_user_mcp_server,
    get_or_create_workspace,
)
from .types import (
    AgentRunOptions,
    AgentRunResult,
    AgentStreamingCallbacks,
    IClaudeAgentSDKClient,
    ToolChoiceMode,
    ToolEventPayload,
)

__all__ = [
    # Runner
    "ClaudeAgentRunner",
    "create_agent_runner",
    # Client
    "SimpleClaudeAgentSDKClient",
    "IClaudeAgentSDKClient",
    # Options / result
    "AgentRunOptions",
    "AgentRunResult",
    # Callbacks & events
    "AgentStreamingCallbacks",
    "ToolChoiceMode",
    "ToolEventPayload",
    # Message building
    "AttachmentPayload",
    "RuntimeContext",
    "build_user_message_content",
    # Workspace
    "get_or_create_workspace",
    # MCP server factory
    "create_user_mcp_server",
    "create_necklace_mcp_server",
]
