> [Input] `backend/libs/claude_agent_kit/server/agent_runner.py`, Claude Code restored source `tools/SkillTool/constants.ts`, `backend/claude_agent/context_builder.py`, frontend tool confirmation flow.
> [Output] Claude-agent tool permission policy for `tool_choice` modes, sensitivity classes, and PreToolUse hook decisions.
> [Pos] permission-policy-doc in `docs/design/claude-agent`
> [Sync] 2026-06-09: initial standalone policy extracted from runner implementation and product rule: query-like tools are low-sensitivity; execution/write/interactive tools are high-sensitivity unless explicitly listed.
> [Sync] 2026-06-09: implementation note added for hook payload normalization (`tool_name`/`toolName`, `tool_input`/`toolInput`) and auto-mode retention of `Skill` in effective `allowed_tools`.
> [Sync] 2026-06-09: Settings-controlled `im_full_access_enabled` added; when enabled, exposed non-answer-form tools receive explicit PreToolUse allow after `.editor/` virtual-index redirects.
> [Sync] 2026-06-13: clarify separation from Claude Code Bash sandbox; per-thread
> workspace filesystem confinement is configured through `.claude/settings.json`,
> not by parsing shell paths in `PreToolUse`.
> [Sync] 2026-06-13: full-access mode now excludes AskUserQuestion-style tools;
> they still use frontend confirmation so answers can be collected.
> [Sync] 2026-06-14: built-in file/search tools are hard-denied outside the
> current thread workspace before full-access allow is considered.
> [Sync] 2026-06-21: Settings `sandbox_network_mode="disabled"` now hard-denies
> network tools before full-access and low-sensitivity allow decisions.
> [Sync] 2026-07-20: `EnterPlanMode` / `ExitPlanMode` added to the
> low-sensitivity auto-allow class (claude-plan §5.7); official `ExitPlanMode`
> ask-semantics deviation recorded in §3.
> [Sync] 2026-07-20: `TodoWrite` / `TaskCreate` / `TaskUpdate` / `TaskList` /
> `TaskGet` added to the low-sensitivity auto-allow class (claude-todo §5.7);
> `TaskUpdate` non-read-only deviation recorded in §3.
> [Sync] 2026-07-23: SandboxPermissionRequest — decision-chain step ②.5 added
> (network allowlist/open gate); `open` mode semantics changed to "ask every
> time". Decision order in §6 re-aligned with code order.
> [Sync] 2026-07-26: step ②.5 REMOVED — network policy is a system-level
> control enforced by Claude Code's own sandbox (sandbox.network via
> workspace.py); runtime asks arrive exclusively via the SDK can_use_tool
> channel (see `claude-agent-sandbox-network-permission-tool.md`). The
> PreToolUse decision chain returns to its pre-feature shape; `open` mode
> reverts to "unrestricted egress"; the network-variant confirmation card
> still exists but is only triggered by can_use_tool (`SandboxNetworkAccess`).

# Claude-Agent Permission Policy

This document is the source of truth for Claude-agent tool permission decisions.
It describes the product policy, not Claude Code's internal classifier.

## 1. Goals

- Avoid native Claude Code permission prompts when the backend has already made a safe product-level decision.
- Keep `tool_choice=auto` useful for low-risk query and navigation workflows.
- Route high-sensitivity actions through the frontend confirmation side-channel so the user sees and approves the exact tool input.
- Default unknown tools to high-sensitivity.

## 2. Modes

| Mode | Policy |
|---|---|
| `auto` | Low-sensitivity tools return explicit `permissionDecision:"allow"` from `PreToolUse`. High-sensitivity tools emit `tool-approval-request` and wait for frontend confirmation. |
| `manual` | All non-special tools go through frontend confirmation. `.editor/` virtual-index `Read` redirects still run because they only replace placeholder reads with a safe tempfile snapshot. |
| `none` | No tools are exposed; auto allow rules do not apply. |

