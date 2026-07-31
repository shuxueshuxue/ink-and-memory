> [Input] `backend/routers/claude_agent.py`, `backend/claude_agent/service.py`, `backend/claude_agent/context_builder.py`, `backend/claude_agent/thread_factory.py`, `backend/claude_agent/thread_pool.py`, `backend/libs/claude_agent_kit/types.py`
> [Output] Define the `assemble_context` lifecycle contract, context source order, filtering policy, failure handling, and test expectations for Claude Agent planning and execution turns.
> [Pos] context-design-doc in `docs/design/claude-agent`
> [Sync] 2026-05-28: cleaned duplicate migration headers and Pawkeyland-only context assumptions; aligned the design with Ink & Memory `thread_id`, `message_parts`, workspace-file attachments, and planning prompt optimization.
> [Sync] 2026-05-29: add existing_session / resume resolution design — `assemble_context` now loads `chat_thread` from DB, gates resume on `_has_usable_claude_resume` (contract-version check) + local JSONL file probe, derives `thread_id_for_agent` / `should_resume`; `_TurnExecution` gains `resume_existing_session` field; `_persist_turn` writes back `claude_session_id` + `agent_contract_version` so the DB self-heals across deployments.
> [Sync] 2026-06-09: `claude-agent-prompt-optimization.md` now exists as the planning prompt optimization contract; `context_builder.py` also carries the Expert Prompt Architect template for agent-side planning turns.
> [Sync] 2026-06-16: Session Retrieval Workflow now tells the Agent to pass `query` / `labels` into `mcp__user__get_sessions_range`; default retrieval is character fuzzy matching, while vector mode is an interface boundary only.
> [Sync] 2026-06-22: Phase 1 loads `system_config` before prompt/cwd assembly; Settings `system_prompt` is rendered as lower-priority configurable guidance under `_SYSTEM_PROMPT_TEMPLATE`, and `workspace_enabled=false` skips thread workspace initialization plus `cwd` / workspace context injection.

# Claude Agent Context Assembly Design

This document is the implementation contract for `ClaudeAgentService.assemble_context`.
It covers the Phase 1 context boundary only: what context can enter a turn, how it is ordered and filtered, what the method returns, and what must remain outside this stage.

Prompt optimization for planning turns is specified separately in [`claude-agent-prompt-optimization.md`](./claude-agent-prompt-optimization.md). That optimizer prepares the task text before `assemble_context`; it does not replace the runtime system prompt or workspace context described here. The same Expert Prompt Architect template is also embedded in `ClaudeAgentContextBuilder` so agent-side planning turns follow the contract even when upstream optimization is unavailable.

## 1. Scope

`assemble_context` is the single application-layer entry point that turns a validated `ClaudeAgentRunRequest` plus an `AgentRunState` into a `_TurnExecution` carrier for `execute_session`.

It owns:

- building or reusing the session `system_prompt`;
- loading `system_config` once per turn for Settings-backed prompt, workspace, sandbox network, full-access, and SDK env configuration;
- building the current turn's Claude content blocks from `message_parts` and attachments;
- resolving the working directory for the session;
- **loading `existing_session` from `chat_thread` DB row** and resolving resume eligibility (`_has_usable_claude_resume` + local JSONL file probe);
- **deriving `thread_id_for_agent` and `should_resume`** for `AgentRunOptions`;
- copying runtime controls into `AgentRunOptions`;
- creating the per-turn `_TurnContext` that stores queue, tool confirmation state, streaming dedup sets, reasoning state, and persistence buffers;
- returning a carrier that Phase 3 can execute without re-reading request context.

It does not own:

- HTTP authentication or thread ownership checks;
- prompt optimization LLM calls;
- runner creation or SDK process lifecycle;
- streaming callbacks, SSE frame emission, or persistence;
- tool execution, tool result interpretation, or manual approval UI;
- client-provided system prompts, untrusted history arrays, or ad hoc `conversation_id` routing.

## 2. Lifecycle Position

