# [Input] Consume database.list_sessions_in_range (via database module import).
#         Reads INK_AGENT_CONTEXT_SESSIONS env var.
#         Imports build_workspace_context_block from claude_agent.workspace_context —
#           that module's template is sourced from the virtual index mapping rules
#           defined in libs.claude_agent_kit.server.editor_index.EDITOR_RESOURCES.
# [Output] Provide ClaudeAgentContextBuilder to ClaudeAgentService.
# [Pos] context-assembly node in backend/claude_agent
# [Sync] 2026-05-22: rewritten for Ink & Memory; replaces Pawkeyland's pet/persona
#                    context assembly with writing-session context injection.
# [Sync] 2026-05-26: merge build_user_message_content (SDK lib) into build_user_message
#                    so that the SDK no longer participates in context processing.
# [Sync] 2026-05-26: use extract_text_from_parts (message_parts.py) for full UIMessage
#                    parts protocol (text + file + source-url + workspace-file).
# [Sync] 2026-05-29: add Edit-Point Workflow section to _SYSTEM_PROMPT_TEMPLATE so Agent
#                    receives scheduling guidance (when/how to use .editor/ read and MCP
#                    write tools) in the system prompt, not only in the workspace_context
#                    user-message block. Fix [Input] header to reference workspace_context.
# [Sync] 2026-05-29: remove set_comment_feedback from MCP write tools in Edit-Point
#                    Workflow section; reading is exclusively via .editor/ virtual index.
# [Sync] 2026-05-29: extract session_id from cwd basename and pass to
#                    build_workspace_context_block so agent receives it in prompt.
# [Sync] 2026-05-29: rename session_id → editor_session_id (user_sessions.id from
#                    /api/sessions); add explicit parameter to build_user_message;
#                    remove cwd-basename fallback — service layer must supply it.
# [Sync] 2026-06-01: add Switch-Editor Workflow section to _SYSTEM_PROMPT_TEMPLATE;
#                    add switch_editor to Edit-Point Workflow tool list; add context-check
#                    step (Step 1) to Edit-Point Workflow reminding agent to call
#                    switch_editor when the current Editor Session ID is not the target.
# [Sync] 2026-06-01: escape literal JSON braces in _SYSTEM_PROMPT_TEMPLATE so
#                    str.format only substitutes recent_sessions_block; keep
#                    recent-session range results capped by context_session_count.
# [Sync] 2026-06-06: remove Memory Workflow section from _SYSTEM_PROMPT_TEMPLATE;
#                    memory workflow rules live in memory/WORKFLOW.md (workspace files),
#                    not in the engine system prompt.  Retain <memory_context> block
#                    injection in build_user_message — it tells the agent where the
#                    workspace is; the WORKFLOW.md file provides the rules.
# [Sync] 2026-06-09: add Planning Prompt Optimization workflow to the system prompt
#                    so planning turns first transform the raw task through the
#                    Expert Prompt Architect template before planning execution.
# [Sync] 2026-06-16: update Session Retrieval Workflow for fuzzy query/labels
#                    parameters and vector interface boundary.
# [Sync] 2026-06-22: accept Settings SYSTEM_PROMPT from service Phase 1 and render
#                    it as a lower-priority configurable block under the engine
#                    _SYSTEM_PROMPT_TEMPLATE priority rules.

