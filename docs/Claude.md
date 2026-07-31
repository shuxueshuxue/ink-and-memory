# Claude Agent — Business Usage Guide

This document describes how the Claude-agent service is used in **Ink & Memory** and the
rules that govern its integration.  Read this before modifying any Deck, editor-chat, or
agent-session code.

---

## What is the Claude-agent service?

The Claude-agent service (`POST /api/claude-agent`) is a streaming SSE endpoint that runs
a stateful, multi-turn conversation with Claude (via the Claude Code SDK).  Each
conversation is tied to a **thread** (`chat_thread` row in the database), identified by a
`thread_id`.

Threads persist across sessions.  The agent can use MCP tools (file read/write, workspace
navigation, etc.) and receives context such as the current editor state.

---

## Where is it used?

### 1. Chat view (full experience)

`ChatPanel` + `ChatView` provide the full-featured chat interface with sidebar, tool
call UI, file attachments, and message history.  The `voiceSystemPrompt` prop is forwarded
as `systemPrompt` in the request body, so the agent responds in the persona of the active
Deck voice.

### 2. Inline Deck chat (Writing view)

When a user types `@` in the editor and selects a Deck voice, a `ChatWidgetUI` is
inserted at the cursor.  **This widget talks to the same claude-agent service** — it is
NOT a separate lighter-weight endpoint.

Key rules:
- The voice's `system_prompt` (stored in `voiceConfig.tagline` inside `ChatWidgetData`)
  **must always be forwarded** as `systemPrompt` in the request body.
- The widget uses the same `thread_id` that was created for the voice via
  `POST /api/claude-agent/threads`.
- Voice-bound threads initialize procedural Memory through
  `POST /api/workspace/memory-init` after `voice.thread_id` is known. The
  endpoint reads `voices.memory_workspace_config`; the client does not upload
  prompt contents directly.
- **No automatic navigation** to the Chat page occurs when `@` is used.  The user stays
  in the Writing view.  The "Chat →" button in the widget is the opt-in path to the full
  Chat view.

---

## System Prompt Injection Rules

Every request to `/api/claude-agent` that originates from a Deck voice interaction
**must** include:

```jsonc
{
  "systemPrompt": "<voice.system_prompt>"
}
```

This applies to both the full Chat view (`ChatPanel.voiceSystemPrompt`) and the inline
widget (`ChatWidgetUI` sends `data.voiceConfig.tagline`).

Omitting the system prompt causes the agent to respond without persona context, which
breaks the Deck voice experience.

---

## Thread Lifecycle

1. Thread creation: `POST /api/claude-agent/threads` → `{ thread_id }`
2. Thread is stored in `voice.thread_id` (lazily, on first use).
3. Procedural Memory initialization: `POST /api/workspace/memory-init` with
   `{ "sessionId": thread_id, "threadId": thread_id }`.
4. All messages to that voice use the same `thread_id` — history is preserved.
5. The inline widget and the full Chat view share the same thread; both reflect the
   same conversation.

---

## Do Not Do

- ❌ Do not replace the claude-agent call with `chatWithVoice` (polycli endpoint) for
  Deck interactions.  `chatWithVoice` is stateless and does not support tools or history.
  It is reserved for the Comments chat feature only.
- ❌ Do not auto-navigate to the Chat view when the user selects a voice via `@`.
  The interaction must remain inline in the editor.
- ❌ Do not strip or omit the `systemPrompt` field from Deck voice messages.
- ❌ Do not make `/api/claude-agent/threads` initialize Memory. Thread creation
  creates only `chat_thread`; Memory belongs to the workspace file interface.
- ❌ Do not copy prompt templates from project `.claude/memory/` into thread
  workspaces at runtime. Use `voices.memory_workspace_config`.