```mermaid
sequenceDiagram
    participant User
    participant Opt as Prompt Optimization
    participant API as Claude Agent API
    participant Factory as ThreadFactory
    participant State as AgentRunState
    participant Service as ClaudeAgentService
    participant Builder as ContextBuilder
    participant Runner as ClaudeAgentRunner

    User->>Opt: raw planning task
    Opt-->>API: optimized planning prompt as UIMessage text
    API->>API: auth, thread ownership, message validation, attachment sync
    API->>Factory: ClaudeAgentRunRequest
    Factory->>State: get_or_create(thread_id) + per-session lock
    Factory->>Runner: create or reuse runner
    Factory->>Service: assemble_context(request, state, queue, runner)
    Service->>Service: get_system_config(user_id)
    alt first turn or rebuilt state
        Service->>Builder: build_system_prompt(user_id, configured_system_prompt)
        Builder-->>Service: system prompt with Settings block + recent writing sessions
        Service->>State: cache system_prompt and mark initialized
    else Settings SYSTEM_PROMPT changed
        Service->>Builder: build_system_prompt(user_id, configured_system_prompt)
        Builder-->>Service: rebuilt system prompt
        Service->>State: replace cached system_prompt
    else initialized state
        Service->>State: reuse cached system_prompt
    end
    Service->>Builder: build_user_message(message_parts, attachments, runtime)
    Service->>State: cache cwd if workspace is initialized here
    Service-->>Factory: _TurnExecution(run_options, turn_context, runner)
    Factory->>Service: execute_session(execution)
```

The factory is responsible for session locking, runner caching, lifecycle observers, and final cleanup. `assemble_context` may receive an already-created runner because the current service carrier includes `runner`; the runner is opaque in this phase and must not be called here.

## 3. Inputs

| Input | Source | Required | Context role |
|---|---|---:|---|
| `request.user_id` | authenticated HTTP user | yes | Key for recent writing context lookup and persistence ownership. |
| `request.thread_id` | `/api/claude-agent/threads` | yes | Stable chat thread, Thread Session key, and workspace key after validation. |
| `request.message_parts` | Vercel AI SDK `UIMessage.parts` | yes for normal text turns | User goal, optimized planning prompt, file metadata, source URL metadata, and workspace-file metadata. |
| `request.attachments` | synced API attachments | no | Inline image content blocks when the media type can be sent to Claude. |
| `request.resume` | client request | no | Gate for resume eligibility; `True` enables the DB + file-system resume check. |
| `request.tool_choice` | client request | no | Tool policy copied into `AgentRunOptions`; valid modes are `auto`, `manual`, and `none`. |
| `request.model` | client request or server selection | no | Runtime context and SDK model override when allowed by server policy. |
| `request.max_turns` | server default or client request | no | SDK turn budget; defaults belong in config/env, not in route logic. |
| `request.cwd` | trusted internal/debug caller | no | Explicit workspace override. Production chat callers should omit it. |
| `state` | `AgentRunStatePool` | yes | Cross-turn cache for `system_prompt`, `cwd`, runner presence, lifecycle, and turn count. |
| `queue` | factory-owned `asyncio.Queue` | yes | Shared queue later used by Phase 3 callbacks. |
| `runner` | factory-owned runner cache | yes in current service signature | Passed through to `_TurnExecution`; not executed during assembly. |
| `existing_session` (DB) | `database.get_chat_thread(thread_id, user_id)` | internal | Loaded by `assemble_context`; provides `claude_session_id` and `agent_contract_version` for resume gating. |
| `system_config` (DB) | `database.get_system_config(user_id)` | internal | Loaded before prompt/cwd assembly; provides Settings SYSTEM_PROMPT, Workspace Mode, sandbox network policy, full-access approval mode, and user SDK env vars. |

## 4. Context Source Order

`assemble_context` must assemble context in this order so higher-trust, lower-volatility inputs stay stable and volatile turn data stays local to the current request.

1. **Validated identity and thread**
   The API route must authenticate the user, require `thread_id`, verify that the thread belongs to the user, and reject empty text before creating `ClaudeAgentRunRequest`.

2. **Task goal or optimized planning prompt**
   The final task text enters through `request.message_parts`. For planning tasks, the text should already be transformed by the Expert Prompt Architect flow in [`claude-agent-prompt-optimization.md`](./claude-agent-prompt-optimization.md). `assemble_context` treats that optimized text as the user turn payload and does not call the optimizer itself.