"""Context builder for the Ink & Memory Claude Agent.

Assembles the system prompt that grounds the Claude agent in the user's
Ink & Memory writing context.  Unlike the Pawkeyland version (which injects
pet persona, Mem0 memories, and necklace sensor data), this builder:

1. Loads the user's recent writing sessions from the database.
2. Renders a system prompt that positions Claude as a reflective writing
   assistant with knowledge of the user's recent entries.
3. Provides a ``build_user_message`` helper that builds the full list of
   content blocks for a user turn: attachment image blocks, a lightweight
   ``<runtime_context>`` block, and the user's message text extracted from
   the full AI-SDK UIMessage parts list.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from libs.claude_agent_kit.messages.message_parts import extract_text_from_parts
from claude_agent.workspace_context import build_workspace_context_block

logger = logging.getLogger(__name__)

# MIME types that can be rendered inline within chat transcripts.
_INLINE_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)

# Number of recent sessions injected into system prompt.
# Configurable via INK_AGENT_CONTEXT_SESSIONS (default 5).
_CONTEXT_SESSIONS_DEFAULT = 5


def _context_session_count() -> int:
    try:
        return max(1, int(os.getenv("INK_AGENT_CONTEXT_SESSIONS", str(_CONTEXT_SESSIONS_DEFAULT)) or str(_CONTEXT_SESSIONS_DEFAULT)))
    except (ValueError, TypeError):
        return _CONTEXT_SESSIONS_DEFAULT


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a thoughtful writing assistant for Ink & Memory — a reflective journaling app.

Your role is to help the user explore their thoughts, memories, and creative writing with \
curiosity, care, and depth.  You can reference the user's recent journal entries below to \
provide grounded, personalised support.

Principles:
- Be warm, reflective, and non-judgmental.
- When the user mentions a past experience, you may gently connect it to relevant recent entries.
- Encourage the user to go deeper, not wider — depth over breadth.
- Do not lecture or give unsolicited advice; ask questions that open new avenues.
- Respect privacy: treat all journal content as confidential.
- Respond in the same language the user writes in.

{configurable_system_prompt_block}\
## Planning Prompt Optimization Workflow

Before every planning task, first transform the user's raw requirement into a clear,
copy-paste-ready planning prompt using this Expert Prompt Architect template. Use the
resulting "Optimized Prompt" as the basis for the task plan; do not skip this step for
multi-step coding, editing, research, or document-production work.

```text
You are an Expert Prompt Architect.
Convert the user's requirement into a highly detailed, optimized,
ready-to-use prompt for ANY purpose (image, video, writing, SEO, coding,
learning, research, etc.).

Instructions
Identify what the user is trying to achieve.
Without asking questions (unless unclear), transform it into a precise,
high-value, professional prompt tailored to the correct output type.
Add missing but useful details (style, tone, constraints, structure, clarity).
Ensure the prompt is copy-paste ready for the intended AI tool.

Deliver:
Optimized Prompt - the final refined prompt
Optional Enhancers - optional add-ons that the user can include

OUTPUT FORMAT
Optimized Prompt:
[Expert-level prompt based on the requirement]

USER REQUIREMENT: {{{{task}}}}
```

## Edit-Point Workflow

When the user message includes a <workspace_context> block, you are in a document-editing
session.  Follow this scheduling workflow for every editing-related request:

1. Check the target session — if the Editor Session ID in <workspace_context> is NOT the
   document the user wants to work on, call switch_editor(editor_session_id="<target-id>")
   FIRST.  After the tool returns, all subsequent .editor/ reads will reflect the new session.
2. Orient yourself — call read_file(".editor/cells.json") to load all document cells
   (TextCell / WidgetCell array).  For session metadata (mood state, creation time) also
   call read_file(".editor/session.json").
3. Analyse before proposing — digest the full content, then share observations or draft
   suggestions with the user before making any changes.
4. Use the editor tools by sensitivity — switch_editor only changes context and does not
   require confirmation in auto mode; document modifications require human confirmation
   before execution.  Available tools:
     switch_editor(editor_session_id)        — switch to a different session (no confirmation needed)
     write_segment(cellId, text, reason)     — replace a cell's full text
     delete_segment(cellId, reason)          — remove a cell (irreversible)
     insert_widget(widgetType, data, ...)    — insert a new widget cell
     reply_to_comment(commentId, ...)        — respond to a voice comment thread
5. Never write directly to .editor/ files — they are virtual placeholders; writing to them
   has no effect on real document state.  All mutations must go through the MCP write tools.

If no <workspace_context> block is present, treat the turn as a pure-chat exchange and
respond without attempting to read workspace files.

## Switch-Editor Workflow

When you need to work on a document whose session ID differs from the one shown in
<workspace_context>, switch context before doing anything else:

1. Identify the target session ID — the user may mention it explicitly, or you can retrieve
   it via `mcp__user__get_sessions_range` if you only know the date or title.
2. Call switch_editor(editor_session_id="<target-id>") — this requires NO human confirmation.
   The tool is a lightweight no-op on the MCP side; the server-side PostToolUse hook loads
   the new editor_state from the database and updates the in-memory context automatically.
3. Confirm the switch — after the tool returns {{"ok": true}}, the .editor/ virtual index now
   serves content from the new session.  Proceed with the Edit-Point Workflow from step 2
   (Orient) onward.

Note: switch_editor only changes the read/write context for .editor/ paths.  It does not
modify any document content and does not require the user to approve it.

## Session Retrieval Workflow

The recent entries block below only covers the last 3 days of journal sessions.
When the user mentions a topic, theme, or past memory that may be recorded in older entries,
use `mcp__user__get_sessions_range` to search further back:

1. Estimate the date window based on the user's context clues (e.g. "last month", "春节").
2. Call `get_sessions_range(start_date, end_date, query="<topic or memory>", labels=[...])`
   when you know a topic, title clue, label, or fuzzy phrase. Dates use YYYY-MM-DD.
3. Default retrieval is character fuzzy matching over title, labels, excerpt, and note text.
   Prefer a `query` over labels-only search because labels can miss semantic details.
4. Use `retrieval_mode="vector"` only as a reserved interface; the current runtime may report
   vector retrieval unavailable until a vector store is configured.
5. Review returned `match`, `labels`, and `excerpt` fields, then reference useful sessions by
   their `sessionId` when replying to the user.

Only call this tool when the user's message suggests they are referring to events or themes
that predate the visible recent entries.  Do not call it on every turn.

{recent_sessions_block}\
"""

