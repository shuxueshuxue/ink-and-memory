# [Input] Consume IClaudeAgentSDKClient, AgentStreamingCallbacks, AgentRunOptions,
#         AgentRunResult, ToolEventPayload from types.py;
#         build_user_message_content from messages/;
#         SimpleClaudeAgentSDKClient from simple_cas_client.py;
# [Output] Provide ClaudeAgentRunner and create_agent_runner to application layers.
# [Pos] core runner node in libs/claude_agent_kit/server
# [Sync] 2026-05-09: forward stdio MCP tool input and result events for frontend traces.
# [Sync] 2026-05-09: merge project .env SDK injection, stderr capture, and PreToolUse confirmation hooks while keeping Pet Chat's narrow stdio MCP surface.
# [Sync] 2026-05-09: expose zero-argument necklace intent tools while keeping server-owned upstream parameters.
# [Sync] 2026-05-09: guard ExceptionGroup checks on Python runtimes that lack PEP 654 builtins.
# [Sync] 2026-05-09: expose app Mem0 memory recall through zero-argument stdio MCP.
# [Sync] 2026-05-10: keep Claude Code Mem0 hooks on the server-bound Pawkeyland memory index instead of a thread namespace.
# [Sync] 2026-05-10: keep app memory MCP on the server-bound Mem0 API host.
# [Sync] 2026-05-24: prefer INK_AGENT_MEM0_* env names while accepting PAWKEYLAND_* aliases.
# [Sync] 2026-05-10: bridge PreToolUse confirmation through the FastAPI loop so the SDK control task never blocks the worker, even if a future SDK release moves hook dispatch off the running loop.
# [Sync] 2026-05-10: forward include_runtime_context to message building for app-owned runtime prompts.
# [Sync] 2026-05-10: forward app local time into the SDK runtime_context block.
# [Sync] 2026-05-11: stream thinking_delta from delta.thinking through an index-keyed thinking block accumulator and retain signature_delta metadata.
# [Sync] 2026-05-11: include Claude Code interleaved-thinking disable env in SDK propagation diagnostics.
# [Sync] 2026-05-24: diagnose direct ANTHROPIC_AUTH_TOKEN auth.
# [Sync] 2026-05-12: enrich the on_error path with SDK-call context **without changing the exception type** — the SDK's Query._read_messages strips the original ProcessError(message, exit_code, stderr) down to ``str(e)`` before re-raising, so by the time the runner's ``except Exception`` runs we only have a generic "Command failed with exit code 1" string.  The except block now (a) keeps the original exception object untouched (``run_error = exc`` for non-group exceptions, preserving downstream ``isinstance`` checks like ``test_sdk_error_sets_success_false``'s ``assertIsInstance(errors[0], RuntimeError)``); (b) attaches a structured ``[claude_agent_kit] sdk_call_context: resume=… thread_id=… cwd=… model=…`` PEP-678 note via ``run_error.add_note(...)`` so formatted tracebacks and ``getattr(exc, '__notes__', [])`` consumers see the failing session; (c) attaches a second ``[claude_agent_kit] cli_stderr: …`` note when the SDK ``debug_stderr`` buffer captured anything; (d) emits a single ``logger.exception`` with all the structured fields plus traceback for log aggregators.  ``ExceptionGroup`` is the only case that still gets re-wrapped into a plain Exception (its default ``str()`` is unreadable and downstream typed handlers gain nothing from the group wrapper).  The Service-side ``on_error`` SSE frame composes the user-facing ``errorText`` by joining ``str(error)`` with the notes via ``" | "`` so the rich context surfaces through the existing SSE schema unchanged.
# [Sync] 2026-05-12: widen run_streaming's exception catch from ``except Exception`` to ``except BaseException`` so anyio TaskGroup ``BaseExceptionGroup`` wrappers actually fire ``callbacks.on_error`` and surface as ``AgentRunResult(success=False)``.  Root cause: ``claude_agent_sdk._internal.query.Query._read_messages`` catches the CLI failure, logs ``ERROR Fatal error in message reader: Command failed with exit code 1``, and reshapes it into a synthetic ``{"type":"error"}`` stream message; ``Query.receive_messages`` raises a plain ``Exception`` from that sentinel; ``async with ClaudeSDKClient`` ``__aexit__`` then cancels the still-running write / control sibling tasks, raising ``CancelledError`` (a ``BaseException`` subclass), and the SDK's TaskGroup packages everything into a ``BaseExceptionGroup``.  ``BaseExceptionGroup`` is **not** an ``Exception`` subclass, so the previous ``except Exception`` silently let the failure propagate past the runner — ``on_error`` never fired, ``success`` kept its default ``True``, and the caller saw a half-finished stream with no error frame.  New ``_is_pure_cancellation(exc)`` helper distinguishes "every leaf is ``CancelledError``" (true outer cancel — re-raise so the FastAPI / pytest task hierarchy still unwinds) from "at least one non-cancelled leaf" (the typical CLI-failure-plus-sibling-cancel group — fall through to the existing diagnostic-enrichment + ``on_error`` path).  The group-flattening branch is also widened from ``_EXCEPTION_GROUP_TYPES`` to ``_BASE_EXCEPTION_GROUP_TYPES`` so ``BaseExceptionGroup`` (which ``ExceptionGroup`` is now a subclass of, per PEP 654) gets the same readable-message treatment instead of leaving the ugly default group ``str()`` in the SSE error frame.  Bare non-cancelled ``BaseException`` leaves (``KeyboardInterrupt`` / ``SystemExit``) are wrapped into a plain ``Exception`` for the same SSE-serialisation reason.  No service-side change required: ``execute_session`` already routes ``result.success is False`` to a ``{"type":"error","errorText":...}`` SSE frame, and the existing ``except BaseException`` + ``_exception_group_contains_cancelled`` re-raise stays as the *outer* cancel safety net for cases the runner re-raises from ``_is_pure_cancellation``.
# [Sync] 2026-05-24: keep run_streaming's BaseException diagnostic log on logger.exception so backend logs include the caught traceback while on_error still receives the enriched run_error.
# [Sync] 2026-05-24: rename _REQUEST_MODEL_OVERRIDE_ENV_KEY from PAWKEYLAND_CLAUDE_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE to INK_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE; keep legacy key as fallback in _apply_request_model_override_if_allowed for zero-downtime migration.
# [Sync] 2026-05-24: move _inject_mem0_session_hook_env and _verify_claude_sdk_env_for_query_stream calls inside run_streaming's try/except BaseException block so any raised exception is caught and routed to callbacks.on_error → SSE error frame; raise RuntimeError in _verify_claude_sdk_env_for_query_stream when no auth key is present instead of silently returning.
# [Sync] 2026-05-27: migrate _pre_tool_use_hook hookSpecificOutput from old {"tool_input":...} format to CLI ≥2.1 format: hookEventName + permissionDecision:"allow" + updatedInput for input override; permissionDecision:"deny" + permissionDecisionReason for all block paths. The old "tool_input" key is silently ignored by the CLI, leaving AskUserQuestion without answers and returning isError:true / output:null.
# [Sync] 2026-05-27: add _ALWAYS_CONFIRM_TOOL_NAMES constant; original auto mode
#                    only confirmed AskUserQuestion/mcp__user__ask_user. Superseded
#                    by 2026-06-06: non-files tools now use confirmation too.
# [Sync] 2026-05-28: implement .editor/ virtual index read interception in _pre_tool_use_hook — detect is_editor_index_path, write tempfile from editor_state, return updatedInput redirect (CLI ≥2.1 format); cleanup tempfiles in finally block.
# [Sync] 2026-05-29: extract .editor/ redirect block into module-level _apply_editor_index_redirect for unit-testability; _pre_tool_use_hook delegates to it.
# [Sync] 2026-05-29: _editor_mcp_stdio_config now accepts editor_state dict and passes it
#                    as INK_EDITOR_STATE_JSON env var (session-inline, no tempfile);
#                    removes tempfile creation/cleanup for editor MCP in run_streaming.
# [Sync] 2026-05-29: switch editor MCP from read-only tools to write-only tools; replace
#                    INK_EDITOR_STATE_JSON injection with INK_AGENT_SESSION_ID +
#                    INK_AGENT_USER_ID so write handlers call database directly; add all
#                    four write tool names to _ALWAYS_CONFIRM_TOOL_NAMES; editor MCP
#                    startup condition now checks mcp_env for INK_AGENT_SESSION_ID.
# [Sync] 2026-05-29: remove env-var session injection; _editor_mcp_stdio_config is
#                    zero-argument — session_id flows via MCP tool arguments from prompt;
#                    editor MCP startup condition restored to opts.editor_state is not None.
# [Sync] 2026-05-29: remove env-var session context injection; session_id flows through
#                    MCP tool call arguments (agent reads from <workspace_context> prompt);
#                    _editor_mcp_stdio_config reverts to zero-arg form; editor MCP startup
#                    condition restored to opts.editor_state is not None.
# [Sync] 2026-05-29: _pre_tool_use_hook reads live editor_state via opts.editor_state_getter
#                    (supplied by service.py as lambda: state.editor_state) so PreToolUse
#                    virtual-index reads see the flyweight's latest value after write-tool
#                    DB refreshes; falls back to opts.editor_state when getter is absent.
# [Sync] 2026-06-07: refine auto-mode PreToolUse policy to product sensitivity:
#                    workspace files/ built-in file tools and explicit low-risk
#                    query tools receive hook-level allow; execution/write/
#                    interaction tools fall through to frontend confirmation.
# [Sync] 2026-06-07: add Bash+ls and mcp__editor__switch_editor to low-sensitivity
#                    auto-allow class; _apply_low_sensitivity_query_permission now
#                    accepts optional tool_input for command-level Bash inspection.
# [Sync] 2026-06-07: expand _LOW_SENSITIVITY_BASH_PREFIXES from {ls} to full
#                    read-only/navigation set: ls cd pwd echo cat head tail wc
#                    find which type date whoami id groups env printenv uname hostname.
# [Sync] 2026-06-09: classify Claude Code's built-in Skill tool as low-sensitivity
#                    after confirming SKILL_TOOL_NAME == "Skill" in restored source;
#                    keep switch_editor in the low-sensitivity class.
# [Sync] 2026-06-09: normalize PreToolUse/PostToolUse hook payload keys across
#                    snake_case and camelCase shapes so inputs like
#                    {"toolName": "Skill"} still hit the low-sensitivity allow path.
# [Sync] 2026-06-09: add Settings-controlled IM full-access mode: after safe
#                    .editor/ redirects, exposed tools can receive explicit
#                    PreToolUse permissionDecision:"allow".
# [Sync] 2026-06-13: full-access mode keeps AskUserQuestion-style tools on the
#                    frontend confirmation path so user answers can be collected
#                    and merged into updatedInput.
# [Sync] 2026-06-17: detect seccomp-denied sandbox startup errors
#                    (e.g. apply-seccomp Permission denied) and attach actionable
#                    Docker runtime remediation notes to runner errors.
# [Sync] 2026-06-17: expand DEFAULT_ALLOWED_TOOLS to include built-in filesystem,
#                    notebook, todo and Bash tools so agents can read/write the
#                    workspace without requiring a custom allowedTools override.
# [Sync] 2026-06-21: enforce Settings sandbox_network_mode="disabled" in
#                    PreToolUse before full-access or low-sensitivity allows.
# [Sync] 2026-07-20: claude-plan — inject per-thread CLAUDE_CONFIG_DIR via
#                    apply_plan_mode_env_to_options after sdk_options
#                    construction; classify EnterPlanMode/ExitPlanMode as
#                    low-sensitivity auto-allow (official ExitPlanMode ask
#                    semantics deviation recorded in
#                    claude-agent-permission-policy.md); add PostToolUse
#                    plan-file observer hook with INK_AGENT_PLAN_EMIT_DEBOUNCE_MS
#                    debounce firing callbacks.on_plan_file_changed.
# [Sync] 2026-07-20: claude-todo — DEFAULT_ALLOWED_TOOLS gains the v2 task
#                    tools (TaskCreate/TaskUpdate/TaskList/TaskGet); all five
#                    todo tools (+TodoWrite) classified low-sensitivity
#                    auto-allow (TaskUpdate non-read-only deviation recorded in
#                    claude-agent-permission-policy.md §3); INK_AGENT_TASK_V2_ENABLED-
#                    gated apply_task_v2_env_to_options injects
#                    CLAUDE_CODE_ENABLE_TASKS/CLAUDE_CODE_TASK_LIST_ID; add
#                    PostToolUse task observer hook with
#                    INK_AGENT_TODO_EMIT_DEBOUNCE_MS debounce firing
#                    callbacks.on_tasks_changed with derived TodoItem dicts.
# [Sync] 2026-07-23: SandboxPermissionRequest runtime-proxy channel — wire
#                    ClaudeAgentOptions.can_use_tool=_can_use_tool: the CLI's
#                    sandbox-runtime network ask ("SandboxNetworkAccess",
#                    input {"host"}) is a system-level control request invisible
#                    to PreToolUse; route it through the frontend confirmation
#                    side-channel with confirmationKind="sandbox_network" +
#                    networkRequest{host, policyMode, matchedAllowedDomain}.
#                    Approved → PermissionResultAllow(updated_input);
#                    rejected/failure/timeout → PermissionResultDeny mentioning
#                    the host and the Settings allowedDomains remedy; any
#                    exception fails closed.  Other tool names route through the
#                    same generic chain (rare per official contract — the hook
#                    resolves tools first, so no double-prompting).
# [Sync] 2026-07-26: REMOVE the PreToolUse-layer network gate added 2026-07-23
#                    (step ②.5 _apply_sandbox_network_permission plus the
#                    _match_sandbox_network_allowed_domain /
#                    _extract_network_tool_host / _is_ip_literal helpers, the
#                    full-access/low-sensitivity skip guards, the step ⑦
#                    payload discriminator, and the AgentRunOptions
#                    sandbox_network_allowed_domains plumbing).  Rationale:
#                    network policy is a system-level control enforced by
#                    Claude Code's own sandbox (sandbox.network written into
#                    per-thread .claude/settings.json by workspace.py) whose
#                    asks arrive exclusively via can_use_tool — the PreToolUse
#                    gate was wrong-layer duplication.  The hook's decision
#                    flow returns to its pre-feature shape; can_use_tool is
#                    now the single network-confirmation channel.  With one
#                    trigger source left, the networkRequest.source field is
#                    dropped entirely.
# [Sync] 2026-07-26: SDK migration claude-code-sdk 0.0.25 → claude-agent-sdk
#                    0.2.128 (package + ClaudeCodeOptions→ClaudeAgentOptions
#                    rename).  Required for can_use_tool: 0.0.25 serializes
#                    control responses in the old {"allow": true} dialect,
#                    which the deployed CLI rejects (permissionToolOutputSchema
#                    expects {behavior:"allow", updatedInput}); the new SDK
#                    emits the correct shape.  Non-mechanical adaptations:
#                    (1) debug_stderr file object is deprecated/unread — CLI
#                    stderr capture now registers an options.stderr callback
#                    via _make_cli_stderr_capture, so the
#                    "debug-to-stderr" _StderrSentinelArgs hack is retired
#                    (class kept for reference only); (2) the new transport
#                    prefers its bundled CLI over system `claude`
#                    (cli_path option overrides); (3) extra_args passthrough,
#                    hooks dict format, include_partial_messages, resume, and
#                    the ClaudeSDKClient query/receive_response API are
#                    unchanged.  Advisory CanUseToolShadowedWarning may fire
#                    once per process because allowed_tools contains
#                    whole-tool entries alongside can_use_tool — intentional.
# [Sync] 2026-07-26: HOTFIX — replace all ~25 HookJSONOutput(...) constructor
#                    calls with plain dict literals.  In claude-agent-sdk
#                    0.2.128 HookJSONOutput is a Union of TypedDicts
#                    (types.py:561), NOT callable, so every constructor call
#                    raised TypeError: 'types.UnionType' object is not
#                    callable.  Two production symptoms, one root cause:
#                    (a) PostToolUse plan-file/tasks observers crashed with
#                    visible tracebacks; (b) PreToolUse allow/deny decisions
#                    were silently dropped — the hook errored out, the CLI
#                    received no decision and executed the tool even after the
#                    user rejected it in the confirmation dialog.  Hook
#                    callbacks now return plain dicts per the official
#                    contract: {} for no-op, {"hookSpecificOutput":
#                    {"hookEventName": ..., "permissionDecision": "allow|deny",
#                    "permissionDecisionReason": ..., "updatedInput": ...}}
#                    for decisions.  The import is kept for return-type
#                    annotations only (the Union IS the correct type).  No
#                    decision logic, key names, or behavior changed.
# [Sync] 2026-07-26: wire apply_cli_path_to_options into options assembly
#                    (before plan/task env injection) so the system/npm CLI —
#                    Docker's apply-seccomp-patched runtime — is not shadowed
#                    by the SDK bundled CLI (bundled-first _find_cli in 0.2.128).