3. **Settings system prompt**
   `assemble_context` calls `database.get_system_config(user_id)` before building `state.system_prompt`. When `system_config.system_prompt` is non-empty, Service passes it to `ClaudeAgentContextBuilder.build_system_prompt(user_id, configured_system_prompt=...)`.

   The builder renders it as:

   ```text
   ## Configurable Page System Prompt (Lower Priority)
   ...
   <settings_system_prompt>
   ...Settings SYSTEM_PROMPT...
   </settings_system_prompt>
   ```

   Priority is explicit: `_SYSTEM_PROMPT_TEMPLATE` is the engine/system template and has higher priority than Settings SYSTEM_PROMPT. Settings text may add tone, domain preferences, or task defaults, but cannot override identity, privacy, planning, tool-use, context assembly, workspace, safety, or output constraints from the template. On conflict, the template wins.

   The normalized Settings SYSTEM_PROMPT used for the cached prompt is stored on `AgentRunState.system_config_system_prompt`. During a live Thread Session, if Settings SYSTEM_PROMPT changes, Phase 1 rebuilds `state.system_prompt`; otherwise it reuses the cached prompt.

   Fallback behavior:

   | Case | Behavior |
   |---|---|
   | Missing/empty `system_prompt` | Omit the configurable block; build the normal engine prompt. |
   | `get_system_config` failure | Log a warning; build the engine prompt without Settings SYSTEM_PROMPT and continue the turn. |
   | Settings/template conflict | Follow `_SYSTEM_PROMPT_TEMPLATE`; Settings block is lower priority by construction. |

4. **Historical writing context**
   On the first initialized turn for a state, `ClaudeAgentContextBuilder.build_system_prompt(user_id, configured_system_prompt=...)` loads recent writing sessions through `database.list_sessions_in_range`. Only sessions from the **last 3 days** are included in the system prompt. The rendered block is cached in `state.system_prompt` and reused until the state is rebuilt or Settings SYSTEM_PROMPT changes.

   Each entry in the recent sessions block uses the format:
   ```
   ### {date} — sessionId:{sessionId}, {labels}: {title}
   {excerpt}
   ```
   where `labels` is the comma-joined list of session labels (from `user_sessions.labels`), and `sessionId` allows the agent to reference a session when calling `mcp__user__get_sessions_range`.

   For sessions **older than 3 days**, the agent must call `mcp__user__get_sessions_range(start_date, end_date, query, labels)` to retrieve them on demand. The system prompt's Session Retrieval Workflow section explains that `query` uses default character fuzzy matching over title, labels, excerpt, and note text. `retrieval_mode="vector"` is currently only a reserved interface and may return unavailable until a vector store is configured.

5. **Rules and assistant behavior**
   Current behavior rules live in `ClaudeAgentContextBuilder`'s system prompt template. Future prompt assets must be loaded through the project's prompt/config pattern rather than embedded in route handlers.

6. **File memory and attachment context**
   When `system_config.workspace_enabled=true`, the API route may sync uploaded files into the thread workspace before `assemble_context`. Metadata is injected into `message_parts` as file/source/workspace-file parts, and inline-safe image attachments are passed through `request.attachments`. `build_user_message` converts these into Claude content blocks and readable file metadata.

   When `workspace_enabled=false`, the route must not initialize or sync a thread workspace for attachments. The turn remains chat-only; no workspace-file parts are injected.

7. **Runtime context**
   `build_user_message` inserts a lightweight `<runtime_context>` block before the user text. It may include date, local time, timezone, model, max turns, session ID, and resume status when those values are supplied by upstream code.

