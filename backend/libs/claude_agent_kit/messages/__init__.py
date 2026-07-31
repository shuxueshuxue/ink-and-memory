# [Input] None.
# [Output] Re-export build_user_message_content and RuntimeContext to server and application layers.
# [Pos] subpackage root in libs/claude_agent_kit/messages
# [Sync] 2026-05-01: initial Python port

"""Messages subpackage for ClaudeAgentKit."""
from .build_user_message_content import (
    AttachmentPayload,
    RuntimeContext,
    build_user_message_content,
)
from .message_parts import extract_text_from_parts

__all__ = [
    "AttachmentPayload",
    "RuntimeContext",
    "build_user_message_content",
    "extract_text_from_parts",
]
