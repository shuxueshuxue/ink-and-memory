# Agent Interaction Patterns

This document describes the interaction patterns and responsibilities for all AI-agent
features in **Ink & Memory**.  Read this when adding or modifying any agent-driven UI.

---

## Agent Entry Points

| Entry Point              | Service Used       | Navigation | System Prompt Source             |
|--------------------------|--------------------|------------|----------------------------------|
| `@`-picker in editor     | claude-agent       | Stay in Writing view | `voice.system_prompt` (inline widget) |
| "Chat →" button in widget | claude-agent      | Open Chat view | `voice.system_prompt` (forwarded) |
| Deck Manager "Chat" btn  | claude-agent       | Open Chat view | `voice.system_prompt`            |
| Comments chat            | chatWithVoice (polycli) | Stay inline | voice ID lookup on backend  |

---

## Inline Deck Chat (Writing View)

### Trigger
User types `@` → `AgentDropdown` appears → user selects a voice.

### What happens
1. `handleAgentSelect` in `App.tsx` inserts a `ChatWidgetUI` at the cursor.
2. A Claude-agent thread is created asynchronously (`POST /api/claude-agent/threads`).
3. The thread is persisted to `voice.thread_id`.
4. The procedural Memory workspace is initialized explicitly (`POST /api/workspace/memory-init`).
5. The widget's `threadId` is updated once the thread exists.
6. **The user stays in the Writing view.**

### ChatWidgetUI responsibilities
- Maintain local `InlineMessage[]` state (not persisted to editor state).
- Before voice-bound sends, ensure `/memory/` exists via `/api/workspace/memory-init`.
- On each send: POST to `/api/claude-agent` with `systemPrompt = voiceConfig.tagline`.
- Read the SSE response stream (`text-delta` events) and display streaming text inline.
- Expose a **"Chat →"** button to open the full Chat view for the same thread.

### System prompt contract
`voiceConfig.tagline` in `ChatWidgetData` stores the voice's `system_prompt`.  It is set
in `ChatWidget` constructor:

```ts
tagline: voiceConfig.systemPrompt || voiceConfig.tagline
```

Every `/api/claude-agent` POST from the inline widget **must** include:

```ts
systemPrompt: data.voiceConfig.tagline
```

---

## Full Chat View

### Trigger
- "Chat →" button in `ChatWidgetUI`
- "Chat" button in `DeckEditorModal` voice card
- Direct navigation to the chat view

### What happens
`handleOpenChatThread(threadId, voiceInfo)` in `App.tsx`:
1. Sets `requestedChatThreadId` and `activeChatVoice`.
2. Switches `currentView` to `'chat'`.
3. `ChatView` receives `requestedThreadId` and `activeVoice`.
4. `ChatPanel` receives `voiceSystemPrompt = activeVoice.systemPrompt`.

### System prompt contract
`ChatPanel` forwards `voiceSystemPrompt` as `systemPrompt` in every
`prepareSendMessagesRequest` body.

---

## Comments Chat

Powered by `chatWithVoice` (PolyCLI sync endpoint).  Stateless — no thread, no history.
Used exclusively by the Comments feature (`handleCommentChatSend`).  Do **not** use this
for Deck voice interactions.

---

## Adding a New Agent Entry Point

1. Decide: inline widget or full Chat view?
2. If inline: follow the `ChatWidgetUI` pattern — create/reuse a thread, POST to
   `/api/workspace/memory-init`, then POST to `/api/claude-agent` with `systemPrompt`,
   stream SSE response.
3. If full Chat view: call `handleOpenChatThread(threadId, voiceInfo)` in `App.tsx`.
4. Always pass the voice system prompt.  Never omit it.
5. Update this document and `docs/Claude.md`.

---

## SSE Stream Handling (inline widgets)

The `/api/claude-agent` endpoint emits Pawkeyland-aligned SSE events.  For inline
widgets that handle their own streaming (without `useChat`), the relevant events are:

| Event type      | Action                                          |
|-----------------|-------------------------------------------------|
| `text-delta`    | Append `event.delta` to the streaming buffer    |
| `finish`        | Commit accumulated text as an assistant message |
| `message-final` | Same as `finish` — commit accumulated text      |
| `error`         | Show error message; clear streaming state       |

All other event types (`tool-input-*`, `reasoning-*`, etc.) can be ignored by simple
inline widgets that do not display tool calls.