8. **Resume resolution (existing_session)**
   `assemble_context` loads the `chat_thread` DB row for `request.thread_id` to determine whether the Claude SDK session can be resumed.

   | Step | Logic |
   |---|---|
   | **Load** | `database.get_chat_thread(thread_id, user_id)` → `existing_session` |
   | **Contract check** | `_has_usable_claude_resume(existing_session)` — requires `claude_session_id` non-empty **and** `agent_contract_version == _AGENT_RUNTIME_CONTRACT_VERSION` |
   | **File probe** | `locate_session_file(projects_root, candidate_session_id)` — verifies the transcript JSONL exists locally; prevents `--resume` from causing CLI exit-1 on a fresh deployment or after CLI retention reaping |
   | **thread_id_for_agent** | `existing_claude_session_id` if all checks pass, else `None` (SDK allocates a new session) |
   | **should_resume** | `bool(request.resume and thread_id_for_agent is not None)` |

   `_AGENT_RUNTIME_CONTRACT_VERSION` is controlled by the `INK_AGENT_CONTRACT_VERSION` env var; bump it when the system prompt or tool set changes incompatibly.

9. **Workspace**
   Workspace lifecycle is controlled by `system_config.workspace_enabled`.

   | Mode | Required behavior |
   |---|---|
   | `workspace_enabled=true` | `assemble_context` calls `get_or_create_workspace(state.session_id, sandbox_enabled=True, sandbox_network_*)`, writes `state.cwd`, passes `cwd` into `build_user_message`, and sets `AgentRunOptions.cwd` to the thread workspace. |
   | `workspace_enabled=false` | `assemble_context` does **not** call `get_or_create_workspace`, ignores client `request.cwd`, clears cached `state.cwd`, passes `cwd=""` into `build_user_message`, and sets `AgentRunOptions.cwd=None`. |

   With `cwd=""`, `build_user_message` does not inject `<workspace_context>` or `<memory_context>`.

10. **Tool state**
   `tool_choice` is copied into `AgentRunOptions`. `_TurnContext` starts with empty confirmation/dedup/reasoning state for the turn. Existing pending tool confirmations must not leak into a new turn.

## 5. Filtering And Priority Rules

| Rule | Required behavior |
|---|---|
| Client system prompts | Do not accept or merge client-provided system prompt fields in the public HTTP contract. |
| Client history | Do not accept client-owned `history` or `chat_history` arrays as authoritative context. Persisted chat messages are read through server-owned storage APIs. |
| Message text | Extract text through the UIMessage parts protocol. Text parts remain the goal source; file/source/workspace-file parts become explicit metadata text. |
| Attachments | Inline image MIME types may become image blocks. Unsupported binary types are represented by metadata when available; otherwise log and omit the binary payload. |
| External facts | Do not prefetch arbitrary live data during assembly. Realtime facts must enter through explicit tools during Phase 3. |
| Historical context | If DB context cannot be loaded, degrade to a valid system prompt with the no-session fallback. Do not fail the turn for missing optional history. |
| Settings SYSTEM_PROMPT | Load only through `database.get_system_config(user_id)`. Treat as lower priority than `_SYSTEM_PROMPT_TEMPLATE`; omit when empty or unavailable. |
| Workspace override | Treat `request.cwd` as trusted/internal only when Workspace Mode is enabled. When `workspace_enabled=false`, ignore it and do not initialize a workspace. |
| Tool policy | Support `auto`, `manual`, and `none`; invalid values should be rejected before SDK execution. |
| Prompt optimization | Preserve the raw user task for audit upstream, but pass only the optimized planning prompt into `message_parts` when the turn is a planning task. |

## 6. Outputs

`assemble_context` returns `_TurnExecution` with:

| Output | Contents |
|---|---|
| `request` | Original validated `ClaudeAgentRunRequest`. |
| `state` | The active `AgentRunState` after any `system_prompt`, `cwd`, and `turn_context` writes. |
| `runner` | Opaque runner reference supplied by the factory. |
| `run_options` | `AgentRunOptions(thread_id=thread_id_for_agent, user_message, resume=should_resume, model, cwd, max_turns, tool_choice, system_prompt)`. `thread_id` is `None` on the first turn; the Claude SDK session ID on resume turns. `cwd=None` when Workspace Mode is disabled. |
| `turn_context` | New `_TurnContext(queue, confirmation_store, pending sets, reasoning state, collected_parts)`. |
| `resume_existing_session` | The `chat_thread` DB row when the session is being resumed; `None` on the first turn. Carried to Phase 3 for diagnostic / persistence use. |

State side effects:

