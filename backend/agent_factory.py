#!/usr/bin/env python3
# [Input] Consume claude_agent package factory export.
# [Output] Provide a shared ClaudeAgentThreadFactory singleton for FastAPI routers and server lifecycle.
# [Pos] backend singleton factory entrypoint
# [Sync] 2026-05-25: extracted Claude Agent factory creation from backend/server.py.

from claude_agent import ClaudeAgentThreadFactory

claude_agent_thread_factory = ClaudeAgentThreadFactory()