"""Claude Agent Runner.

Python translation of TypeScript:
  server/server/agent-runner.ts

Unified interface for running the Claude agent with streaming support.
Wraps ``SimpleClaudeAgentSDKClient`` to provide a clean streaming-callback
interface for the AI worker.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from claude_agent_sdk.types import (  # type: ignore[import-untyped]
    AssistantMessage,
    ClaudeAgentOptions,
    HookContext,
    HookJSONOutput,
    HookMatcher,
    McpServerConfig,
    McpStdioServerConfig,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    ToolPermissionContext,
    UserMessage,
)

from ..types import (
    AgentRunOptions,
    AgentRunResult,
    AgentStreamingCallbacks,
    IClaudeAgentSDKClient,
    ToolChoiceMode,
    ToolEventPayload,
)
from .simple_cas_client import SimpleClaudeAgentSDKClient
from .memory_tool import allowed_memory_tool_names
from .necklace_tool import allowed_necklace_tool_names
from .editor_tool import allowed_editor_tool_names, SWITCH_EDITOR_TOOL_NAME, load_editor_state_from_db
from .sessions_tool import GET_SESSIONS_RANGE_TOOL_NAME
from .sdk_env import (
    apply_cli_path_to_options,
    apply_plan_mode_env_to_options,
    apply_project_sdk_runtime_options,
    apply_task_v2_env_to_options,
    apply_user_sdk_env_to_options,
)
from .workspace import get_plans_dir, get_tasks_dir, get_workspace_root, read_task_items

logger = logging.getLogger(__name__)

try:
    _BASE_EXCEPTION_GROUP_TYPES: tuple[type[BaseException], ...] = (BaseExceptionGroup,)  # type: ignore[name-defined]
    _EXCEPTION_GROUP_TYPES: tuple[type[BaseException], ...] = (ExceptionGroup,)  # type: ignore[name-defined]
except NameError:
    _BASE_EXCEPTION_GROUP_TYPES = ()
    _EXCEPTION_GROUP_TYPES = ()

# ---------------------------------------------------------------------------
# Default tool allowlist.
#
# Includes built-in filesystem/notebook/todo/Bash tools so agents can operate
# on the workspace out of the box.  Sandbox policy (workspace.py) restricts
# actual filesystem access to the thread workspace and any extra read-only
# paths configured via INK_AGENT_SANDBOX_EXTRA_ALLOW_READ.
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_TOOLS: list[str] = [
    
    "WebFetch",
    "WebSearch",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Grep",
    "Glob",
    "LS",
    "NotebookRead",
    "TodoRead",
    "TodoWrite",
    # Claude Code v2 file-task tools (claude-todo §5.7).  Whether the CLI
    # actually exposes them is decided by the official isTodoV2Enabled()
    # (mutually exclusive with TodoWrite); listing them here is harmless.
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
    "Bash",
    "BashOutput",
    "Skill",
    "mcp__user__touch_animation",
    f"mcp__user__{GET_SESSIONS_RANGE_TOOL_NAME}",
    *allowed_memory_tool_names(),
    *allowed_necklace_tool_names(),
    *allowed_editor_tool_names(),
]

_AUTO_MODE_REQUIRED_ALLOWED_TOOLS: frozenset[str] = frozenset({
    # SkillTool has its own Claude Code permission prompt for non-safe skill
    # metadata. Keep the tool in auto-mode allowed_tools even when callers pass
    # a custom allowed_tools list so our PreToolUse allow can own the decision.
    "Skill",
})
_USER_MCP_TOOL_PREFIX = "mcp__user__"
_MEMORY_MCP_TOOL_PREFIX = "mcp__memory__"
_NECKLACE_MCP_TOOL_PREFIX = "mcp__necklace__"
_EDITOR_MCP_TOOL_PREFIX = "mcp__editor__"
_SWITCH_EDITOR_MCP_TOOL_NAME = f"{_EDITOR_MCP_TOOL_PREFIX}{SWITCH_EDITOR_TOOL_NAME}"
_WORKSPACE_FILES_PERMISSION_TOOLS: frozenset[str] = frozenset({
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
})
_WORKSPACE_BOUNDARY_FILE_TOOLS: frozenset[str] = frozenset({
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Grep",
    "Glob",
    "LS",
    "NotebookRead",
})
_WORKSPACE_QUERY_PERMISSION_TOOLS: frozenset[str] = frozenset({
    "Read",
    "Grep",
    "Glob",
    "LS",
    "NotebookRead",
})
_LOW_SENSITIVITY_QUERY_TOOL_NAMES: frozenset[str] = frozenset({
    # Claude Code built-in query tools that do not accept arbitrary filesystem
    # paths. File/search tools are handled by the workspace-boundary helper.
    "TodoRead",
    "WebFetch",
    "WebSearch",
    "BashOutput",
    # Claude Code built-in SkillTool expands/executes a named skill prompt.
    # Source check: restored-src/src/tools/SkillTool/constants.ts exports
    # SKILL_TOOL_NAME = "Skill".
    "Skill",
    # Claude Code Plan Mode session-state tools.  Neither mutates user
    # content directly; official ExitPlanMode ask semantics are downgraded
    # to low-sensitivity per claude-agent-permission-policy.md §3 deviation
    # record (claude-plan §5.7, 2026-07-20).
    "EnterPlanMode",
    "ExitPlanMode",
    # Claude Code todo/task-list tools (v1 TodoWrite + v2 file tasks).
    # All five are session-metadata operations confined to the per-thread
    # workspace; the TaskUpdate non-read-only deviation is recorded in
    # claude-agent-permission-policy.md §3 (claude-todo §5.7, 2026-07-20).
    "TodoWrite",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
    # SDK / MCP resource discovery and reads, where available.
    "ListMcpResources",
    "ReadMcpResource",
    # Product-owned read-only MCP tools.
    f"mcp__user__{GET_SESSIONS_RANGE_TOOL_NAME}",
    *allowed_memory_tool_names(),
    *allowed_necklace_tool_names(),
    # Editor context-switch — no-op MCP handler; state update happens in
    # PostToolUse hook. Agent declares which document it's working on.
    f"{_EDITOR_MCP_TOOL_PREFIX}{SWITCH_EDITOR_TOOL_NAME}",
})

# Shell metacharacters that would make a Bash command unsafe for auto-allow.
_SHELL_METACHAR_RE = re.compile(r'[|;&<>`]|\$\(|\$\{')

# Read-only / navigation shell commands that carry no filesystem side effects.
# Any command whose first token matches one of these and contains no shell
# metacharacters is considered low-sensitivity and receives hook-level allow.
_LOW_SENSITIVITY_BASH_PREFIXES: frozenset[str] = frozenset({
    "ls",       # list directory
    "cd",       # change directory (no filesystem mutation)
    "pwd",      # print working directory
    "echo",     # print text (safe without redirection)
    "cat",      # read file contents
    "head",     # read first N lines
    "tail",     # read last N lines
    "wc",       # word/line/byte count
    "find",     # locate files (read-only traversal)
    "which",    # locate a command
    "type",     # show command type
    "date",     # print current date/time
    "whoami",   # print current user
    "id",       # print user/group identity
    "groups",   # list group memberships
    "env",      # print environment
    "printenv", # print specific env vars
    "uname",    # print system info
    "hostname", # print hostname
})

_NETWORK_BASH_PREFIXES: frozenset[str] = frozenset({
    "curl",
    "wget",
    "ping",
    "nslookup",
    "dig",
    "host",
    "nc",
    "netcat",
    "telnet",
    "ssh",
    "scp",
    "sftp",
    "rsync",
})
_NETWORK_TOOL_NAMES: frozenset[str] = frozenset({
    "WebFetch",
    "WebSearch",
})
_PACKAGE_NETWORK_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "git": frozenset({"clone", "fetch", "pull", "push", "ls-remote", "submodule"}),
    "npm": frozenset({"install", "i", "add", "update", "ci", "audit", "publish", "view", "pack"}),
    "npx": frozenset({""}),
    "pnpm": frozenset({"install", "i", "add", "update", "dlx", "publish"}),
    "yarn": frozenset({"install", "add", "up", "upgrade", "publish", "dlx"}),
    "bun": frozenset({"install", "add", "x", "pm"}),
    "pip": frozenset({"install", "download", "wheel", "index"}),
    "pip3": frozenset({"install", "download", "wheel", "index"}),
    "uv": frozenset({"add", "sync", "pip", "tool"}),
    "go": frozenset({"get", "install", "mod"}),
    "cargo": frozenset({"install", "search", "publish", "update"}),
}
_COMMAND_WRAPPERS: frozenset[str] = frozenset({"command", "exec", "sudo", "time"})


def _is_low_sensitivity_bash_command(command: str) -> bool:
    """Return True when *command* is a safe, read-only shell invocation.

    Checks two conditions:
    1. No shell metacharacters (``|`` ``&`` ``;`` ``<`` ``>`` `` ` `` ``$(`` ``${``).
    2. The first token is one of :data:`_LOW_SENSITIVITY_BASH_PREFIXES`.

    Examples that pass: ``ls -la``, ``cd /tmp``, ``cat notes.md``, ``echo hello``.
    Examples that fail: ``ls | grep foo``, ``cat file > out``, ``rm -rf /``.
    """
    cmd = command.strip()
    if not cmd:
        return False
    if _SHELL_METACHAR_RE.search(cmd):
        return False
    first_token = cmd.split()[0]
    return first_token in _LOW_SENSITIVITY_BASH_PREFIXES


def _split_shell_command(command: str) -> list[str]:
    """Best-effort shell tokenization for policy classification."""

    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.strip().split()


def _command_name(token: str) -> str:
    """Return the lower-case executable basename for a shell token."""

    return Path(token).name.lower()


def _unwrap_command_tokens(tokens: list[str]) -> list[str]:
    """Skip common wrappers so policy sees the command being executed."""

    index = 0
    while index < len(tokens):
        name = _command_name(tokens[index])
        if name == "env":
            index += 1
            while index < len(tokens):
                token = tokens[index]
                if token.startswith("-") or ("=" in token and not token.startswith("=")):
                    index += 1
                    continue
                break
            continue
        if name in _COMMAND_WRAPPERS:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        break
    return tokens[index:]


def _is_network_bash_command(command: str) -> bool:
    """Return True when a Bash command is expected to use outbound network."""

    tokens = _unwrap_command_tokens(_split_shell_command(command))
    if not tokens:
        return False

    name = _command_name(tokens[0])
    if name in _NETWORK_BASH_PREFIXES:
        return True

    if name in {"python", "python3"} and len(tokens) >= 4:
        return (
            tokens[1] == "-m"
            and tokens[2] in {"pip", "pip3"}
            and tokens[3].lower() in _PACKAGE_NETWORK_SUBCOMMANDS["pip"]
        )

    subcommands = _PACKAGE_NETWORK_SUBCOMMANDS.get(name)
    if subcommands is None:
        return False
    if "" in subcommands:
        return True
    if len(tokens) < 2:
        return False

    if name == "uv" and tokens[1] == "pip" and len(tokens) >= 3:
        return tokens[2].lower() in {"install", "download", "wheel"}
    return tokens[1].lower() in subcommands


def _apply_disabled_network_permission(
    sandbox_network_mode: str,
    tool_name: str,
    tool_input: Optional[dict[str, Any]] = None,
) -> Optional[HookJSONOutput]:
    """Hard-deny known network tools when Settings disables network access."""

    if sandbox_network_mode != "disabled":
        return None
    if tool_name in _NETWORK_TOOL_NAMES:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "代理网络访问已关闭，禁止网络访问。",
            }
        }
    if tool_name == "Bash":
        command = str((tool_input or {}).get("command") or "").strip()
        if _is_network_bash_command(command):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "代理网络访问已关闭，禁止执行网络命令。",
                }
            }
    return None


# ---------------------------------------------------------------------------
# SandboxPermissionRequest — runtime-proxy network approval (can_use_tool)
#
# Design: docs/design/claude-agent/claude-agent-sandbox-network-permission-tool.md
# Network policy is a system-level control enforced by Claude Code's own
# sandbox (sandbox.network written into per-thread .claude/settings.json by
# workspace.py).  The CLI's runtime asks arrive exclusively via the SDK
# ``can_use_tool`` control channel — there is deliberately NO PreToolUse-layer
# network gate (the earlier step ②.5 was removed 2026-07-26 as wrong-layer
# duplication).
# ---------------------------------------------------------------------------

# Discriminator attached to the confirmation payload (and the SSE
# ``tool-approval-request`` frame) so the frontend can render the
# network-variant confirmation card.  Absent for generic confirmations.
SANDBOX_NETWORK_CONFIRMATION_KIND = "sandbox_network"

# Tool name used by the CLI's sandbox-runtime network ask, delivered through
# the SDK ``can_use_tool`` control channel (not PreToolUse) when sandboxed Bash
# hits a non-allowlisted host at the runtime proxy
# (restored-src cli/structuredIO.ts).  Input shape: ``{"host": <hostname>}``.
SANDBOX_NETWORK_ACCESS_TOOL_NAME = "SandboxNetworkAccess"

# Tool names that have specialized confirmation semantics. Auto mode now uses
# sensitivity classes: explicit query/context-selection/Skill tools can run,
# while execution/write/interactive tools confirm through the frontend. This
# set remains the explicit inventory of Q&A and editor-write tools whose
# UI/result handling is special.
_ALWAYS_CONFIRM_TOOL_NAMES: frozenset[str] = frozenset({
    "AskUserQuestion",
    "mcp__user__ask_user",
    # Editor write tools — all require human confirmation (see mcp-tools.md §4)
    "mcp__editor__write_segment",
    "mcp__editor__delete_segment",
    "mcp__editor__insert_widget",
    "mcp__editor__reply_to_comment",
})
_ANSWER_FORM_TOOL_NAMES: frozenset[str] = frozenset({
    "AskUserQuestion",
    "mcp__user__ask_user",
})
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_FALSE_ENV_VALUES = {"0", "false", "no", "off"}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_NECKLACE_ENV_NAMES: tuple[str, ...] = (
    "PAWKEYLAND_AGENT_PET_ID",
    "PAWKEYLAND_AGENT_PET_SPECIES",
    "PAWKEYLAND_AGENT_PET_TYPE",
    "PAWKEYLAND_QIALG_BASE_URL",
    "PAWKEYLAND_QIALG_LOGIN_URL",
    "PAWKEYLAND_QIALG_LOGIN_MOBILE",
    "PAWKEYLAND_QIALG_LOGIN_SMS_CODE",
    "PAWKEYLAND_QIALG_LOGIN_CAPTCHA",
    "PAWKEYLAND_QIALG_LOGIN_THIRD_ID",
    "PAWKEYLAND_QIALG_NECKLACE_ACCESS_TOKEN",
    "PAWKEYLAND_NECKLACE_FETCH_TIMEOUT_S",
    "PAWKEYLAND_NECKLACE_RECENT_WINDOW_MINUTES",
    "PAWKEYLAND_NECKLACE_USE_REFERENCE_TIME",
    "PAWKEYLAND_NECKLACE_REFERENCE_TIME",
    "PAWKEYLAND_NECKLACE_REFERENCE_DATE",
)
_MEMORY_ENV_ALIASES: tuple[tuple[str, str], ...] = (
    ("INK_AGENT_MEM0_ENABLED", "PAWKEYLAND_MEM0_ENABLED"),
    ("INK_AGENT_MEM0_API_KEY", "PAWKEYLAND_MEM0_API_KEY"),
    ("INK_AGENT_MEM0_API_HOST", "PAWKEYLAND_MEM0_API_HOST"),
    ("INK_AGENT_MEM0_CONNECT_TIMEOUT_MS", "PAWKEYLAND_MEM0_CONNECT_TIMEOUT_MS"),
    ("INK_AGENT_MEM0_READ_TIMEOUT_MS", "PAWKEYLAND_MEM0_READ_TIMEOUT_MS"),
    ("INK_AGENT_MEM0_TOP_K", "PAWKEYLAND_MEM0_TOP_K"),
    ("INK_AGENT_MEM0_USER_ID", "PAWKEYLAND_MEM0_USER_ID"),
    ("INK_AGENT_USER_MESSAGE", "PAWKEYLAND_AGENT_USER_MESSAGE"),
)
_MEMORY_USER_ID_ENV_NAMES = ("INK_AGENT_MEM0_USER_ID", "PAWKEYLAND_MEM0_USER_ID")
_CLAUDE_SDK_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "API_TIMEOUT_MS",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "DISABLE_INTERLEAVED_THINKING",
)
_CLAUDE_SDK_AUTH_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_AUTH_TOKEN",
)
# Primary key (Ink & Memory prefix); legacy Pawkeyland key is accepted as
# fallback so deployments with the old .env survive until they migrate.
_REQUEST_MODEL_OVERRIDE_ENV_KEY = "INK_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE"
_REQUEST_MODEL_OVERRIDE_ENV_KEY_LEGACY = (
    "PAWKEYLAND_CLAUDE_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE"
)


def _verify_claude_sdk_env_for_query_stream(sdk_options: ClaudeAgentOptions) -> None:
    """Log Claude SDK subprocess env propagation status without exposing secrets."""

    existing_env = getattr(sdk_options, "env", None)
    if isinstance(existing_env, dict):
        env = existing_env
    else:
        env = dict(existing_env or {})
        sdk_options.env = env

    present_keys = [key for key in _CLAUDE_SDK_ENV_KEYS if bool(env.get(key))]
    missing_keys = [key for key in _CLAUDE_SDK_ENV_KEYS if not env.get(key)]
    has_auth_key = any(bool(env.get(key)) for key in _CLAUDE_SDK_AUTH_ENV_KEYS)

    if not has_auth_key:
        logger.warning(
            "Claude SDK env check before query_stream has no auth key; "
            "present_keys=%s missing_keys=%s env_count=%d",
            present_keys,
            missing_keys,
            len(env),
        )
        raise RuntimeError(
            f"Claude SDK has no auth key in subprocess env; "
            f"expected one of {_CLAUDE_SDK_AUTH_ENV_KEYS!r}. "
            f"present_keys={present_keys!r} env_count={len(env)}"
        )

    logger.debug(
        "Claude SDK env check before query_stream; present_keys=%s "
        "missing_keys=%s env_count=%d",
        present_keys,
        missing_keys,
        len(env),
    )


def _env_flag_enabled(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in _TRUE_ENV_VALUES


def _first_env_value(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _first_mapping_value(mapping: dict[str, str], *names: str) -> str:
    for name in names:
        value = str(mapping.get(name, "") or "").strip()
        if value:
            return value
    return ""


def _set_env_aliases(
    env: dict[str, str],
    canonical_name: str,
    legacy_name: str,
    value: str,
) -> None:
    if not value:
        return
    env[canonical_name] = value
    env[legacy_name] = value


def _apply_request_model_override_if_allowed(
    sdk_options: ClaudeAgentOptions,
    requested_model: Optional[str],
) -> None:
    """Apply request-level model only when explicitly enabled by project env."""

    model_name = (requested_model or "").strip()
    if not model_name:
        return

    existing_env = getattr(sdk_options, "env", None)
    if isinstance(existing_env, dict):
        env = existing_env
    else:
        env = dict(existing_env or {})
        sdk_options.env = env

    # Accept both new (INK_AGENT_*) and legacy (PAWKEYLAND_*) key names.
    override_enabled = _env_flag_enabled(
        env.get(_REQUEST_MODEL_OVERRIDE_ENV_KEY)
        or env.get(_REQUEST_MODEL_OVERRIDE_ENV_KEY_LEGACY)
    )
    if override_enabled:
        sdk_options.model = model_name
        logger.debug("Claude SDK request model override enabled; model=%s", model_name)
        return

    logger.info(
        "Ignoring request-level Claude SDK model override; requested_model=%s "
        "configured_model_present=%s override_env_key=%s",
        model_name,
        bool(env.get("ANTHROPIC_MODEL")),
        _REQUEST_MODEL_OVERRIDE_ENV_KEY,
    )


def _inject_mem0_session_hook_env(
    sdk_options: ClaudeAgentOptions,
    request_env: Optional[dict[str, str]],
) -> None:
    """Expose the app-resolved Mem0 binding to Claude Code lifecycle hooks."""

    existing_env = getattr(sdk_options, "env", None)
    if isinstance(existing_env, dict):
        env = existing_env
    else:
        env = dict(existing_env or {})
        sdk_options.env = env

    scoped_env = request_env or {}
    app_mem0_user_id = _first_mapping_value(scoped_env, *_MEMORY_USER_ID_ENV_NAMES)
    if not app_mem0_user_id:
        # Project .env is allowed to carry Mem0 service config, but not a
        # request-scoped memory identity. Avoid leaking a stale or legacy hook key.
        env.pop("INK_AGENT_MEM0_USER_ID", None)
        env.pop("PAWKEYLAND_MEM0_USER_ID", None)
        env.pop("INK_AGENT_USER_MESSAGE", None)
        env.pop("PAWKEYLAND_AGENT_USER_MESSAGE", None)
        env.pop("MEM0_USER_ID", None)
        return

    for canonical_name, legacy_name in _MEMORY_ENV_ALIASES:
        if canonical_name == "INK_AGENT_MEM0_USER_ID":
            continue
        value = _first_mapping_value(scoped_env, canonical_name, legacy_name)
        if not value:
            value = _first_env_value(canonical_name, legacy_name)
        if value:
            _set_env_aliases(env, canonical_name, legacy_name, str(value))
    env.pop("INK_AGENT_MEM0_USER_ID", None)
    env.pop("PAWKEYLAND_MEM0_USER_ID", None)
    # Follow the claude-runner hook contract: lifecycle hooks read MEM0_USER_ID.
    # The value is the app memory key, never the Claude SDK thread id.
    env["MEM0_USER_ID"] = app_mem0_user_id


class _StderrSentinelArgs(dict):  # type: ignore[type-arg]
    """Enable SDK stderr capture without adding an unsupported CLI flag.

    Only used with the legacy claude-code-sdk (<0.1) transport, which gates
    stderr piping on ``"debug-to-stderr" in extra_args``.  Retained for
    reference; the current claude-agent-sdk transport pipes stderr whenever an
    ``options.stderr`` callback is registered, so new code must NOT rely on
    this sentinel (see ``_make_cli_stderr_capture``).
    """

    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        return item == "debug-to-stderr" or super().__contains__(item)


def _make_cli_stderr_capture(buf: Any) -> Callable[[str], None]:
    """Return an SDK ``stderr`` callback appending CLI stderr lines to *buf*.

    claude-agent-sdk (>=0.1) deprecates ``ClaudeAgentOptions.debug_stderr``
    (no longer read by the transport); CLI stderr is piped only when an
    ``options.stderr`` callback is registered, and delivered line-by-line.
    The runner keeps its TemporaryFile buffer contract for the on_error
    diagnostic notes by funnelling those lines through this callback.
    Diagnostics must never break a run, so every failure is swallowed.
    """

    def _capture(line: str) -> None:
        try:
            buf.write(line.encode("utf-8", errors="replace") + b"\n")
            buf.flush()
        except Exception:  # noqa: BLE001
            pass

    return _capture


def _iter_exception_leaves(exc: BaseException) -> list[BaseException]:
    if _BASE_EXCEPTION_GROUP_TYPES and isinstance(exc, _BASE_EXCEPTION_GROUP_TYPES):
        leaves: list[BaseException] = []
        for child in exc.exceptions:
            leaves.extend(_iter_exception_leaves(child))
        return leaves
    return [exc]


def _format_exception_message(exc: BaseException) -> str:
    leaves = _iter_exception_leaves(exc)
    if len(leaves) == 1 and leaves[0] is exc:
        return str(exc)
    return "; ".join(f"{type(leaf).__name__}: {leaf}" for leaf in leaves)


def _sandbox_runtime_failure_hint(
    error_message: str,
    stderr_snippet: str,
) -> Optional[str]:
    """Return remediation guidance for known sandbox-runtime startup failures."""

    error_content = f"{error_message}\n{stderr_snippet}"
    error_content_lower = error_content.lower()
    if "apply-seccomp" in error_content_lower and "permission denied" in error_content_lower:
        return (
            "Claude Bash sandbox could not apply seccomp in this runtime "
            "(apply-seccomp permission denied). For Docker backend runs, start "
            "the container with docker-compose keys "
            "`cap_add: [SYS_ADMIN]` + `security_opt: [seccomp=unconfined, apparmor=unconfined]` "
            "(or docker run `--cap-add=SYS_ADMIN --security-opt seccomp=unconfined "
            "--security-opt apparmor=unconfined`), then recreate containers."
        )
    if "failed to make / slave: permission denied" in error_content_lower or (
        "bubblewrap" in error_content_lower and "permission denied" in error_content_lower
    ):
        return (
            "Claude Bash sandbox bubblewrap mount setup was blocked by container "
            "security policy. Ensure Docker backend sets `cap_add: [SYS_ADMIN]` "
            "and `security_opt: [seccomp=unconfined, apparmor=unconfined]`."
        )
    return None