- `state.system_prompt` is built once per fresh state and reused while `state.is_context_initialized` is true unless Settings SYSTEM_PROMPT changes.
- `state.system_config_system_prompt` records the Settings SYSTEM_PROMPT value used for the cached system prompt.
- `state.cwd` is written when Workspace Mode is enabled and workspace initialization is needed; it is cleared when Workspace Mode is disabled.
- `state.turn_context` is replaced every turn.
- The current implementation keeps `run_options` in `_TurnExecution`; do not assume `state.run_options` is populated unless a future change explicitly adds that mirror.

## 7. Failure Handling

| Failure | Handling contract |
|---|---|
| Missing or unauthorized `thread_id` | API route rejects before `assemble_context`. |
| Invalid session/workspace key | Factory or workspace layer rejects before SDK execution; no context should be persisted. |
| Empty user text | API route rejects before context assembly. Attachment-only turns must still provide file/source/workspace metadata text. |
| DB session lookup failure (`get_chat_thread`) | Log warning, set `existing_session = None`; treat as first turn — resume is skipped, no turn failure. |
| `_has_usable_claude_resume` returns False | Fall through to `thread_id_for_agent = None` silently; SDK allocates a fresh session. |
| Local JSONL file missing (`locate_session_file` returns None) | Log warning with `stale_claude_session_id`; set `resume_existing_session = None`; SDK allocates a fresh session; `_persist_turn` will write the new `claude_session_id` to heal the DB row. |
| `_AGENT_RUNTIME_CONTRACT_VERSION` mismatch | `_has_usable_claude_resume` returns False; fall through to a fresh session. |
| Workspace initialization failure | Fail the turn before SDK execution; cleanup must leave the state idle and without stale `turn_context`. |
| Unsupported attachment media | Log and continue with available metadata; do not inject unreadable binary data as text. |
| `get_system_config` failure | Log warning, use default agent settings, build system prompt without Settings SYSTEM_PROMPT, and keep Workspace Mode enabled by default for backward compatibility. |
| Workspace Mode disabled | Skip workspace initialization and attachment workspace sync; continue the chat turn with `cwd=None`. |
| Prompt optimizer unavailable | Planning layer should fall back to the raw task or a policy-defined retry path before calling `assemble_context`; this method should not block waiting for optimizer recovery. |
| Tool confirmation leak | Factory cleanup must cancel pending confirmations and clear `state.turn_context` when the stream ends or disconnects. |

## 8. Boundary Conditions

- Same `thread_id` calls are serialized by the factory lock; different threads remain isolated.
- Destroyed states are rebuilt through `AgentRunStatePool.get_or_create`; rebuilt states must rebuild `system_prompt` and workspace state as needed.
- `state.system_prompt` cache is intentionally independent of persisted chat history. Updating recent journal context requires state rebuild or explicit invalidation.
- Updating Settings SYSTEM_PROMPT does not require process restart; Phase 1 compares the current config value against `state.system_config_system_prompt` and rebuilds the cached prompt when it changes.
- `message_parts=None` produces a valid content-block list with runtime context and empty text, but public routes should reject empty user-facing text before that point.
- `request.cwd` can cause context to run outside the default workspace only when Workspace Mode is enabled and a trusted internal/debug caller provides it. Keep it out of public UI flows unless a trusted admin/debug policy is in place.
- **Cross-environment resume safety**: `chat_thread.claude_session_id` is durable in DB, but the SDK transcript JSONL lives in the local CLI runtime at `~/.claude/projects/<cwd-encoded>/<session_id>.jsonl`. After a fresh deployment or CLI retention reaping, the DB row still points at a stale `claude_session_id`; `assemble_context` probes the filesystem before committing to `--resume`. On a miss, the DB self-heals after `_persist_turn` writes the freshly captured `claude_session_id`.
- **Contract version gating**: `_AGENT_RUNTIME_CONTRACT_VERSION` (env `INK_AGENT_CONTRACT_VERSION`) must be bumped whenever the system prompt, MCP tool set, or SDK interaction changes incompatibly with existing transcripts. The check prevents old transcripts from being resumed with a mismatched runtime.

## 9. Testability Requirements

Coverage should stay focused on the contracts above:

- `ClaudeAgentContextBuilder.build_system_prompt` includes the writing assistant role, recent entries, session count cap, no-session fallback, and DB-error fallback.
- `ClaudeAgentContextBuilder.build_system_prompt(..., configured_system_prompt=...)` renders non-empty Settings SYSTEM_PROMPT inside a lower-priority block and omits the block for empty config.
- `build_user_message` preserves block order: image attachments, runtime context, final user text/metadata.
- `assemble_context` builds `system_prompt` once per fresh state and reuses it on subsequent turns.
- `assemble_context` passes Settings SYSTEM_PROMPT from `get_system_config` into `build_system_prompt`, and rebuilds the cached prompt when that config changes.
- `assemble_context` initializes workspace and passes `cwd` only when `workspace_enabled=true`.
- When `workspace_enabled=false`, `assemble_context` does not call `get_or_create_workspace`, clears `state.cwd`, and passes `AgentRunOptions.cwd=None`.
- `assemble_context` copies `tool_choice`, `model`, `max_turns` into `AgentRunOptions`.
- **Resume path**: when `request.resume=True` and `existing_session` has a matching contract version and the JSONL file exists locally, `run_options.thread_id` equals the stored `claude_session_id` and `run_options.resume=True`.
- **No-resume path (first turn)**: `run_options.thread_id=None`, `run_options.resume=False` when `existing_session` is absent or `_has_usable_claude_resume` returns False.
- **File-probe miss**: when `locate_session_file` returns None for a otherwise valid `existing_session`, the method falls back to `thread_id_for_agent=None` and logs a warning.
- **Contract version mismatch**: when `existing_session.agent_contract_version` differs from `_AGENT_RUNTIME_CONTRACT_VERSION`, resume is skipped.
- **DB load failure**: when `get_chat_thread` raises, `assemble_context` does not fail the turn; it proceeds as a first turn.
- `_TurnContext` starts clean each turn and does not reuse confirmation or reasoning state.
- `_TurnExecution.resume_existing_session` is the DB row when resuming, `None` otherwise.
- Planning prompt optimization tests should assert that optimized prompt text enters through `message_parts`, while `assemble_context` remains optimizer-agnostic.
- Failure tests should cover DB fallback, invalid session ID, workspace initialization failure, unsupported attachment media, and cleanup after cancellation.

## 10. Implementation Checklist

- [ ] Validate auth, thread ownership, and non-empty text before constructing `ClaudeAgentRunRequest`.
- [ ] Run Expert Prompt Architect optimization before planning turns and store the result as UIMessage text.
- [ ] Keep raw user task available upstream for audit or UI comparison.
- [ ] Build `system_prompt` only through `ClaudeAgentContextBuilder`.
- [x] Load Settings SYSTEM_PROMPT through `get_system_config` and render it as lower-priority configurable guidance. *(2026-06-22)*
- [ ] Guard recent-session count through `INK_AGENT_CONTEXT_SESSIONS`.
- [ ] Convert UIMessage parts with `extract_text_from_parts` semantics.
- [ ] Sync attachments to workspace before context assembly and inject workspace-file parts.
- [ ] Keep unsupported binary payloads out of prompt text.
- [ ] Resolve `cwd` without hard-coded local paths.
- [x] Skip workspace initialization and `cwd` injection when `workspace_enabled=false`. *(2026-06-22)*
- [x] **Load `chat_thread` row from DB and call `_has_usable_claude_resume` before building `AgentRunOptions`.** *(2026-05-29)*
- [x] **Probe local JSONL via `locate_session_file` before committing to `--resume`.** *(2026-05-29)*
- [x] **Set `run_options.thread_id = thread_id_for_agent` (None on first turn) and `run_options.resume = should_resume`.** *(2026-05-29)*
- [x] **Carry `resume_existing_session` in `_TurnExecution`.** *(2026-05-29)*
- [ ] Create a fresh `_TurnContext` for every turn.
- [ ] Copy tool mode into `AgentRunOptions` and start with no pending confirmations.
- [ ] Keep SDK calls and SSE callbacks out of `assemble_context`.
- [ ] Clear `turn_context` and pending confirmations on completion, error, or disconnect.
- [ ] Add or update tests whenever a new context source, priority rule, or failure path is introduced.
