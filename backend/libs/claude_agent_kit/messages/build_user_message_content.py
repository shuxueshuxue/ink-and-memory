# [Input] None — standalone content-block builder.
# [Output] Provide build_user_message_content and RuntimeContext to server/agent_runner.
# [Pos] utility node in libs/claude_agent_kit/messages
# [Sync] 2026-05-09: trim per-turn pet chat runtime context to remove generic file workspace instructions.
# [Sync] 2026-05-10: keep the SDK runtime_context block enabled by default, with an opt-out for specialized callers.
# [Sync] 2026-05-10: enrich SDK runtime_context with app-provided local time and timezone.

"""Build user message content blocks.

Python translation of TypeScript:
  messages/messages/build-user-message-content.ts
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# MIME types that can be rendered inline within chat transcripts
INLINE_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)


@dataclass
class AttachmentPayload:
    """Attachment payload for user-supplied assets such as images or documents.

    Maps to TypeScript ``AttachmentPayload`` in messages/types/messages.ts.
    """

    name: str
    media_type: str
    data: str  # base64-encoded binary data
    id: Optional[str] = None


@dataclass
class RuntimeContext:
    """Runtime context injected from the agent runner so the model is aware
    of the execution environment.

    Maps to TypeScript ``RuntimeContext`` in build-user-message-content.ts.
    """

    cwd: Optional[str] = None
    model: Optional[str] = None
    max_turns: Optional[int] = None
    thread_id: Optional[str] = None
    resume: bool = False
    include_runtime_context: bool = True
    local_time: Optional[str] = None
    local_timezone: Optional[str] = None


def _decode_base64_text(value: str) -> str:
    """Decode a base64-encoded UTF-8 string."""
    return base64.b64decode(value).decode("utf-8")


def build_user_message_content(
    prompt: str,
    attachments: Optional[list[AttachmentPayload]],
    runtime_context: Optional[RuntimeContext] = None,
) -> list[dict[str, Any]]:
    """Construct the content blocks for a user message.

    Combines the prompt text with any attachments into the order expected by
    Claude: context blocks first, attachments, then the user's message.

    Maps to TypeScript ``buildUserMessageContent`` in
    messages/messages/build-user-message-content.ts.
    """
    blocks: list[dict[str, Any]] = []

    # Attach any user-supplied assets (images, documents, etc.).
    if attachments:
        for attachment in attachments:
            try:
                media_type = attachment.media_type
                base64_data = attachment.data

                if media_type in INLINE_IMAGE_MIME_TYPES:
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data,
                            },
                        }
                    ) 
                else:
                    logger.warning("Cannot process file: %s", attachment.name)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error processing file: %s", exc)

    include_runtime_context = (
        runtime_context is None or runtime_context.include_runtime_context
    )
    if include_runtime_context:
        # Inject only lightweight runtime metadata. Pet chat memory/persona/status
        # context is already carried in the prompt assembled by the application layer.
        now = datetime.now(tz=timezone.utc)
        env_lines = [
            (
                f"Date: {now.isoformat()}"
                f" ({now.strftime('%A, %B %d, %Y')})"
            ),
        ]
        if runtime_context:
            if runtime_context.local_time:
                env_lines.append(f"Local time: {runtime_context.local_time}")
            if runtime_context.local_timezone:
                env_lines.append(f"Timezone: {runtime_context.local_timezone}")
            if runtime_context.model:
                env_lines.append(f"Model: {runtime_context.model}")
            if runtime_context.max_turns is not None:
                env_lines.append(f"Max turns: {runtime_context.max_turns}")
            if runtime_context.thread_id:
                env_lines.append(f"Session ID: {runtime_context.thread_id}")
            if runtime_context.resume:
                env_lines.append("Resumed conversation: yes")

        blocks.append(
            {
                "type": "text",
                "text": (
                    "<runtime_context>\n"
                    + "\n".join(env_lines)
                    + "\n</runtime_context>"
                ),
            }
        )

    # Always append the raw prompt text at the end.
    blocks.append({"type": "text", "text": prompt})

    return blocks