When `system_config.im_full_access_enabled=true`, exposed tools bypass the sensitivity matrix and receive explicit `permissionDecision:"allow"` in `PreToolUse`, except answer-form tools (`AskUserQuestion`, `mcp__user__ask_user`), built-in file/search tools whose resolved path is outside the current thread workspace, and network tools when `sandbox_network_mode="disabled"`. Answer-form tools still go through frontend confirmation because the form is the only place where user answers are collected and merged into `updatedInput`; out-of-workspace file/search tools and disabled-network tools are hard-denied before full-access is considered. This setting is controlled from Settings → AI model configuration → 「应如何批准 IM」. `tool_choice="none"` still exposes no tools.

Settings `system_config.workspace_enabled=true` additionally enables the
per-thread Claude Code Bash sandbox described in
[`claude-agent-workspace-sandbox.md`](./claude-agent-workspace-sandbox.md).
That sandbox is a runtime filesystem boundary for Bash and child
processes. It is deliberately not implemented as a shell path parser in
`_pre_tool_use_hook`.

When `system_config.sandbox_network_mode="disabled"`, `_pre_tool_use_hook`
adds an execution-layer guard: `WebFetch`, `WebSearch`, and common Bash network
commands (`curl`, `wget`, `git fetch`, `npm install`, `python -m pip install`,
etc.) return explicit deny before full-access or low-sensitivity allow rules.

The `allowlist` / `open` modes are NOT enforced in this PreToolUse layer: they
configure Claude Code's own sandbox (`sandbox.network` written into per-thread
`.claude/settings.json` by `workspace.py`), and any runtime ask arrives via
the SDK `can_use_tool` channel (`SandboxNetworkAccess`), which routes through
the same frontend confirmation side-channel with
`confirmationKind="sandbox_network"` — see
`claude-agent-sandbox-network-permission-tool.md`. **[2026-07-26]**

## 3. Low-Sensitivity Tools

Low-sensitivity tools are query-like or context-selection operations with no direct content mutation.
Current auto-allow inventory:

| Tool class | Tool names / rule |
|---|---|
| Built-in read/search | `Read`, `Glob`, `Grep`, `LS`, `NotebookRead` only when resolved inside the current thread workspace; `TodoRead`, `WebFetch`, `WebSearch`, `BashOutput` |
| MCP resource query | `ListMcpResources`, `ReadMcpResource` |
| Workspace files area | `Read` / `Write` / `Edit` / `MultiEdit` only when the resolved target is inside `{cwd}/files/**` |
| Session query | `mcp__user__get_sessions_range` |
| Memory query | `mcp__memory__recall_shared_stories` |
| Necklace query | `mcp__necklace__*` names returned by `allowed_necklace_tool_names()` |
| Editor context switch | `mcp__editor__switch_editor` |
| Skill invocation | `Skill` |
| Plan Mode session state | `EnterPlanMode`, `ExitPlanMode` **[2026-07-20]** |
| Todo / task list session state | `TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` **[2026-07-20]** |
| Read-only Bash subset | `Bash` only when the command has no shell metacharacters and the first token is in the read-only/navigation allowlist (`ls`, `cd`, `pwd`, `echo`, `cat`, `head`, `tail`, `wc`, `find`, `which`, `type`, `date`, `whoami`, `id`, `groups`, `env`, `printenv`, `uname`, `hostname`) |

`switch_editor` is low-sensitivity because the MCP handler is a no-op and the PostToolUse hook only changes which existing editor session `.editor/` reads resolve to. It does not modify document content.

`Skill` is low-sensitivity because Claude Code exposes skills through the built-in `Skill` tool, whose job is to expand or run a named skill prompt. The exact tool name was confirmed in restored Claude Code source: `src/tools/SkillTool/constants.ts` exports `SKILL_TOOL_NAME = 'Skill'`. Do not use a broad `skill*` prefix. Allowing `Skill` does not allow later tool calls made by that skill; those calls are evaluated again by this policy.

