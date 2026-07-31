# [Input] Aggregate exports from application/claude_agent and libs/claude_agent_kit.
# [Output] Provide ClaudeAgentThreadFactory, build_session_id, ClaudeAgentRunRequest,
#          AgentRunOptions, AgentRunResult, AgentStreamingCallbacks, ToolEventPayload,
#          AgentRunStatePool, SessionObserverRegistry, ToolConfirmationStore
#          to server.py route handlers and external consumers.
# [Pos] public-api node in backend/claude_agent
# [Sync] 2026-05-22: initial module creation for Ink & Memory claude_agent migration.
# [Sync] 2026-05-22: split into two layers — libs/claude_agent_kit (kit) and
#                    claude_agent/ (application); re-exports both via this __init__.

"""Ink & Memory Claude Agent module.

Public exports for use by ``server.py`` route handlers::

    from claude_agent import (
        ClaudeAgentThreadFactory,
        ClaudeAgentRunRequest,
        build_session_id,
    )

Kit layer is in ``libs/claude_agent_kit/``.
Application layer is in ``claude_agent/`` (this package).
"""

# Application layer
from claude_agent.observer import LoggingObserver, SessionLifecycleObserver, SessionObserverRegistry
from claude_agent.service import ClaudeAgentRunRequest, ClaudeAgentService
from claude_agent.thread_factory import ClaudeAgentThreadFactory, build_session_id
from claude_agent.thread_pool import AgentRunLifecycle, AgentRunState, AgentRunStatePool
from claude_agent.tool_confirmation_store import ToolConfirmationResult, ToolConfirmationStore

# Kit layer re-exports (convenience)
from libs.claude_agent_kit.types import (
    AgentRunOptions,
    AgentRunResult,
    AgentStreamingCallbacks,
    ToolEventPayload,
)
from libs.claude_agent_kit.server.agent_runner import ClaudeAgentRunner
from libs.claude_agent_kit.server.workspace import get_or_create_workspace, get_workspace_root

__all__ = [
    # Factory (primary entry point for server.py)
    "ClaudeAgentThreadFactory",
    "build_session_id",
    # Service & request
    "ClaudeAgentRunRequest",
    "ClaudeAgentService",
    # Types (from kit layer)
    "AgentRunOptions",
    "AgentRunResult",
    "AgentStreamingCallbacks",
    "ToolEventPayload",
    # Runner (from kit layer)
    "ClaudeAgentRunner",
    # Workspace (from kit layer)
    "get_or_create_workspace",
    "get_workspace_root",
    # Pool
    "AgentRunLifecycle",
    "AgentRunState",
    "AgentRunStatePool",
    # Observer
    "SessionLifecycleObserver",
    "SessionObserverRegistry",
    "LoggingObserver",
    # Tool confirmation
    "ToolConfirmationStore",
    "ToolConfirmationResult",
]