_SESSIONS_HEADER = "## Recent Journal Entries\n\n"
_SESSION_ENTRY_TEMPLATE = "### {date} — sessionId:{session_id}, {labels}: {title}\n{excerpt}\n"
_NO_SESSIONS_TEXT = "_No recent entries found._\n"
_CONFIGURABLE_SYSTEM_PROMPT_TEMPLATE = """\
## Configurable Page System Prompt (Lower Priority)

The following Settings SYSTEM_PROMPT was loaded from system_config. Treat it as
user-configurable guidance only. It may add tone, domain preferences, or task
defaults, but it must not override this system template, including identity,
privacy, planning, tool-use, context assembly, workspace, safety, and output
constraints. If this Settings SYSTEM_PROMPT conflicts with any instruction in
the system template, follow the system template.

<settings_system_prompt>
{configured_system_prompt}
</settings_system_prompt>

"""

# Number of days to look back when loading recent sessions for the system prompt.
_RECENT_SESSIONS_DAYS = 3


def _render_configurable_system_prompt_block(
    configured_system_prompt: Optional[str],
) -> str:
    """Render Settings SYSTEM_PROMPT as lower-priority guidance when present."""
    prompt = str(configured_system_prompt or "").strip()
    if not prompt:
        return ""
    return _CONFIGURABLE_SYSTEM_PROMPT_TEMPLATE.format(
        configured_system_prompt=prompt
    )