Implementation detail: hook payloads are normalized before policy lookup. The runner accepts both Claude hook JSON keys (`tool_name`, `tool_input`) and adjacent SDK/frontend camelCase keys (`toolName`, `toolInput`) so a payload such as `{"toolName": "Skill"}` cannot fall through as an unknown tool. In `auto` mode, `Skill` is also retained in effective `allowed_tools` even if a caller passes a custom allowlist, because Claude Code's SkillTool has its own permission path that otherwise defaults to ask for some skill metadata.

`EnterPlanMode` / `ExitPlanMode` are low-sensitivity because both are session-state meta operations: neither mutates user content directly (`EnterPlanMode` is read-only; `ExitPlanMode` only flips the session back to execution). Classification name: `low_sensitivity_permission` via `_LOW_SENSITIVITY_QUERY_TOOL_NAMES` (claude-plan §5.7, 2026-07-20).

**Deviation record (2026-07-20) — official `ExitPlanMode` ask semantics downgraded.** In official Claude Code, `ExitPlanMode` runs `checkPermissions → ask`: an interactive human confirms the plan before execution resumes. This deployment has no TUI approval scenario; keeping ask semantics would pop a frontend confirmation on every plan exit and block the product's "plans flow automatically" requirement. Consequence: the model's self-authored plan enters execution without per-item human confirmation. Risk is bounded by (a) the workspace-boundary permission (`_apply_workspace_boundary_permission`), which hard-denies built-in file/search tools outside the thread workspace, and (b) high-sensitivity write tools (`Write`/`Edit`/`MultiEdit` outside `files/`, mutating `Bash`, editor MCP writes), which still route through the frontend confirmation side-channel. In `tool_choice="manual"` mode both tools keep the high-sensitivity confirmation path unchanged. Fallback: remove the two names from `_LOW_SENSITIVITY_QUERY_TOOL_NAMES` (or gate them behind a future Settings switch) to restore official ask semantics.

The five todo/task tools are low-sensitivity because all of them are session-state task-list operations: none mutates user content directly. `TodoWrite` is officially approval-free (an SDK default-allowed tool); `TaskCreate`/`TaskUpdate` write task JSON, but the write scope is confined by `CLAUDE_CONFIG_DIR` to the per-thread workspace `.claude-home/tasks/` directory — equivalent to session metadata. Classification name: `low_sensitivity_permission` via `_LOW_SENSITIVITY_QUERY_TOOL_NAMES` (claude-todo §5.7, 2026-07-20).

**Deviation record (2026-07-20) — `TaskUpdate` is not strictly read-only.** `TaskUpdate` can trigger `blockTask` bidirectional rewrites and `deleteTask` cascading deletion of task JSON files. This downgrade means task-list creation, mutation, and deletion proceed without per-item human confirmation. Risk is bounded by (a) the write scope being confined to the per-thread workspace `.claude-home/tasks/` directory (session metadata, not user content), and (b) high-sensitivity write tools, which still route through the frontend confirmation side-channel. In `tool_choice="manual"` mode all five tools keep the high-sensitivity confirmation path unchanged. Fallback: remove the five names from `_LOW_SENSITIVITY_QUERY_TOOL_NAMES` to restore confirmation gating.

## 4. High-Sensitivity Tools

High-sensitivity tools require frontend confirmation in `auto` and `manual` modes:

| Tool class | Examples |
|---|---|
| Execution / complex shell | `Bash` with pipes, redirects, substitutions, separators, unknown commands, or write side effects |
| Writes outside workspace files | `Write`, `Edit`, `MultiEdit` when the resolved path is outside `{cwd}/files/**` |
| Editor writes | `mcp__editor__write_segment`, `mcp__editor__delete_segment`, `mcp__editor__insert_widget`, `mcp__editor__reply_to_comment` |
| User interaction | `AskUserQuestion`, `mcp__user__ask_user` |
| Unknown tools | Any tool not explicitly classified as low-sensitivity |

