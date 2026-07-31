# Deck × Claude-Agent Integration Design

## Overview

Each **Voice** inside a Deck can be associated with a persistent **Claude-agent thread**
(`thread_id`).  When a user types `@` in the Writing view and selects a voice from the
agent picker, an **inline chat widget** is inserted at the cursor position.  The widget
communicates directly with the Claude-agent service — the user stays in the Writing view
and the conversation happens inline, without navigating to the Chat page.

The voice's **system prompt** (`voiceConfig.systemPrompt`) is concatenated into every
message request sent to `/api/claude-agent` via the `systemPrompt` request field, so the
agent always responds in character as the selected Deck voice.

Each voice-bound thread also owns a procedural Memory workspace. After the thread is
created and persisted to `voice.thread_id`, the frontend explicitly calls
`POST /api/workspace/memory-init`. That file-interface endpoint reads
`voices.memory_workspace_config` and writes `/memory/` resources for the thread. The
thread creation endpoint does not initialize Memory.

Optionally, a **"Chat →"** button in the widget lets the user open the full Chat view
for a richer experience (tool calls, file attachments, history sidebar).

---

## Data Model

### `voices` table (backend)

A nullable column links each voice to a Claude-agent thread:

```sql
ALTER TABLE voices ADD COLUMN thread_id TEXT;
ALTER TABLE voices ADD COLUMN memory_workspace_config TEXT;
```

| Column | Type | Notes |
|---|---|---|
| `thread_id` | TEXT | UUID of the linked `chat_thread` row, or NULL |
| `memory_workspace_config` | TEXT | JSON config for procedural Memory prompt files and state-file requirements |

The `thread_id` is populated lazily on the first `@`-select of a voice.

---

## API Changes

### `PUT /api/voices/{voice_id}`

`VoiceUpdateRequest` gains an optional `thread_id` field so the frontend can persist the
thread association after creation:

```json
{ "thread_id": "<uuid>" }
```

### `POST /api/claude-agent/threads` (existing)

Unchanged – the frontend calls this to create a new thread and receives `{ thread_id }`.
It does not create `/memory/`.

### `POST /api/workspace/memory-init`

Called after `voice.thread_id` is known and before the first voice-bound agent message:

```json
{ "sessionId": "<thread_id>", "threadId": "<thread_id>" }
```

The backend verifies ownership, resolves `voices.memory_workspace_config`, and writes the
procedural Memory files into `{AGENT_CWD}/{thread_id}/memory/`.

### `POST /api/claude-agent` (existing)

The inline widget sends messages here.  The voice system prompt is forwarded as
`systemPrompt` in the request body so the agent responds in character:

```jsonc
{
  "id": "<thread_id>",
  "resume": true,
  "message": { "id": "…", "role": "user", "parts": [{ "type": "text", "text": "…" }] },
  "chatModel": { "provider": "anthropic", "model": "claude-sonnet-4-20250514" },
  "toolChoice": "auto",
  "attachments": [],
  "systemPrompt": "<voice.system_prompt>",   // ← injected per request
  "allowedAppDefaultToolkit": [],
  "allowedMcpServers": {}
}
```

---

## Frontend Flow

### 1. `@`-Agent Picker in the Writing View

```
User types "@" → AgentDropdown opens (enabled voices from Deck system)
   ↓
User selects a voice
   ↓
handleAgentSelect():
  1. Insert inline ChatWidgetUI into the editor (shows "Creating thread…")
  2. Call POST /api/claude-agent/threads → get thread_id (async)
  3. Persist voice.thread_id
  4. Call POST /api/workspace/memory-init for that thread
  5. Update widget data with thread_id
  6. User stays in the Writing view — no navigation occurs
```

### 2. ChatWidgetUI — Inline Chat Widget

The widget renders directly in the editor at the `@`-insertion point:

```
┌──────────────────────────────────────────────────────┐
│  🧠  Mirror                               [Chat →]   │
│  Ask anything…                                        │
├──────────────────────────────────────────────────────┤
│  [user bubble]  What do you notice in this text?      │
│  [agent bubble] I see patterns of …                  │
├──────────────────────────────────────────────────────┤
│  Message Mirror…                       [✈ send]      │
└──────────────────────────────────────────────────────┘
```

- **Inline send**: user types and presses Enter (or the send button).  The message is
  POST-ed to `/api/claude-agent` with the voice system prompt.  The SSE response is
  streamed and displayed inline with a blinking cursor.
- **Chat →**: opens the same thread in the full Chat view (sidebar, tools, history).
- **×** (hover): removes the widget from the editor.

The widget manages its own local message history (`InlineMessage[]`).  Messages are not
persisted to the editor state — they live in component state and survive view switches
while the Writing view remains mounted.

### 3. Deck Manager – Voice Chat Button

Each voice card inside `DeckEditorModal` gets a **Chat** button.  When clicked it opens
the full Chat view (same `handleOpenChatThread` path), regardless of whether a thread
already exists.

---

## Sequence Diagram

```
User (Writing View)         App.tsx              Claude-Agent API       Workspace API
       │                      │                        │                      │
       │  types "@Mirror"     │                        │                      │
       │─────────────────────►│                        │                      │
       │  voice selected      │                        │                      │
       │                      │ POST /threads ─────────►│                      │
       │                      │◄──── thread_id ─────────│                      │
       │                      │ POST /memory-init ────────────────────────────►│
       │                      │◄──────────────────── ok ──────────────────────│
       │  ChatWidgetUI inserted (thread_id set)         │                      │
       │   User stays in Writing view                   │                      │
       │                      │                        │                      │
       │  [types message]     │                        │                      │
       │  [presses Enter]     │                        │                      │
       │  ChatWidgetUI ────── POST /claude-agent ───────►│                      │
       │                      │     (systemPrompt=voice.system_prompt)        │
       │  SSE stream ◄────────│◄────── text-delta ──────│                      │
       │  inline display      │                        │                      │
       │                      │                        │                      │
       │  [Chat →] clicked    │                        │                      │
       │─────────────────────►│                        │                      │
       │                      │ requestedThreadId=id   │                      │
       │                      │ currentView='chat'     │                      │
```

---

## Component Responsibilities

| Component / Function      | Responsibility                                              |
|---------------------------|-------------------------------------------------------------|
| `AgentDropdown`           | List enabled voices; fire `onSelect(voiceName, voiceConfig)` |
| `handleAgentSelect`       | Insert widget, ensure thread + Memory workspace async — **no navigation** |
| `ChatWidgetUI`            | Inline chat UI; explicit memory-init before SSE send; system prompt injection |
| `ChatWidget` (engine)     | Widget data model; stores `voiceName`, `voiceConfig`, `threadId` |
| `handleOpenChatThread`    | Navigate to Chat view (used by "Chat →" and Deck Manager)    |

---

## Removed / Changed Behaviour

| Old Behaviour                                      | New Behaviour                                      |
|----------------------------------------------------|----------------------------------------------------|
| `handleAgentSelect` auto-navigated to Chat view    | User stays in Writing view; inline chat in widget  |
| `ChatWidgetUI` was a static link card              | `ChatWidgetUI` has a full inline chat interface    |
| Voice system prompt was forwarded only for Chat view | System prompt forwarded on every inline message   |