def _is_pure_cancellation(exc: BaseException) -> bool:
    """Return True when *exc* represents *only* task cancellation.

    The Claude Code SDK runs its CLI subprocess inside an ``anyio.TaskGroup``.
    When the message-reader task fails the SDK re-shapes the failure into a
    synthetic ``{"type": "error"}`` stream message; ``Query.receive_messages``
    raises a plain ``Exception`` from that sentinel.  As the failure unwinds,
    ``ClaudeSDKClient.__aexit__`` cancels the still-running write / control
    sibling tasks, which raise ``CancelledError`` (a ``BaseException`` subclass).
    The TaskGroup then packages the original ``Exception`` together with the
    sibling ``CancelledError`` instances into a ``BaseExceptionGroup`` —
    which is *not* an ``Exception`` subclass, so a bare ``except Exception``
    silently lets it through and ``callbacks.on_error`` never fires.

    To restore correct error reporting we widen the runner's catch to
    ``BaseException`` and use this predicate to decide whether to re-raise
    the group: only re-raise when *every* leaf is a cancellation, which is
    the signature of a true outer cancel (FastAPI shutdown, client
    disconnect, explicit ``task.cancel()``).  Mixed groups — the typical
    "CLI exit 1 + sibling cancellations" case — are treated as a regular
    runner failure so ``on_error`` fires and the service emits the SSE
    ``error`` frame.
    """

    leaves = _iter_exception_leaves(exc)
    if not leaves:
        return False
    return all(isinstance(leaf, asyncio.CancelledError) for leaf in leaves)