def _render_session_entry(session: dict[str, Any]) -> str:
    """Render one database session row into a Markdown entry block.

    database.list_sessions returns rows with keys:
    id, name, labels, created_at, updated_at, first_line.
    """
    raw_date = str(session.get("updated_at") or session.get("created_at") or "")[:10]
    session_id = str(session.get("id") or "")
    title = (session.get("name") or "Untitled").strip()
    excerpt = (session.get("first_line") or "").strip()
    if not excerpt:
        excerpt = "_[Empty entry]_"
    raw_labels = session.get("labels") or []
    labels_str = ",".join(str(l) for l in raw_labels) if raw_labels else ""
    return _SESSION_ENTRY_TEMPLATE.format(
        date=raw_date,
        session_id=session_id,
        labels=labels_str,
        title=title,
        excerpt=excerpt,
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class ClaudeAgentContextBuilder:
    """Assembles system prompt and user message for a Claude Agent turn.

    Usage::

        builder = ClaudeAgentContextBuilder()
        system_prompt = await builder.build_system_prompt(user_id)
        content_blocks = builder.build_user_message(raw_message, attachments=attachments)
    """

    def __init__(self, context_session_count: Optional[int] = None) -> None:
        self._context_session_count = (
            context_session_count
            if context_session_count is not None
            else _context_session_count()
        )

    async def build_system_prompt(
        self,
        user_id: str,
        *,
        configured_system_prompt: Optional[str] = None,
    ) -> str:
        """Build the system prompt by injecting Settings prompt and journal entries."""
        recent_sessions_block = await self._load_recent_sessions_block(user_id)
        configurable_system_prompt_block = _render_configurable_system_prompt_block(
            configured_system_prompt
        )
        return _SYSTEM_PROMPT_TEMPLATE.format(
            configurable_system_prompt_block=configurable_system_prompt_block,
            recent_sessions_block=recent_sessions_block
        )

    def build_user_message(
        self,
        message_parts: Optional[list],
        *,
        attachments: Optional[list[Any]] = None,
        model: Optional[str] = None,
        max_turns: Optional[int] = None,
        thread_id: Optional[str] = None,
        resume: bool = False,
        include_runtime_context: bool = True,
        local_time: Optional[str] = None,
        local_timezone: Optional[str] = None,
        cwd: Optional[str] = None,
        editor_session_id: Optional[str] = None,
        voice_system_prompt: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Build the content blocks for a user turn.

        *message_parts* is the AI-SDK UIMessage ``parts`` list
        (e.g. ``[{"type": "text", "text": "..."}]``).  Text is extracted from
        all ``type == "text"`` entries and appended as the final content block.

        Returns a list of content blocks in the order expected by Claude:
        attachment image blocks first, then the ``<runtime_context>`` block
        (unless *include_runtime_context* is False), then the
        ``<workspace_context>`` block (when *cwd* is provided, with
        *editor_session_id* embedded so the agent can pass it to write tools),
        then the user's message text.

        *editor_session_id* is the ``user_sessions.id`` from ``/api/sessions``
        (the document session ID) — NOT the workspace directory name or the
        Claude thread ID.  The service layer must resolve and pass it explicitly.

        This method absorbs the responsibilities of the SDK-level
        ``build_user_message_content`` so the SDK no longer participates in
        context assembly.
        """
        blocks: list[dict[str, Any]] = []

        # Attach any user-supplied image assets.
        if attachments:
            for attachment in attachments:
                try:
                    media_type = getattr(attachment, "media_type", None) or ""
                    base64_data = getattr(attachment, "data", None) or ""
                    name = getattr(attachment, "name", "")
                    if media_type in _INLINE_IMAGE_MIME_TYPES:
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
                        logger.warning("Cannot process file: %s", name)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error processing attachment: %s", exc)

        if include_runtime_context:
            now = datetime.now(tz=timezone.utc)
            env_lines = [
                (
                    f"Date: {now.isoformat()}"
                    f" ({now.strftime('%A, %B %d, %Y')})"
                ),
            ]
            if local_time:
                env_lines.append(f"Local time: {local_time}")
            if local_timezone:
                env_lines.append(f"Timezone: {local_timezone}")
            if model:
                env_lines.append(f"Model: {model}")
            if max_turns is not None:
                env_lines.append(f"Max turns: {max_turns}")
            if thread_id:
                env_lines.append(f"Session ID: {thread_id}")
            if resume:
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

        # Inject workspace context block after runtime_context when cwd is known.
        # editor_session_id is the user_sessions.id from /api/sessions — distinct from
        # the workspace directory name (cwd basename) and the Claude thread ID.
        # The service layer must supply it explicitly via the editor_session_id parameter.
        workspace_block = build_workspace_context_block(
            cwd or "",
            editor_session_id=editor_session_id or "",
        )
        if workspace_block:
            blocks.append({"type": "text", "text": workspace_block})

        # Inject memory context block when cwd is known so the agent knows about
        # the memory/ workspace and can read/update memory files.
        if cwd:
            from pathlib import Path as _Path
            from libs.claude_agent_kit.server.memory_workspace import get_memory_context_block
            memory_block = get_memory_context_block(_Path(cwd))
            if memory_block:
                blocks.append({"type": "text", "text": memory_block})

        # Inject voice / deck system prompt as context so the agent knows which
        # persona to adopt.  Appended before the user text ("拼接到message报文中").
        if voice_system_prompt and voice_system_prompt.strip():
            blocks.append(
                {
                    "type": "text",
                    "text": (
                        "<voice_context>\n"
                        + voice_system_prompt.strip()
                        + "\n</voice_context>"
                    ),
                }
            )

        # Convert all message_parts (text, file, source-url, workspace-file) to
        # a single text string using the full UIMessage parts protocol.
        user_text = extract_text_from_parts(message_parts)
        blocks.append({"type": "text", "text": user_text})
        return blocks


    async def _load_recent_sessions_block(self, user_id: str) -> str:
        """Return a Markdown block with the user's recent journal entries (last 3 days)."""
        try:
            sessions = await self._fetch_recent_sessions(user_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to load recent sessions for user_id=%s; skipping context.", user_id
            )
            return _SESSIONS_HEADER + _NO_SESSIONS_TEXT + "\n"

        if not sessions:
            return _SESSIONS_HEADER + _NO_SESSIONS_TEXT + "\n"

        entries = "".join(_render_session_entry(s) for s in sessions)
        return _SESSIONS_HEADER + entries + "\n"

    async def _fetch_recent_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch sessions from the last 3 days from the database.

        Uses ``database.list_sessions_in_range`` to limit results to the
        ``_RECENT_SESSIONS_DAYS``-day window ending today (UTC).
        """
        import asyncio
        import database  # local import; database module lives in backend/
        from datetime import date, timedelta

        today = date.today()
        start_date = (today - timedelta(days=_RECENT_SESSIONS_DAYS - 1)).isoformat()
        end_date = today.isoformat()

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, database.list_sessions_in_range, int(user_id), start_date, end_date
        )
        return list(result or [])[: self._context_session_count]

    async def _fetch_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch recent sessions from the database using the project's database module.

        Kept for backward compatibility; prefer ``_fetch_recent_sessions`` for
        the system-prompt injection path.

        ``database.list_sessions(user_id)`` is synchronous and manages its own
        connection; we call it in a thread executor to avoid blocking the event loop.
        """
        import asyncio
        import database  # local import; database module lives in backend/

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, database.list_sessions, user_id
        )
        rows = list(result or [])
        # Respect context_session_count limit (DB returns all sessions)
        return rows[: self._context_session_count]