## 5. Hook Output Contract

Every backend allow decision must use the Claude Code CLI 2.1+ `PreToolUse` format. Hook callbacks return **plain dict literals** — in claude-agent-sdk 0.2.128 `HookJSONOutput` is a Union of TypedDicts, NOT callable **[2026-07-26]**:

```python
{
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }
}
```

Do not use empty `{}` to mean allow. Empty output only declines to make a hook-level decision; Claude Code then falls back to its own permission layer, which can still show a native permission prompt.

Deny decisions use:

```python
{
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
}
```

## 6. Decision Order

`agent_runner.py::_pre_tool_use_hook` applies decisions in this order:

1. `.editor/` virtual-index `Read` redirect, all modes.
2. Disabled-network check; `WebFetch`, `WebSearch`, and common Bash network commands are hard-denied when `sandbox_network_mode="disabled"`.
3. Built-in file/search workspace-boundary check, all modes; outside current thread workspace is a hard deny.
4. If `im_full_access_enabled` is true, tools are exposed, and the tool is not an answer-form tool: explicit allow.
5. In `auto` only: workspace `files/` built-in file permission.
6. In `auto` only: explicit low-sensitivity tool allow.
7. Frontend confirmation callback.
8. Deny by default when confirmation is required but unavailable.

Bash sandboxing is not a step in this order. Claude Code loads the sandbox
settings from the current thread workspace and enforces them when a Bash command
actually runs.

## 7. Frontend Confirmation

When a high-sensitivity tool reaches the confirmation branch, the backend emits `tool-approval-request`.
The frontend maps that event to the existing tool part with `toolMetadata.approvalRequested=true` and renders Approve/Cancel UI.
Sandbox network confirmations additionally carry `confirmationKind="sandbox_network"` and `networkRequest{host, policyMode, matchedAllowedDomain}`; they originate exclusively from the SDK `can_use_tool` channel (`SandboxNetworkAccess` runtime-proxy asks — not from this PreToolUse layer **[2026-07-26]**). The frontend renders a network-variant confirmation card (host + policy mode + binary Approve/Reject) when present and falls back to the generic card when absent (backward compatible).

Approval returns explicit `permissionDecision:"allow"`.
Rejection returns explicit `permissionDecision:"deny"` with the user-visible reason.

AskUserQuestion-style tools additionally merge frontend `answers` into `updatedInput`.
This remains true in full-access mode.

## 8. Matrix

| Tool / condition | `auto` | `manual` | `none` |
|---|---|---|---|
| `.editor/` virtual-index `Read` | Redirect + allow | Redirect + allow | Not exposed |
| `Read`, `Glob`, `Grep`, `LS` inside current thread workspace | Allow | Confirm | Not exposed |
| `Read`, `Glob`, `Grep`, `LS` outside current thread workspace | Deny | Deny | Not exposed |
| `Write` inside `{cwd}/files/**` | Allow | Confirm | Not exposed |
| `Write` outside `{cwd}/files/**` | Confirm | Confirm | Not exposed |
| `Skill` | Allow | Confirm | Not exposed |
| `mcp__editor__switch_editor` | Allow | Confirm | Not exposed |
| `EnterPlanMode` / `ExitPlanMode` | Allow | Confirm | Not exposed |
| `TodoWrite` / `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet` | Allow | Confirm | Not exposed |
| Editor write MCP tools | Confirm | Confirm | Not exposed |
| `AskUserQuestion` / `mcp__user__ask_user` | Confirm with form | Confirm with form | Not exposed |
| `AskUserQuestion` / `mcp__user__ask_user` with full access | Confirm with form | Confirm with form | Not exposed |
| Read-only Bash subset | Allow | Confirm | Not exposed |
| Complex or mutating Bash | Confirm | Confirm | Not exposed |
| Unknown tool | Confirm | Confirm | Not exposed |
