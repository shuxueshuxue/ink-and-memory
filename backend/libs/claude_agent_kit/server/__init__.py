# [Input] None.
# [Output] Re-export ClaudeAgentRunner, create_agent_runner, SimpleClaudeAgentSDKClient,
#          session-file helpers, workspace lifecycle API, and MCP server factories to
#          application layers.
# [Pos] subpackage root in libs/claude_agent_kit/server
# [Sync] 2026-05-09: export necklace MCP server factory.
# [Sync] 2026-05-09: export memory MCP server factory.

"""Server subpackage for ClaudeAgentKit."""
from .agent_runner import ClaudeAgentRunner, create_agent_runner
from .simple_cas_client import SimpleClaudeAgentSDKClient

# MCP server factories — only available when mcp + Pawkeyland infra are installed.
# Ink & Memory does not use these MCP servers; imports are guarded so the core
# Runner/workspace/types surface remains importable without optional deps.
try:
    from .memory_mcp_server import create_memory_mcp_server
    from .mcp_server import create_user_mcp_server
    from .necklace_mcp_server import create_necklace_mcp_server
except Exception:  # noqa: BLE001
    create_memory_mcp_server = None  # type: ignore[assignment]
    create_user_mcp_server = None  # type: ignore[assignment]
    create_necklace_mcp_server = None  # type: ignore[assignment]
from .session_files import (
    SESSION_FILE_EXTENSION,
    get_projects_root,
    locate_session_file,
    normalize_session_id,
    parse_session_messages_from_jsonl,
    read_session_messages,
)
from .workspace import (
    get_workspace_root,
    init_workspace,
    get_or_create_workspace,
    resolve_safe_path,
    is_archive,
    extract_archive_in_skills,
)
from .workspace_file_sync import sync_skills_symlinks

__all__ = [
    "ClaudeAgentRunner",
    "create_agent_runner",
    "SimpleClaudeAgentSDKClient",
    # MCP server factory
    "create_user_mcp_server",
    "create_memory_mcp_server",
    "create_necklace_mcp_server",
    "SESSION_FILE_EXTENSION",
    "get_projects_root",
    "locate_session_file",
    "normalize_session_id",
    "parse_session_messages_from_jsonl",
    "read_session_messages",
    # Workspace lifecycle (WSK-01)
    "get_workspace_root",
    "init_workspace",
    "get_or_create_workspace",
    "resolve_safe_path",
    # Archive extraction (WSK-04)
    "is_archive",
    "extract_archive_in_skills",
    # Symlink sync (WSK-02)
    "sync_skills_symlinks",
]