def _csv_env_values(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_allowed_tools() -> list[str]:
    """Resolve the default chat tool allowlist from env.

    ``PAWKEYLAND_AGENT_ALLOWED_TOOLS`` may override this with a comma-separated
    list. Leave the env var unset to use the default touch-animation tool.
    """

    return _csv_env_values("PAWKEYLAND_AGENT_ALLOWED_TOOLS") or list(DEFAULT_ALLOWED_TOOLS)


def _user_mcp_enabled() -> bool:
    raw = os.getenv("PAWKEYLAND_ENABLE_AGENT_USER_MCP", "").strip().lower()
    if raw in _FALSE_ENV_VALUES:
        return False
    if raw in _TRUE_ENV_VALUES:
        return True
    return True


def _necklace_mcp_enabled() -> bool:
    raw = os.getenv("PAWKEYLAND_ENABLE_AGENT_NECKLACE_MCP", "").strip().lower()
    if raw in _FALSE_ENV_VALUES:
        return False
    if raw in _TRUE_ENV_VALUES:
        return True
    return True


def _memory_mcp_enabled() -> bool:
    raw = _first_env_value(
        "INK_AGENT_ENABLE_MEMORY_MCP",
        "PAWKEYLAND_ENABLE_AGENT_MEMORY_MCP",
    ).lower()
    if raw in _FALSE_ENV_VALUES:
        return False
    if raw in _TRUE_ENV_VALUES:
        return True
    return True


def _pythonpath_with_repo_root() -> str:
    """Return a PYTHONPATH that lets Claude-spawned MCP subprocesses import this repo."""

    repo_root = str(_REPO_ROOT)
    current = os.getenv("PYTHONPATH", "")
    if not current:
        return repo_root
    parts = [item for item in current.split(os.pathsep) if item]
    if repo_root in parts:
        return current
    return os.pathsep.join([repo_root, *parts])


def _stdio_env(
    *,
    extra_env: Optional[dict[str, str]] = None,
    include_memory_config: bool = False,
    include_necklace_config: bool = False,
) -> dict[str, str]:
    env = {
        "PYTHONPATH": _pythonpath_with_repo_root(),
        "PYTHONUNBUFFERED": "1",
    }
    if include_necklace_config:
        for name in _NECKLACE_ENV_NAMES:
            value = os.getenv(name, "")
            if value:
                env[name] = value
    if include_memory_config:
        for canonical_name, legacy_name in _MEMORY_ENV_ALIASES:
            value = _first_env_value(canonical_name, legacy_name)
            if value:
                _set_env_aliases(env, canonical_name, legacy_name, value)
    for key, value in (extra_env or {}).items():
        if value is not None:
            env[str(key)] = str(value)
    return env


def _user_mcp_stdio_config(extra_env: Optional[dict[str, str]] = None) -> McpStdioServerConfig:
    """Build the external stdio MCP config for the user animation + session tool server.

    *extra_env* is forwarded to ``_stdio_env`` so that session-scoped bindings
    (e.g. ``INK_AGENT_USER_ID``) reach the subprocess.
    """

    return McpStdioServerConfig(
        type="stdio",
        command=sys.executable,
        args=["-m", "libs.claude_agent_kit.server.user_mcp_stdio"],
        env=_stdio_env(extra_env=extra_env),
    )


def _necklace_mcp_stdio_config(extra_env: Optional[dict[str, str]] = None) -> McpStdioServerConfig:
    """Build the external stdio MCP config for the necklace live-context server."""

    return McpStdioServerConfig(
        type="stdio",
        command=sys.executable,
        args=["-m", "libs.claude_agent_kit.server.necklace_mcp_stdio"],
        env=_stdio_env(extra_env=extra_env, include_necklace_config=True),
    )


def _memory_mcp_stdio_config(extra_env: Optional[dict[str, str]] = None) -> McpStdioServerConfig:
    """Build the external stdio MCP config for the Mem0 shared-story server."""

    return McpStdioServerConfig(
        type="stdio",
        command=sys.executable,
        args=["-m", "libs.claude_agent_kit.server.memory_mcp_stdio"],
        env=_stdio_env(extra_env=extra_env, include_memory_config=True),
    )


def _editor_mcp_stdio_config() -> McpStdioServerConfig:
    """Build the external stdio MCP config for the EditorState write-only server.

    Session context (session_id) is supplied by the Claude agent at tool-call
    time — the agent reads it from the ``<workspace_context>`` prompt block and
    includes it as a required argument in every write tool call.  No session
    data needs to be injected into the subprocess environment here.
    """
    return McpStdioServerConfig(
        type="stdio",
        command=sys.executable,
        args=["-m", "libs.claude_agent_kit.server.editor_mcp_stdio"],
        env=_stdio_env(),
    )


# ---------------------------------------------------------------------------
# .editor/ virtual index redirect helper
# ---------------------------------------------------------------------------


def _apply_editor_index_redirect(
    tool_name: str,
    tool_input: dict[str, Any],
    editor_state: Optional[dict[str, Any]],
    tmp_paths: list[str],
) -> Optional[HookJSONOutput]:
    """Apply `.editor/` virtual-index redirect for a PreToolUse Read call.

    Returns a hook output dict whose ``hookSpecificOutput.updatedInput`` points
    to a freshly written tempfile when all three conditions are satisfied:

    1. ``tool_name == "Read"``
    2. ``editor_state`` is not ``None``
    3. The ``file_path`` input targets a recognised ``.editor/`` resource

    Returns ``None`` when any condition is not met (fall-through).

    Side effects:
    - On success, appends the tempfile path to *tmp_paths* so the caller can
      clean it up in a ``finally`` block.

    On any exception the error is logged at WARNING level and ``None`` is
    returned so the caller falls through to the unmodified read path (the
    agent sees the on-disk placeholder ``{}``).

    This function is module-level so it can be tested in isolation without
    running a real Claude Code SDK subprocess.

    Design reference: ``docs/design/claude-agent/edit-point/workspace-adapter.md``
    §4.2 Interception conditions, §4.3 Interception flow.
    """
    if tool_name != "Read" or editor_state is None:
        return None

    raw_path: str = tool_input.get("file_path", "")

    try:
        from .editor_index import is_editor_index_path, get_editor_resource_data  # noqa: PLC0415

        if not is_editor_index_path(raw_path):
            return None

        resource_data = get_editor_resource_data(raw_path, editor_state)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            prefix="editor_",
            encoding="utf-8",
        ) as tmp:
            json.dump(resource_data, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        tmp_paths.append(tmp_path)
        logger.debug(
            "PreToolUse: redirected .editor read %r → %r",
            raw_path,
            tmp_path,
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"file_path": tmp_path},
            }
        }
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to intercept .editor/ read for %r; falling through.",
            raw_path,
            exc_info=True,
        )
        return None


def _extract_workspace_boundary_path(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Return the filesystem path argument used by a built-in file/search tool.

    Claude Code built-ins use different input keys: Read/Write/Edit use
    ``file_path``, Grep/Glob/LS use ``path``, and NotebookRead uses
    ``notebook_path``.  Grep/Glob may omit ``path`` to mean the current working
    directory; return an empty string so the caller resolves that as ``cwd``.
    """

    if tool_name == "NotebookRead":
        raw_path = tool_input.get("notebook_path")
    else:
        raw_path = tool_input.get("file_path") or tool_input.get("path")
    return str(raw_path).strip() if raw_path is not None else ""


def _is_path_inside_workspace_root(raw_path: str, cwd: Optional[str]) -> bool:
    """Return True when *raw_path* resolves inside the session workspace root."""

    if not cwd:
        return False

    try:
        workspace = Path(cwd).expanduser().resolve(strict=False)
        candidate = Path(raw_path).expanduser() if raw_path else workspace
        if not candidate.is_absolute():
            candidate = workspace / candidate
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(workspace)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _workspace_boundary_deny(reason_path: str) -> HookJSONOutput:
    """Return a hard deny for built-in file/search tools outside thread cwd."""

    display_path = reason_path or "."
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Workspace sandbox boundary: built-in file/search tools may "
                f"only access the current thread workspace; rejected path {display_path!r}."
            ),
        }
    }


def _apply_workspace_boundary_permission(
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: Optional[str],
    *,
    auto_allow_queries: bool,
) -> Optional[HookJSONOutput]:
    """Enforce the thread workspace boundary for built-in file/search tools.

    Claude Code's Bash sandbox is Bash-scoped. Built-in tools such as Read,
    Grep, Glob, and LS are governed by permissions/hooks instead, so enforce
    the same ``{AGENT_CWD}/{thread_id}`` boundary before the generic
    low-sensitivity allow or frontend confirmation paths can run.
    """

    if tool_name not in _WORKSPACE_BOUNDARY_FILE_TOOLS:
        return None

    raw_path = _extract_workspace_boundary_path(tool_name, tool_input)
    if not _is_path_inside_workspace_root(raw_path, cwd):
        return _workspace_boundary_deny(raw_path)

    if auto_allow_queries and tool_name in _WORKSPACE_QUERY_PERMISSION_TOOLS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    return None


def _extract_builtin_file_tool_path(tool_input: dict[str, Any]) -> str:
    """Return the path argument from a built-in Claude file tool input."""

    raw_path = tool_input.get("file_path") or tool_input.get("path") or ""
    return str(raw_path).strip() if raw_path is not None else ""


def _is_path_inside_workspace_files(raw_path: str, cwd: Optional[str]) -> bool:
    """Return True when *raw_path* resolves below ``{cwd}/files/``.

    ``raw_path`` may be absolute or relative to the Claude working directory.
    ``Path.resolve(strict=False)`` keeps non-existent target files checkable
    while resolving existing parent symlinks and ``..`` components.
    """

    if not raw_path or not cwd:
        return False

    try:
        workspace = Path(cwd).expanduser().resolve(strict=False)
        files_dir = (workspace / "files").resolve(strict=False)
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = workspace / candidate
        resolved = candidate.resolve(strict=False)
        if resolved == files_dir:
            return False
        resolved.relative_to(files_dir)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Plan Mode plan-file observation (claude-plan §5.3)
# ---------------------------------------------------------------------------

# Built-in file-mutation tools whose writes can land in the plans directory.
_PLAN_FILE_WRITE_TOOL_NAMES: frozenset[str] = frozenset({
    "Write",
    "Edit",
    "MultiEdit",
})


def _plan_emit_debounce_seconds() -> float:
    """Return the plan-file emit debounce window (seconds) from env config."""

    try:
        raw = os.getenv("INK_AGENT_PLAN_EMIT_DEBOUNCE_MS", "500") or "500"
        return max(0.0, float(raw)) / 1000.0
    except (TypeError, ValueError):
        return 0.5


def _resolve_plans_dir_for_cwd(cwd: Optional[str]) -> Optional[Path]:
    """Return the current run's plans dir, delegating to ``get_plans_dir()``.

    The service layer always sets cwd to the per-thread workspace root
    (``{workspace_root}/{thread_id}``), so the workspace session_id is the
    resolved cwd basename.  Returns ``None`` when cwd is empty (Workspace
    Mode disabled), lies outside the workspace root (e.g. ad-hoc unit-test
    dirs), or no plans directory exists yet.
    """

    if not cwd:
        return None
    try:
        workspace = Path(cwd).expanduser().resolve(strict=False)
        workspace.relative_to(get_workspace_root().resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return None
    try:
        return get_plans_dir(workspace.name)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Task v2 file-task observation (claude-todo §5.3)
# ---------------------------------------------------------------------------

# Built-in v2 task tools whose execution mutates the tasks directory.
# TaskList/TaskGet are read-only and never trigger an emission.
_TASK_V2_WRITE_TOOL_NAMES: frozenset[str] = frozenset({
    "TaskCreate",
    "TaskUpdate",
})


def _todo_emit_debounce_seconds() -> float:
    """Return the todo emit debounce window (seconds) from env config."""

    try:
        raw = os.getenv("INK_AGENT_TODO_EMIT_DEBOUNCE_MS", "500") or "500"
        return max(0.0, float(raw)) / 1000.0
    except (TypeError, ValueError):
        return 0.5


def _resolve_tasks_dir_for_cwd(cwd: Optional[str]) -> Optional[Path]:
    """Return the current run's tasks dir, delegating to ``get_tasks_dir()``.

    Mirrors ``_resolve_plans_dir_for_cwd``: the workspace session_id is the
    resolved cwd basename.  Returns ``None`` when cwd is empty (Workspace
    Mode disabled), lies outside the workspace root, or no v2 tasks have
    been written yet.
    """

    if not cwd:
        return None
    try:
        workspace = Path(cwd).expanduser().resolve(strict=False)
        workspace.relative_to(get_workspace_root().resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return None
    try:
        return get_tasks_dir(workspace.name)
    except Exception:  # noqa: BLE001
        return None


def _plan_file_path_for_hook(
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: Optional[str],
) -> Optional[Path]:
    """Return the resolved plan file path when a write tool targets the plans dir.

    Only built-in ``Write``/``Edit``/``MultiEdit`` calls whose resolved path
    stays inside ``get_plans_dir()`` and ends in ``.md`` qualify; everything
    else returns ``None`` so the PostToolUse hook no-ops.
    """

    if tool_name not in _PLAN_FILE_WRITE_TOOL_NAMES or not cwd:
        return None
    raw_path = _extract_builtin_file_tool_path(tool_input)
    if not raw_path:
        return None
    plans_dir = _resolve_plans_dir_for_cwd(cwd)
    if plans_dir is None:
        return None
    try:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path(cwd).expanduser().resolve(strict=False) / candidate
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(plans_dir)
    except (OSError, RuntimeError, ValueError):
        return None
    if resolved.suffix.lower() != ".md":
        return None
    return resolved


def _apply_workspace_files_permission(
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: Optional[str],
) -> Optional[HookJSONOutput]:
    """Explicitly allow built-in file tools for the session ``files/`` area.

    Claude Code treats ``allowed_tools`` and PreToolUse hook success as separate
    from some built-in file permission prompts. Returning an explicit
    ``permissionDecision: allow`` for the sandboxed workspace files directory
    lets agents create or edit normal workspace artifacts without granting
    access to source code, ``.editor/``, or other workspace internals.
    """

    if tool_name not in _WORKSPACE_FILES_PERMISSION_TOOLS:
        return None

    raw_path = _extract_builtin_file_tool_path(tool_input)
    if not _is_path_inside_workspace_files(raw_path, cwd):
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def _apply_low_sensitivity_query_permission(
    tool_name: str,
    tool_input: Optional[dict[str, Any]] = None,
) -> Optional[HookJSONOutput]:
    """Explicitly allow auto-mode tools whose product class is low-sensitivity.

    Returning an empty ``{}`` would merely decline to make a hook
    decision and let Claude Code's own permission layer decide. These low-risk
    query tools should skip both the frontend confirmation side-channel and
    Claude Code's native permission prompt in auto mode, so the hook must return
    an explicit ``permissionDecision: "allow"``.

    Special case — ``Bash``: only read-only/navigation commands qualify. Any
    command containing shell metacharacters is treated as high-sensitivity and
    falls through to frontend confirmation.
    """

    if tool_name in _LOW_SENSITIVITY_QUERY_TOOL_NAMES:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    if tool_name == "Bash":
        command = str((tool_input or {}).get("command") or "").strip()
        if _is_low_sensitivity_bash_command(command):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                }
            }

    return None


def _explicit_pre_tool_use_allow() -> HookJSONOutput:
    """Return the CLI 2.1+ explicit allow shape for PreToolUse hooks."""

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def _extract_hook_tool_name(hook_input: dict[str, Any]) -> str:
    """Return tool name from Claude hook payloads.

    Claude Code hook JSON is documented as ``tool_name`` / ``tool_input``, but
    adjacent SDK/control-protocol surfaces and frontend events use camelCase.
    Accept both so a payload shaped like ``{"toolName": "Skill"}`` still uses
    the low-sensitivity policy instead of falling through as an unknown tool.
    """

    value = hook_input.get("tool_name")
    if value is None:
        value = hook_input.get("toolName")
    return str(value or "")


def _extract_hook_tool_input(hook_input: dict[str, Any]) -> dict[str, Any]:
    """Return tool input from Claude hook payloads in snake or camel case."""

    value = hook_input.get("tool_input")
    if value is None:
        value = hook_input.get("toolInput")
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------


async def _call(fn: Optional[Callable[..., Any]], *args: Any) -> None:
    """Invoke *fn* with *args*, awaiting it if it returns a coroutine."""
    if fn is None:
        return
    result = fn(*args)
    if inspect.isawaitable(result):
        await result


async def _await_confirmation(
    callback: Callable[..., Any],
    payload: dict[str, Any],
    *,
    host_loop: Optional[asyncio.AbstractEventLoop],
) -> Optional[dict[str, Any]]:
    """Run a tool-confirmation callback on the host (FastAPI) event loop.

    The Claude Code SDK invokes PreToolUse hooks from a control-protocol task
    inside its anyio TaskGroup. Today that task runs on the same loop as
    ``run_streaming``, so a direct ``await`` is fine. Future SDK changes (or
    custom transports) may move hook dispatch to a worker thread or a sub-loop;
    in those cases we must hop back to the loop that owns the
    ToolConfirmationStore Future before awaiting it, otherwise the FastAPI
    worker is starved while the confirmation Future is unreachable.

    The bridge stays on the same loop when caller and host already match, so
    auto-mode and existing tests pay no cost.
    """

    raw = callback(payload)

    if not inspect.isawaitable(raw):
        return raw  # type: ignore[return-value]

    coro = raw  # An awaitable; usually a coroutine

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if host_loop is None or running_loop is host_loop:
        return await coro  # type: ignore[no-any-return]

    if not host_loop.is_running():
        # The host loop disappeared (server shutdown). Best-effort: drop the
        # awaitable and let the caller fall through to the default deny path.
        if hasattr(coro, "close"):
            try:
                coro.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
        return None

    future = asyncio.run_coroutine_threadsafe(coro, host_loop)  # type: ignore[arg-type]
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.cancel()
        raise


def _block_value(block: Any, key: str, default: Any = None) -> Any:
    """Read a content-block field from SDK objects or raw dict blocks."""

    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _block_type(block: Any) -> Optional[str]:
    """Infer SDK content-block type from dict fields or SDK class names."""

    explicit = _block_value(block, "type")
    if isinstance(explicit, str) and explicit:
        return explicit

    block_name = type(block).__name__
    if block_name == "TextBlock":
        return "text"
    if block_name == "ThinkingBlock":
        return "thinking"
    if block_name == "ToolUseBlock":
        return "tool_use"
    if block_name == "ToolResultBlock":
        return "tool_result"
    return None


def _maybe_json(value: str) -> Any:
    text = str(value or "").strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _normalize_tool_result_output(content: Any) -> Any:
    """Return tool_result content in the most useful SSE shape.

    Claude Code may surface MCP results as SDK block objects or raw dicts. For
    JSON text results, parse to a dict so the frontend can inspect fields
    without re-parsing a text blob.
    """

    if isinstance(content, str):
        return _maybe_json(content)
    if not isinstance(content, list):
        return content

    text_parts: list[str] = []
    for item in content:
        if _block_type(item) == "text":
            text = _block_value(item, "text", "")
            if isinstance(text, str):
                text_parts.append(text)

    if text_parts:
        combined = "".join(text_parts).strip()
        return _maybe_json(combined)
    return content


# ---------------------------------------------------------------------------
# ClaudeAgentRunner
# ---------------------------------------------------------------------------


class ClaudeAgentRunner:
    """Unified streaming runner for the Claude Agent SDK.

    Maps to TypeScript ``ClaudeAgentRunner`` in agent-runner.ts.
    """

    def __init__(self, sdk_client: Optional[IClaudeAgentSDKClient] = None) -> None:
        self._sdk_client: IClaudeAgentSDKClient = (
            sdk_client or SimpleClaudeAgentSDKClient()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_streaming(
        self,
        opts: AgentRunOptions,
        callbacks: AgentStreamingCallbacks,
    ) -> AgentRunResult:
        """Run the agent and deliver events via *callbacks*.

        Maps to TypeScript ``runStreaming``.
        """
        thread_id = opts.thread_id
        user_message = opts.user_message
        resume = opts.resume
        model = opts.model
        cwd = opts.cwd
        max_turns = opts.max_turns
        allowed_tools = (
            list(opts.allowed_tools)
            if opts.allowed_tools is not None
            else _default_allowed_tools()
        )
        tool_choice: ToolChoiceMode = opts.tool_choice
        if tool_choice == "auto":
            for required_tool in _AUTO_MODE_REQUIRED_ALLOWED_TOOLS:
                if required_tool not in allowed_tools:
                    allowed_tools.append(required_tool)
        sandbox_network_mode = str(opts.sandbox_network_mode or "allowlist")
        system_prompt = opts.system_prompt
        mcp_env = dict(opts.mcp_env or {})
        turn_runtime = dict(opts.turn_runtime or {})

        include_partial_messages = True

        # Accumulators
        messages: list[Any] = []
        text_parts: list[str] = []
        # Initialise to None so that a run that fails before the SDK emits any
        # ResultMessage does not return the conversation_id as the session_id.
        # If the run succeeds the SDK always emits a ResultMessage whose
        # session_id is a real UUID, which overwrites this value below.
        current_session_id: Optional[str] = None
        success = True
        run_error: Optional[Exception] = None
        usage: dict[str, Optional[int]] = {}

        # Pending tool-call tracker (tool_call_id → {tool_name, input})
        pending_tool_calls: dict[str, dict[str, Any]] = {}
        emitted_tool_input_ids: set[str] = set()
        # Streaming tool-call tracker keyed by content block index. Claude
        # streams tool arguments as input_json_delta chunks after an initially
        # empty content_block_start; emit one complete tool event at block stop.
        pending_stream_tools: dict[int, dict[str, Any]] = {}
        pending_stream_thinking: dict[int, dict[str, Any]] = {}

        # Build user message content blocks for the SDK.
        # When the caller (e.g. ClaudeAgentContextBuilder.build_user_message) has
        # already produced a list of content blocks, use them directly.
        # For plain-string messages (e.g. in tests) wrap the text in a single block.
        if isinstance(user_message, list):
            user_msg_content = user_message
        else:
            user_msg_content = [{"type": "text", "text": user_message}]
        user_msg_dict: dict[str, Any] = {
            "type": "user",
            "uuid": str(uuid4()),
            "session_id": thread_id,
            "parent_tool_use_id": None,
            "message": {
                "role": "user",
                "content": user_msg_content,
            },
        }

        # Disable all tools when tool_choice == "none"
        effective_allowed_tools = [] if tool_choice == "none" else allowed_tools

        async def _generate_messages():
            yield user_msg_dict

        # ------------------------------------------------------------------
        # PreToolUse hook
        # Fired by the SDK before tool execution. Auto mode directly allows
        # bounded workspace files/ file operations and explicit query tools;
        # execution/write/state/interactive tools use the frontend confirmation
        # side-channel. Manual mode uses the frontend confirmation side-channel
        # for every non-.editor virtual-index read.
        #
        # Loop / thread contract (manual mode)
        # -----------------------------------
        # Capture the FastAPI worker loop here, while ``run_streaming`` is
        # still on the awaiting coroutine. Whatever loop or thread the SDK
        # later uses to dispatch the hook, we must run the application's
        # ``on_tool_confirmation_request`` coroutine on this loop so the
        # ToolConfirmationStore Future that gets registered is owned by it.
        # That keeps ``POST /api/claude-agent/tool-confirm`` resolvable from
        # the same loop and prevents the worker from being blocked by a
        # cross-loop wakeup.
        # ------------------------------------------------------------------
        try:
            host_loop: Optional[asyncio.AbstractEventLoop] = (
                asyncio.get_running_loop()
            )
        except RuntimeError:  # pragma: no cover — run_streaming is async
            host_loop = None

        # Collects paths of per-read tempfiles created by the .editor/ redirect
        # logic inside _pre_tool_use_hook. Cleaned up in the finally block.
        _editor_redirect_tmp_paths: list[str] = []

        async def _pre_tool_use_hook(
            hook_input: dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> HookJSONOutput:
            del context
            tool_name = _extract_hook_tool_name(hook_input)
            tool_input = _extract_hook_tool_input(hook_input)
            tool_call_id = tool_use_id or str(uuid4())
            pending_tool_calls[tool_call_id] = {
                "tool_name": tool_name,
                "input": tool_input,
            }

            # ----------------------------------------------------------
            # .editor/ virtual index interception (Read tool only)
            # When the agent reads a file under .editor/, redirect to a
            # tempfile populated with live editor_state data so the agent
            # gets real content instead of the placeholder `{}`.
            # This must run before the tool_choice / manual-confirm checks
            # so virtual-index reads are always served in all modes.
            # Delegated to the module-level _apply_editor_index_redirect
            # helper so it can be unit-tested without a real SDK subprocess.
            #
            # Read the editor_state from the AgentRunState flyweight via
            # opts.editor_state_getter (injected by service.py as
            # lambda: state.editor_state) so we always see the latest value —
            # including updates written back after a confirmed MCP write-tool
            # result.  Fall back to the snapshot in opts.editor_state when the
            # getter is not provided (e.g. unit tests, direct runner calls).
            # ----------------------------------------------------------
            live_editor_state = (
                opts.editor_state_getter()
                if opts.editor_state_getter is not None
                else opts.editor_state
            )
            redirect_result = _apply_editor_index_redirect(
                tool_name, tool_input, live_editor_state, _editor_redirect_tmp_paths
            )
            if redirect_result is not None:
                return redirect_result

            disabled_network_permission = _apply_disabled_network_permission(
                sandbox_network_mode,
                tool_name,
                tool_input,
            )
            if disabled_network_permission is not None:
                return disabled_network_permission

            workspace_boundary_permission = _apply_workspace_boundary_permission(
                tool_name,
                tool_input,
                cwd,
                auto_allow_queries=(tool_choice == "auto"),
            )
            if workspace_boundary_permission is not None:
                return workspace_boundary_permission

            if (
                opts.im_full_access_enabled
                and tool_choice != "none"
                and tool_name not in _ANSWER_FORM_TOOL_NAMES
            ):
                return _explicit_pre_tool_use_allow()

            if tool_choice == "auto":
                workspace_files_permission = _apply_workspace_files_permission(
                    tool_name, tool_input, cwd
                )
                if workspace_files_permission is not None:
                    return workspace_files_permission

                low_sensitivity_permission = _apply_low_sensitivity_query_permission(
                    tool_name, tool_input
                )
                if low_sensitivity_permission is not None:
                    return low_sensitivity_permission

            # In auto mode, workspace files/ built-in file tools plus explicit
            # low-sensitivity query/context-selection/Skill tools are allowed
            # above. Execution, write, and interactive tools fall through to
            # the frontend confirmation side-channel so approval is visible and
            # becomes an explicit Claude Code permission decision.

            if callbacks.on_tool_confirmation_request:
                confirmation_payload = {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "input": tool_input,
                }
                try:
                    confirmation_result = await _await_confirmation(
                        callbacks.on_tool_confirmation_request,
                        confirmation_payload,
                        host_loop=host_loop,
                    )
                except asyncio.CancelledError:
                    pending_tool_calls.pop(tool_call_id, None)
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Tool confirmation callback failed: tool_call_id=%s tool_name=%s",
                        tool_call_id,
                        tool_name,
                    )
                    pending_tool_calls.pop(tool_call_id, None)
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "工具确认回调异常",
                        }
                    }

                if (
                    confirmation_result
                    and isinstance(confirmation_result, dict)
                    and "approved" in confirmation_result
                ):
                    if confirmation_result["approved"] is True:
                        pending_tool_calls.pop(tool_call_id, None)
                        updated_input: dict[str, Any] = tool_input

                        # For AskUserQuestion-style tools, merge answers with the
                        # full original input so Claude sees the complete context.
                        # Supports both the classic Q&A format
                        #   { questions: [...], answers: {...} }
                        # and the animation event format
                        #   { act, duration, interaction, answers: {...} }
                        # (defined in docs/app/design/LLM驱动动画事件图设计方案.md)
                        # Note: tool_input originates from Claude (LLM-generated),
                        # not from external HTTP requests, so spreading it is safe.
                        has_answers = bool(confirmation_result.get("answers"))
                        if has_answers and tool_name in (
                            "AskUserQuestion",
                            "mcp__user__ask_user",
                            # Animation event tool — merge frontend answers per §9.5
                            "mcp__user__touch_animation",
                        ):
                            updated_input = {
                                **tool_input,
                                "answers": confirmation_result["answers"],
                            }
                            # CLI ≥ 2.1 expects the PreToolUse hookSpecificOutput
                            # shape: hookEventName + permissionDecision:"allow" +
                            # updatedInput (the old {"tool_input": ...} key is no
                            # longer recognised and causes the override to be silently
                            # ignored, leaving AskUserQuestion without answers and
                            # returning isError:true / output:null).
                            return {
                                "hookSpecificOutput": {
                                    "hookEventName": "PreToolUse",
                                    "permissionDecision": "allow",
                                    "updatedInput": updated_input,
                                }
                            }

                        return {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "allow",
                            }
                        }

                    if confirmation_result["approved"] is False:
                        pending_tool_calls.pop(tool_call_id, None)
                        reason = (
                            confirmation_result.get("reason")
                            or "用户拒绝执行该工具"
                        )
                        return {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "deny",
                                "permissionDecisionReason": reason,
                            }
                        }

            # No callback or no result — deny by default
            pending_tool_calls.pop(tool_call_id, None)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "需要用户确认但未收到响应",
                }
            }

        # ------------------------------------------------------------------
        # can_use_tool callback (SDK control channel) — the SINGLE network
        # confirmation channel.
        #
        # The CLI's sandbox-runtime network ask is a SYSTEM-LEVEL control
        # request raised when sandboxed Bash hits a non-allowlisted host at
        # the sandbox-runtime proxy.  It is NOT visible to PreToolUse — it
        # arrives only through this channel as
        #   tool_name == "SandboxNetworkAccess", input == {"host": <hostname>}
        # (restored-src cli/structuredIO.ts).  Route it through the frontend
        # confirmation side-channel with the sandbox_network discriminator.
        # (The PreToolUse-layer network gate was removed 2026-07-26 — network
        # policy is enforced by the CLI's own sandbox; this channel is the
        # only place per-request network approval happens.)
        #
        # Other tool names: per the official contract, can_use_tool never
        # fires for tools already resolved earlier in the permission flow —
        # our PreToolUse hook returns explicit allow/deny for everything, so
        # this branch should rarely fire (no double-prompting).  It still
        # routes through the same generic confirmation chain for consistent
        # UX and future-proofing.
        #
        # Always fail closed: any exception or missing callback denies.
        # ------------------------------------------------------------------

        async def _can_use_tool(
            tool_name: str,
            input_data: dict[str, Any],
            context: ToolPermissionContext,
        ) -> PermissionResult:
            del context
            is_sandbox_network_ask = tool_name == SANDBOX_NETWORK_ACCESS_TOOL_NAME
            host = (
                str(input_data.get("host") or "").strip().lower() or None
                if is_sandbox_network_ask and isinstance(input_data, dict)
                else None
            )

            def _sandbox_deny(reason: str) -> PermissionResultDeny:
                target = host or "unknown host"
                return PermissionResultDeny(
                    message=(
                        f"{reason}（目标主机：{target}。如需长期放行，"
                        "可在设置中将该域名加入沙箱网络 allowedDomains。）"
                    )
                )

            if not callbacks.on_tool_confirmation_request:
                if is_sandbox_network_ask:
                    return _sandbox_deny("网络访问需要用户确认，但确认通道不可用")
                return PermissionResultDeny(message="需要用户确认但未收到响应")

            tool_call_id = str(uuid4())
            confirmation_payload: dict[str, Any] = {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "input": input_data,
            }
            if is_sandbox_network_ask:
                confirmation_payload["confirmationKind"] = (
                    SANDBOX_NETWORK_CONFIRMATION_KIND
                )
                confirmation_payload["networkRequest"] = {
                    "host": host,
                    "policyMode": sandbox_network_mode,
                    "matchedAllowedDomain": None,
                }

            try:
                confirmation_result = await _await_confirmation(
                    callbacks.on_tool_confirmation_request,
                    confirmation_payload,
                    host_loop=host_loop,
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — fail closed
                logger.warning(
                    "can_use_tool confirmation failed: tool_name=%s host=%s",
                    tool_name,
                    host,
                    exc_info=True,
                )
                if is_sandbox_network_ask:
                    return _sandbox_deny("网络访问确认失败，已拦截")
                return PermissionResultDeny(message="工具确认回调异常")

            if (
                confirmation_result
                and isinstance(confirmation_result, dict)
                and confirmation_result.get("approved") is True
            ):
                updated_input: dict[str, Any] = dict(input_data or {})
                # Mirror PreToolUse step ⑦: merge frontend answers into the
                # input for AskUserQuestion-style tools so Claude receives
                # the collected responses.
                if confirmation_result.get("answers") and tool_name in (
                    "AskUserQuestion",
                    "mcp__user__ask_user",
                    "mcp__user__touch_animation",
                ):
                    updated_input = {
                        **updated_input,
                        "answers": confirmation_result["answers"],
                    }
                return PermissionResultAllow(updated_input=updated_input)

            reason = (
                (confirmation_result or {}).get("reason")
                if isinstance(confirmation_result, dict)
                else None
            )
            if is_sandbox_network_ask:
                return _sandbox_deny(reason or "用户拒绝了该网络访问")
            return PermissionResultDeny(message=reason or "用户拒绝执行该工具")

        # ------------------------------------------------------------------
        # PostToolUse hook
        # Fired by the SDK after a tool has executed and its result is
        # available.  Used exclusively to intercept the switch_editor
        # context-switch tool: after the no-op MCP handler returns ok, this
        # hook reads the target editor_session_id from the tool input, loads
        # the new editor_state from the database, and writes it into the
        # AgentRunState flyweight via opts.editor_state_setter.  Subsequent
        # .editor/ reads in the same turn will see the new document context
        # because PreToolUse reads live_editor_state via opts.editor_state_getter
        # which is bound to the same flyweight.
        # ------------------------------------------------------------------

        async def _post_tool_use_hook(
            hook_input: dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> HookJSONOutput:
            del context
            tool_name = _extract_hook_tool_name(hook_input)

            # Only act on the switch_editor context-switch tool.
            if tool_name != _SWITCH_EDITOR_MCP_TOOL_NAME:
                return {}

            if opts.editor_state_setter is None:
                logger.warning(
                    "PostToolUse: switch_editor fired but editor_state_setter is None; "
                    "skipping context switch."
                )
                return {}

            tool_input = _extract_hook_tool_input(hook_input)
            new_session_id: str = str(tool_input.get("editor_session_id") or "").strip()
            if not new_session_id:
                logger.warning(
                    "PostToolUse: switch_editor missing editor_session_id; "
                    "context switch skipped."
                )
                return {}

            try:
                new_state = await asyncio.to_thread(load_editor_state_from_db, new_session_id)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "PostToolUse: switch_editor DB load failed for session %r",
                    new_session_id,
                    exc_info=True,
                )
                return {}

            if new_state:
                opts.editor_state_setter(new_state)
                logger.debug(
                    "PostToolUse: editor context switched to session %r", new_session_id
                )
            else:
                logger.warning(
                    "PostToolUse: switch_editor found no editor_state for session %r; "
                    "context switch skipped.",
                    new_session_id,
                )

            return {}

        # ------------------------------------------------------------------
        # PostToolUse hook — Plan Mode plan-file observer (claude-plan §5.3)
        # Fired after built-in Write/Edit/MultiEdit calls; when the resolved
        # target path lands inside the thread workspace plans dir, notify the
        # service layer via callbacks.on_plan_file_changed so it can re-read
        # the plan and emit a plan-updated SSE frame.  Emissions are debounced
        # per resolved file path per turn (INK_AGENT_PLAN_EMIT_DEBOUNCE_MS,
        # default 500ms, leading-edge) — the ExitPlanMode final read in the
        # service layer always captures the terminal version.  This hook never
        # blocks or alters the tool flow.
        # ------------------------------------------------------------------
        _plan_emit_last_ts: dict[str, float] = {}
        plan_debounce_s = _plan_emit_debounce_seconds()

        async def _plan_file_post_tool_use_hook(
            hook_input: dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> HookJSONOutput:
            del tool_use_id, context
            try:
                tool_name = _extract_hook_tool_name(hook_input)
                tool_input = _extract_hook_tool_input(hook_input)
                plan_path = _plan_file_path_for_hook(tool_name, tool_input, cwd)
                if plan_path is None or callbacks.on_plan_file_changed is None:
                    return {}
                key = str(plan_path)
                now = time.monotonic()
                last_emit = _plan_emit_last_ts.get(key)
                if last_emit is not None and (now - last_emit) < plan_debounce_s:
                    return {}
                _plan_emit_last_ts[key] = now
                await _call(callbacks.on_plan_file_changed, key)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "PostToolUse: plan-file observer failed; skipping emit.",
                    exc_info=True,
                )
            return {}

        # ------------------------------------------------------------------
        # PostToolUse hook — Task v2 file-task observer (claude-todo §5.3)
        # Fired after TaskCreate/TaskUpdate calls; re-reads the thread
        # workspace tasks dir, derives the full TodoItem list (read-time
        # semantics: metadata._internal filtered, resolved blockers dropped)
        # and notifies the service layer via callbacks.on_tasks_changed so it
        # can emit a todo-updated SSE frame.  Emissions are debounced per
        # tasks dir per turn (INK_AGENT_TODO_EMIT_DEBOUNCE_MS, default 500ms,
        # leading-edge).  This hook never blocks or alters the tool flow.
        # ------------------------------------------------------------------
        _todo_emit_last_ts: dict[str, float] = {}
        todo_debounce_s = _todo_emit_debounce_seconds()

        async def _tasks_changed_post_tool_use_hook(
            hook_input: dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> HookJSONOutput:
            del tool_use_id, context
            try:
                tool_name = _extract_hook_tool_name(hook_input)
                if tool_name not in _TASK_V2_WRITE_TOOL_NAMES:
                    return {}
                if callbacks.on_tasks_changed is None:
                    return {}
                tasks_dir = _resolve_tasks_dir_for_cwd(cwd)
                if tasks_dir is None:
                    return {}
                key = str(tasks_dir)
                now = time.monotonic()
                last_emit = _todo_emit_last_ts.get(key)
                if last_emit is not None and (now - last_emit) < todo_debounce_s:
                    return {}
                items, _mtime = read_task_items(tasks_dir)
                _todo_emit_last_ts[key] = now
                await _call(callbacks.on_tasks_changed, items)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "PostToolUse: task observer failed; skipping emit.",
                    exc_info=True,
                )
            return {}

        # ------------------------------------------------------------------
        # Build SDK options
        # ------------------------------------------------------------------
        mcp_servers: dict[str, McpServerConfig] = {}
        if _user_mcp_enabled() and any(
            tool.startswith(_USER_MCP_TOOL_PREFIX) for tool in effective_allowed_tools
        ):
            # Use an external stdio MCP process instead of SDK in-process MCP.
            # The Python SDK multiplexes prompt input, permission responses, and
            # SDK MCP messages over the Claude CLI stdin stream; once the prompt
            # reaches EOF, later control writes can fail with
            # "ProcessTransport is not ready for writing".  Stdio MCP gives the
            # tool protocol its own child-process stdin/stdout.
            mcp_servers["user"] = _user_mcp_stdio_config(extra_env=mcp_env)
        if _memory_mcp_enabled() and any(
            tool.startswith(_MEMORY_MCP_TOOL_PREFIX) for tool in effective_allowed_tools
        ):
            mcp_servers["memory"] = _memory_mcp_stdio_config(mcp_env)
        if _necklace_mcp_enabled() and any(
            tool.startswith(_NECKLACE_MCP_TOOL_PREFIX) for tool in effective_allowed_tools
        ):
            mcp_servers["necklace"] = _necklace_mcp_stdio_config(mcp_env)

        # Start the editor MCP subprocess when editor_state is active and at least one
        # write tool is in the effective allowlist.  Session context (session_id) flows
        # through the MCP protocol: the agent reads it from <workspace_context> and
        # passes it as a required argument in every write tool call — no env-var injection.
        if (
            opts.editor_state is not None
            and any(
                tool.startswith(_EDITOR_MCP_TOOL_PREFIX) for tool in effective_allowed_tools
            )
        ):
            mcp_servers["editor"] = _editor_mcp_stdio_config()
            logger.debug("Editor MCP enabled; session context flows via tool arguments.")

        _stderr_buf = tempfile.TemporaryFile()
        sdk_options = apply_project_sdk_runtime_options(
            ClaudeAgentOptions(
                max_turns=max_turns,
                allowed_tools=effective_allowed_tools,
                include_partial_messages=include_partial_messages,
                hooks={
                    "PreToolUse": [HookMatcher(matcher=None, hooks=[_pre_tool_use_hook])],
                    "PostToolUse": [
                        HookMatcher(
                            matcher=None,
                            hooks=[
                                _post_tool_use_hook,
                                _plan_file_post_tool_use_hook,
                                _tasks_changed_post_tool_use_hook,
                            ],
                        )
                    ],
                },
                # SDK control channel for system-level permission asks the
                # PreToolUse hook cannot see — primarily the sandbox-runtime
                # network ask ("SandboxNetworkAccess"); routed through the same
                # frontend confirmation side-channel.
                can_use_tool=_can_use_tool,
                cwd=cwd or os.getcwd(),
                mcp_servers=mcp_servers,
            )
        )
        # CLI binary resolution: pin cli_path to the system/npm CLI when one
        # exists (Docker's apply-seccomp-patched runtime; local npm claude),
        # else leave unset so the SDK falls back to its bundled CLI.  An
        # explicit cli_path on options always wins.
        apply_cli_path_to_options(sdk_options)
        # Plan Mode: point CLAUDE_CONFIG_DIR at {cwd}/.claude-home so CLI plan
        # files land in the per-thread workspace (claude-plan §5.1).  Lowest
        # priority in the env chain: an explicit CLAUDE_CONFIG_DIR already on
        # options.env is preserved, and the user_sdk_env merge below still
        # overlays on top.  No-op when cwd is falsy (Workspace Mode disabled).
        apply_plan_mode_env_to_options(sdk_options, cwd)
        # Task v2 (claude-todo §5.1): always pin CLAUDE_CODE_TASK_LIST_ID=main
        # at the same lowest priority (explicit values preserved; user_sdk_env
        # below still overlays on top) so the new CLI's default-on task tools
        # write to the list dir get_tasks_dir() resolves; the legacy
        # INK_AGENT_TASK_V2_ENABLED gate only adds an explicit
        # CLAUDE_CODE_ENABLE_TASKS=1.
        apply_task_v2_env_to_options(sdk_options)
        # Overlay user-scoped SDK env vars (higher priority than backend/.env).
        apply_user_sdk_env_to_options(sdk_options, opts.user_sdk_env or {})
        existing_extra_args = getattr(sdk_options, "extra_args", None)
        sdk_options.extra_args = dict(existing_extra_args or {})
        if tool_choice == "none":
            sdk_options.extra_args["tools"] = ""
        # claude-agent-sdk pipes CLI stderr only when an `stderr` callback is
        # registered (the legacy debug_stderr file object is no longer read).
        sdk_options.stderr = _make_cli_stderr_capture(_stderr_buf)
        if resume:
            sdk_options.resume = thread_id
        _apply_request_model_override_if_allowed(sdk_options, model)
        if system_prompt:
            sdk_options.system_prompt = system_prompt
        # ------------------------------------------------------------------
        # Stream processing
        # ------------------------------------------------------------------
        def _accumulate(delta: str) -> None:
            text_parts.append(delta)

        try:
            _inject_mem0_session_hook_env(sdk_options, mcp_env)
            _verify_claude_sdk_env_for_query_stream(sdk_options)
            async for message in self._sdk_client.query_stream(
                _generate_messages(), sdk_options
            ):
                messages.append(message)

                # Track session ID
                if isinstance(message, (ResultMessage, StreamEvent)):
                    if message.session_id:
                        current_session_id = message.session_id
                elif isinstance(message, SystemMessage):
                    sid = (message.data or {}).get("session_id")
                    if sid:
                        current_session_id = sid

                # Raw message callback
                await _call(callbacks.on_message, message)

                # Route to typed handler
                await self._process_message(
                    message=message,
                    callbacks=callbacks,
                    pending_tool_calls=pending_tool_calls,
                    emitted_tool_input_ids=emitted_tool_input_ids,
                    pending_stream_tools=pending_stream_tools,
                    pending_stream_thinking=pending_stream_thinking,
                    on_text_accumulate=_accumulate,
                    include_partial_messages=include_partial_messages,
                    usage_accumulator=usage,
                )

            full_text = "".join(text_parts)

            if full_text and callbacks.on_text_done:
                await _call(callbacks.on_text_done, full_text)

        except BaseException as exc:  # noqa: BLE001
            # ----------------------------------------------------------
            # Why ``except BaseException`` (not ``except Exception``)
            # ----------------------------------------------------------
            # ``ClaudeSDKClient`` runs its CLI subprocess + control
            # protocol inside an ``anyio.TaskGroup``.  When the CLI exits
            # non-zero, the message-reader task raises a plain
            # ``Exception`` (the SDK reshapes ``ProcessError`` into a
            # synthetic ``{"type":"error"}`` stream message; see
            # ``claude_agent_sdk._internal.query.Query._read_messages`` —
            # the same place that emits the visible
            # ``ERROR Fatal error in message reader: Command failed with
            # exit code 1`` log line).  As that failure unwinds, the
            # ``async with ClaudeSDKClient(...)`` ``__aexit__`` cancels
            # the still-running write / control sibling tasks, which
            # raise ``CancelledError`` — and the TaskGroup packages the
            # original ``Exception`` together with the sibling
            # ``CancelledError`` instances into a ``BaseExceptionGroup``.
            # ``BaseExceptionGroup`` is *not* an ``Exception`` subclass,
            # so a plain ``except Exception`` silently lets the failure
            # propagate past the runner: ``callbacks.on_error`` never
            # fires, ``success`` keeps its default ``True``, and the
            # caller sees a half-finished stream with no error frame.
            # We catch ``BaseException`` and use ``_is_pure_cancellation``
            # to re-raise only the genuine cancel cases (FastAPI
            # shutdown, client disconnect, explicit ``task.cancel()``)
            # while routing the typical CLI-failure-plus-sibling-cancel
            # group through the normal ``on_error`` path.
            # ----------------------------------------------------------
            if _is_pure_cancellation(exc):
                raise
            success = False
            stderr_snippet = ""
            try:
                _stderr_buf.seek(0)
                stderr_snippet = (
                    _stderr_buf.read(8192)
                    .decode("utf-8", errors="replace")
                    .strip()
                )
            except Exception:  # noqa: BLE001
                pass
            # ----------------------------------------------------------
            # SDK-side diagnostic enrichment.
            #
            # claude_agent_sdk's ``Query._read_messages`` catches the
            # original ``ProcessError`` from the CLI subprocess and
            # forwards only ``str(e)`` through its in-process message
            # stream — every structured field (``exit_code`` / actual
            # ``stderr`` / which session was being resumed) is dropped
            # before the consumer chain re-raises ``Exception(str(e))``.
            # By the time we reach this except block we have only a
            # generic "Command failed with exit code 1" string and no
            # way to tell which run it came from.
            #
            # Two-pronged enrichment that *preserves* the original
            # exception type so downstream ``isinstance`` checks keep
            # working:
            #   * ``run_error.__notes__`` (PEP 678) carries the SDK-call
            #     context as a structured note, visible in formatted
            #     tracebacks and accessible via ``getattr(exc, '__notes__', [])``.
            #   * a logger.exception emits the same fields as a structured
            #     log line plus traceback so backend logs can correlate the
            #     failure with a specific session / cwd / model without grepping.
            # ExceptionGroup *and* BaseExceptionGroup are both re-wrapped
            # (into a plain Exception carrying the joined leaf messages),
            # because exception groups are rarely useful to downstream
            # typed handlers and their default ``str()`` is unreadable.
            # The ``isinstance(exc, _BASE_EXCEPTION_GROUP_TYPES)`` test
            # also covers ``ExceptionGroup`` because PEP 654 makes it a
            # subclass of ``BaseExceptionGroup``.
            # Bare ``BaseException`` leaves that are *not* a cancellation
            # (e.g. ``KeyboardInterrupt`` / ``SystemExit``) are also
            # wrapped so SSE serialisation and ``isinstance(_, Exception)``
            # consumers downstream do not choke on them.
            # ----------------------------------------------------------
            if _BASE_EXCEPTION_GROUP_TYPES and isinstance(
                exc, _BASE_EXCEPTION_GROUP_TYPES
            ):
                run_error = Exception(_format_exception_message(exc))
            elif isinstance(exc, Exception):
                run_error = exc
            else:
                run_error = Exception(_format_exception_message(exc))
            ctx_note = (
                f"[claude_agent_kit] sdk_call_context: "
                f"resume={resume} thread_id={thread_id or 'None'} "
                f"cwd={cwd or 'None'} model={model or 'default'}"
            )
            try:
                run_error.add_note(ctx_note)
                if stderr_snippet:
                    run_error.add_note(f"[claude_agent_kit] cli_stderr: {stderr_snippet}")
                sandbox_hint = _sandbox_runtime_failure_hint(
                    _format_exception_message(exc),
                    stderr_snippet,
                )
                if sandbox_hint:
                    run_error.add_note(f"[claude_agent_kit] sandbox_hint: {sandbox_hint}")
            except AttributeError:
                # PEP 678 add_note requires Python 3.11+; ignore on older runtimes.
                pass
            logger.exception(
                "Claude SDK run failed: error_type=%s error=%r resume=%s "
                "thread_id=%s cwd=%s model=%s stderr_snippet=%s",
                type(run_error).__name__,
                str(run_error),
                resume,
                thread_id or None,
                cwd or None,
                model or None,
                stderr_snippet or None,
            )
            await _call(callbacks.on_error, run_error)
            full_text = "".join(text_parts)
        finally:
            try:
                _stderr_buf.close()
            except Exception:  # noqa: BLE001
                pass
            # Clean up per-read .editor/ redirect tempfiles.
            for _rpath in _editor_redirect_tmp_paths:
                try:
                    os.unlink(_rpath)
                except Exception:  # noqa: BLE001
                    pass
        return AgentRunResult(
            full_text=full_text,  # type: ignore[possibly-undefined]
            session_id=current_session_id,
            success=success,
            error=run_error,
            messages=messages,
            usage=(
                usage
                if (usage.get("input_tokens") or usage.get("output_tokens"))
                else None
            ),
        )

    async def load_messages(self, session_id: str) -> list[Any]:
        """Load message history for a session.

        Maps to TypeScript ``loadMessages``.
        """
        result = await self._sdk_client.load_messages(session_id)
        return result["messages"]

    # ------------------------------------------------------------------
    # Internal message-processing dispatcher
    # ------------------------------------------------------------------

    async def _process_message(
        self,
        message: Any,
        callbacks: AgentStreamingCallbacks,
        pending_tool_calls: dict[str, dict[str, Any]],
        emitted_tool_input_ids: set[str],
        on_text_accumulate: Callable[[str], None],
        include_partial_messages: bool = False,
        usage_accumulator: Optional[dict[str, Optional[int]]] = None,
        pending_stream_tools: Optional[dict[int, dict[str, Any]]] = None,
        pending_stream_thinking: Optional[dict[int, dict[str, Any]]] = None,
    ) -> None:
        """Dispatch a single SDK message to the appropriate callback(s).

        Maps to TypeScript ``processMessage`` (private method).
        """
        if usage_accumulator is None:
            usage_accumulator = {}

        # ------------------------------------------------------------------
        # assistant message — full content snapshot
        # ------------------------------------------------------------------
        if isinstance(message, AssistantMessage):
            content = message.content or []
            if isinstance(content, list):
                for block in content:
                    block_type = _block_type(block)

                    if block_type == "text":
                        # When include_partial_messages is on, text was already
                        # delivered via stream_event text_deltas — skip to avoid
                        # duplicating output.
                        if not include_partial_messages:
                            text = _block_value(block, "text", "")
                            if isinstance(text, str):
                                on_text_accumulate(text)
                                await _call(callbacks.on_text_delta, text)

                    elif block_type == "thinking":
                        thinking = _block_value(block, "thinking")
                        if isinstance(thinking, str) and callbacks.on_tool_event:
                            await _call(
                                callbacks.on_tool_event,
                                ToolEventPayload(type="thinking", output=thinking),
                            )

                    elif block_type == "tool_use":
                        tool_call_id = _block_value(block, "id")
                        tool_name = _block_value(block, "name")
                        tool_input = _block_value(block, "input", {}) or {}
                        if include_partial_messages and tool_call_id in emitted_tool_input_ids:
                            continue
                        if not include_partial_messages or tool_call_id:
                            if callbacks.on_tool_event:
                                await _call(
                                    callbacks.on_tool_event,
                                    ToolEventPayload(
                                        type="tool_use",
                                        tool_name=tool_name,
                                        tool_call_id=tool_call_id,
                                        input=tool_input,
                                    ),
                                )

            elif isinstance(content, str):
                if not include_partial_messages:
                    on_text_accumulate(content)
                    await _call(callbacks.on_text_delta, content)

        # ------------------------------------------------------------------
        # stream_event — incremental SSE events
        # See docs/app/design/Claude SDK Message 事件类型层级.md for full taxonomy.
        # ------------------------------------------------------------------
        elif isinstance(message, StreamEvent):
            event: dict[str, Any] = message.event or {}
            event_type = event.get("type", "")

            if event_type == "content_block_delta":
                delta = event.get("delta") or {}
                delta_type = delta.get("type", "")

                if delta_type == "text_delta":
                    text = delta.get("text", "")
                    if isinstance(text, str):
                        on_text_accumulate(text)
                        await _call(callbacks.on_text_delta, text)

                elif delta_type == "thinking_delta":
                    block_index = event.get("index")
                    thinking_text = delta.get("thinking")
                    if thinking_text is None:
                        thinking_text = delta.get("text", "")
                    active_thinking: Optional[dict[str, Any]] = None
                    if (
                        pending_stream_thinking is not None
                        and isinstance(block_index, int)
                    ):
                        active_thinking = pending_stream_thinking.setdefault(
                            block_index,
                            {"parts": [], "signature": ""},
                        )
                    if isinstance(thinking_text, str) and callbacks.on_tool_event:
                        if active_thinking is not None:
                            # Keep SDK text chunks as Python str values; no byte
                            # slicing/decoding means multibyte characters remain
                            # intact across delta boundaries.
                            active_thinking.setdefault("parts", []).append(
                                thinking_text
                            )
                        await _call(
                            callbacks.on_tool_event,
                            ToolEventPayload(
                                type="thinking_delta", output=thinking_text
                            ),
                        )

                elif delta_type == "signature_delta":
                    block_index = event.get("index")
                    signature = delta.get("signature")
                    if (
                        isinstance(signature, str)
                        and pending_stream_thinking is not None
                        and isinstance(block_index, int)
                    ):
                        active_thinking = pending_stream_thinking.setdefault(
                            block_index,
                            {"parts": [], "signature": ""},
                        )
                        # signature_delta is block metadata, not display text.
                        # If repeated, the latest complete signature wins.
                        active_thinking["signature"] = signature

                elif delta_type == "input_json_delta":
                    block_index = event.get("index")
                    partial_json = delta.get("partial_json") or ""
                    active_tool: Optional[dict[str, Any]] = None
                    if (
                        pending_stream_tools is not None
                        and isinstance(block_index, int)
                        and block_index in pending_stream_tools
                    ):
                        active_tool = pending_stream_tools[block_index]
                        active_tool.setdefault("parts", []).append(partial_json)

                    if callbacks.on_tool_event:
                        await _call(
                            callbacks.on_tool_event,
                            ToolEventPayload(
                                type="tool_input_delta",
                                tool_name=(
                                    active_tool.get("name")
                                    if active_tool
                                    else None
                                ),
                                tool_call_id=(
                                    active_tool.get("id")
                                    if active_tool
                                    else None
                                ),
                                output=partial_json,
                            ),
                        )

            elif event_type == "content_block_start":
                content_block = event.get("content_block") or {}
                cb_type = content_block.get("type", "")

                if cb_type == "tool_use":
                    tool_call_id = content_block.get("id")
                    tool_name = content_block.get("name")
                    block_index = event.get("index")
                    if (
                        pending_stream_tools is not None
                        and isinstance(block_index, int)
                        and tool_call_id
                        and tool_name
                    ):
                        pending_stream_tools[block_index] = {
                            "id": tool_call_id,
                            "name": tool_name,
                            "parts": [],
                        }
                    elif callbacks.on_tool_event:
                        await _call(
                            callbacks.on_tool_event,
                            ToolEventPayload(
                                type="tool_use_start",
                                tool_name=tool_name,
                                tool_call_id=tool_call_id,
                                input={},
                                state=None,
                            ),
                        )

                elif cb_type == "text" and callbacks.on_tool_event:
                    await _call(
                        callbacks.on_tool_event,
                        ToolEventPayload(
                            type="text_block_start",
                            output={"index": event.get("index")},
                        ),
                    )

                elif cb_type == "thinking":
                    block_index = event.get("index")
                    thinking = content_block.get("thinking")
                    signature = content_block.get("signature")
                    if (
                        pending_stream_thinking is not None
                        and isinstance(block_index, int)
                    ):
                        pending_stream_thinking[block_index] = {
                            "parts": (
                                [thinking]
                                if isinstance(thinking, str) and thinking
                                else []
                            ),
                            "signature": (
                                signature if isinstance(signature, str) else ""
                            ),
                        }
                    if (
                        isinstance(thinking, str)
                        and thinking
                        and callbacks.on_tool_event
                    ):
                        await _call(
                            callbacks.on_tool_event,
                            ToolEventPayload(
                                type="thinking_delta", output=thinking
                            ),
                        )

            elif event_type == "content_block_stop":
                block_index = event.get("index")
                active_tool = (
                    pending_stream_tools.pop(block_index, None)
                    if pending_stream_tools is not None and isinstance(block_index, int)
                    else None
                )
                if active_tool and callbacks.on_tool_event:
                    input_json = "".join(active_tool.get("parts") or [])
                    try:
                        parsed_input: dict[str, Any] = (
                            json.loads(input_json) if input_json else {}
                        )
                        if not isinstance(parsed_input, dict):
                            parsed_input = {"_raw_input_json": input_json}
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "content_block_stop: failed to parse tool input JSON "
                            "for block %s (tool=%s): %r",
                            block_index,
                            active_tool.get("name"),
                            input_json,
                        )
                        parsed_input = {"_raw_input_json": input_json}

                    tool_call_id = active_tool.get("id")
                    tool_name = active_tool.get("name")
                    if tool_call_id:
                        pending_tool_calls[tool_call_id] = {
                            "tool_name": tool_name,
                            "input": parsed_input,
                        }
                        emitted_tool_input_ids.add(tool_call_id)
                    if tool_call_id and tool_name:
                        await _call(
                            callbacks.on_tool_event,
                            ToolEventPayload(
                                type="tool_input_available",
                                tool_name=tool_name,
                                tool_call_id=tool_call_id,
                                input=parsed_input,
                                state="input-available",
                            ),
                        )

                active_thinking = (
                    pending_stream_thinking.pop(block_index, None)
                    if pending_stream_thinking is not None and isinstance(block_index, int)
                    else None
                )
                stop_output: dict[str, Any] = {"index": event.get("index")}
                if active_thinking:
                    stop_output["content_block"] = {
                        "type": "thinking",
                        "thinking": "".join(active_thinking.get("parts") or []),
                        "signature": active_thinking.get("signature") or "",
                    }

                if callbacks.on_tool_event:
                    await _call(
                        callbacks.on_tool_event,
                        ToolEventPayload(
                            type="content_block_stop",
                            output=stop_output,
                        ),
                    )

            elif event_type == "message_start":
                msg_meta = event.get("message") or {}
                msg_usage = msg_meta.get("usage") or {}
                if msg_usage.get("input_tokens"):
                    usage_accumulator["input_tokens"] = (
                        usage_accumulator.get("input_tokens") or 0
                    ) + msg_usage["input_tokens"]

                if callbacks.on_tool_event:
                    await _call(
                        callbacks.on_tool_event,
                        ToolEventPayload(
                            type="message_start",
                            output={
                                "model": msg_meta.get("model"),
                                "usage": msg_usage,
                            },
                        ),
                    )

            elif event_type == "message_delta":
                event_usage = event.get("usage") or {}
                if event_usage.get("output_tokens"):
                    usage_accumulator["output_tokens"] = (
                        usage_accumulator.get("output_tokens") or 0
                    ) + event_usage["output_tokens"]

                if callbacks.on_tool_event:
                    delta = event.get("delta") or {}
                    await _call(
                        callbacks.on_tool_event,
                        ToolEventPayload(
                            type="message_delta",
                            output={
                                "stop_reason": delta.get("stop_reason"),
                                "usage": event_usage,
                            },
                            stop_reason=delta.get("stop_reason"),
                        ),
                    )

            elif event_type == "message_stop":
                if callbacks.on_tool_event:
                    await _call(
                        callbacks.on_tool_event, ToolEventPayload(type="message_stop")
                    )

        # ------------------------------------------------------------------
        # result — session end (subtype: success / error)
        # ------------------------------------------------------------------
        elif isinstance(message, ResultMessage):
            # Cumulative usage in the result event overrides stream-level values
            result_usage = message.usage or {}
            if result_usage.get("input_tokens"):
                usage_accumulator["input_tokens"] = result_usage["input_tokens"]
            if result_usage.get("output_tokens"):
                usage_accumulator["output_tokens"] = result_usage["output_tokens"]

            if callbacks.on_tool_event:
                await _call(
                    callbacks.on_tool_event,
                    ToolEventPayload(
                        type="result",
                        output={
                            "subtype": message.subtype,
                            "result": message.result,
                            "is_error": message.is_error,
                            "duration_ms": message.duration_ms,
                            "num_turns": message.num_turns,
                            "total_cost_usd": message.total_cost_usd,
                            "usage": result_usage,
                        },
                        state=(
                            "output-error" if message.is_error else "output-available"
                        ),
                        is_error=message.is_error,
                    ),
                )

        # ------------------------------------------------------------------
        # user message — contains tool_result content blocks
        # ------------------------------------------------------------------
        elif isinstance(message, UserMessage):
            content = message.content
            if isinstance(content, list):
                for block in content:
                    block_type = _block_type(block)
                    if block_type == "tool_result":
                        tool_use_id = _block_value(block, "tool_use_id") or _block_value(
                            block,
                            "toolUseId",
                        )
                        pending_call = (
                            pending_tool_calls.pop(tool_use_id, None)
                            if tool_use_id
                            else None
                        )
                        if callbacks.on_tool_event:
                            is_err = bool(
                                _block_value(
                                    block,
                                    "is_error",
                                    _block_value(block, "isError", False),
                                )
                            )
                            output = _normalize_tool_result_output(
                                _block_value(block, "content")
                            )
                            await _call(
                                callbacks.on_tool_event,
                                ToolEventPayload(
                                    type="tool_result",
                                    tool_name=(
                                        pending_call.get("tool_name")
                                        if pending_call
                                        else None
                                    ),
                                    tool_call_id=tool_use_id,
                                    output=output,
                                    is_error=is_err,
                                    state=(
                                        "output-error"
                                        if is_err
                                        else "output-available"
                                    ),
                                ),
                            )

        # ------------------------------------------------------------------
        # system — init, hook_started, hook_response (informational only)
        # ------------------------------------------------------------------
        elif isinstance(message, SystemMessage):
            pass  # Not streamed to callbacks

        # ------------------------------------------------------------------
        # Fallback for any other message types from the SDK
        # ------------------------------------------------------------------
        else:
            msg_type = getattr(message, "type", type(message).__name__)

            if msg_type == "tool_progress" and callbacks.on_tool_event:
                await _call(
                    callbacks.on_tool_event,
                    ToolEventPayload(
                        type="tool_progress",
                        tool_name=getattr(message, "tool_name", None),
                        tool_call_id=getattr(message, "tool_use_id", None),
                        output={
                            "elapsed_time_seconds": getattr(
                                message, "elapsed_time_seconds", None
                            )
                        },
                    ),
                )

            elif msg_type == "tool_use_summary" and callbacks.on_tool_event:
                await _call(
                    callbacks.on_tool_event,
                    ToolEventPayload(
                        type="tool_use_summary",
                        output={
                            "summary": getattr(message, "summary", None),
                            "preceding_tool_use_ids": getattr(
                                message, "preceding_tool_use_ids", None
                            ),
                        },
                    ),
                )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def create_agent_runner(
    sdk_client: Optional[IClaudeAgentSDKClient] = None,
) -> ClaudeAgentRunner:
    """Create a new :class:`ClaudeAgentRunner` instance.

    Maps to TypeScript ``createAgentRunner``.
    """
    return ClaudeAgentRunner(sdk_client)
