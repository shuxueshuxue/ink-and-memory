# [Input] Consume backend/.env, process env, and ClaudeAgentOptions-like objects.
# [Output] Provide helpers that merge project/runtime env vars into ClaudeAgentOptions.env
#          and force Claude Code to read project settings only.
# [Pos] SDK environment helper node in libs/claude_agent_kit/server
# [Sync] 2026-05-08: centralize .env injection for ClaudeSDKClient subprocess options.
# [Sync] 2026-05-08: map TypeScript settingSources=["project"] to Python SDK extra_args.
# [Sync] 2026-05-24: load SDK subprocess env from backend/.env by default.
# [Sync] 2026-05-24: keep SDK env injection direct; no app runtime alias mapping.
# [Sync] 2026-05-24: add INK_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE to allowlist (renamed from
#                    PAWKEYLAND_CLAUDE_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE); legacy key kept
#                    for zero-downtime migration.
# [Sync] 2026-06-12: merge Cloud Run/process SDK env after backend/.env so Secret
#                    Manager-injected ANTHROPIC_AUTH_TOKEN reaches the subprocess.
# [Sync] 2026-07-20: add apply_plan_mode_env_to_options() — inject per-thread
#                    CLAUDE_CONFIG_DIR={cwd}/.claude-home at the lowest env
#                    priority so Plan Mode files land in the thread workspace
#                    (claude-plan §5.1); key stays out of the dotenv allowlist.
# [Sync] 2026-07-20: add apply_task_v2_env_to_options() — gated by
#                    INK_AGENT_TASK_V2_ENABLED (default off), injects
#                    CLAUDE_CODE_ENABLE_TASKS=1 / CLAUDE_CODE_TASK_LIST_ID=main
#                    at the lowest env priority so v2 task files land in
#                    {workspace}/.claude-home/tasks/main/ (claude-todo §5.1).
# [Sync] 2026-07-26: SDK migration claude-code-sdk → claude-agent-sdk 0.2.128 —
#                    docstring/type-name updates only (ClaudeAgentOptions);
#                    extra_args["setting-sources"]="project" passthrough is
#                    still correct because the new transport only emits its own
#                    --setting-sources flag when options.setting_sources is set
#                    (we never set it).
# [Sync] 2026-07-26: HOTFIX task-list divergence — the 0.2.128 bundled CLI
#                    enables task tools by default (CLAUDE_CODE_ENABLE_TASKS
#                    !== "0") and falls back to sessionId/teamName taskListId
#                    when CLAUDE_CODE_TASK_LIST_ID is unset, so runs with the
#                    legacy INK_AGENT_TASK_V2_ENABLED gate off wrote tasks to
#                    per-session dirs that get_tasks_dir("main") never found
#                    (empty 计划与待办 panel despite working task tools).
#                    apply_task_v2_env_to_options now ALWAYS pins
#                    CLAUDE_CODE_TASK_LIST_ID=main (lowest priority); the gate
#                    only forces an explicit CLAUDE_CODE_ENABLE_TASKS=1.
# [Sync] 2026-07-26: add apply_cli_path_to_options() — pin options.cli_path to
#                    the system/npm CLI (CLAUDE_CODE_CLI_PATH override →
#                    shutil.which("claude") → leave unset for SDK bundled
#                    fallback) so Docker's apply-seccomp-patched npm CLI is not
#                    shadowed by the SDK bundled CLI; explicit cli_path wins.

"""Runtime option helpers for Claude Code SDK subprocesses."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Optional

from dotenv import dotenv_values

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_ENV_FILE = _BACKEND_ROOT / ".env"
_CLAUDE_SETTING_SOURCES_ARG = "setting-sources"
_CLAUDE_PROJECT_SETTING_SOURCE = "project"

logger = logging.getLogger(__name__)
_PROJECT_DOTENV_SDK_ENV_NAMES = frozenset(
    {
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "API_TIMEOUT_MS",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "DISABLE_INTERLEAVED_THINKING",
        # Request-level model override gate (renamed from Pawkeyland prefix)
        "INK_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE",
        # Legacy key — accepted by agent_runner.py fallback; kept here so old
        # .env files continue to work without redeployment.
        "PAWKEYLAND_CLAUDE_AGENT_ALLOW_REQUEST_MODEL_OVERRIDE",
    }
)
_REMOVED_PROJECT_DOTENV_SDK_ENV_NAMES = frozenset({"ANTHROPIC_API_KEY"})

# Plan Mode config-home injection (claude-plan §5.1).  CLAUDE_CONFIG_DIR is
# deliberately NOT in ``_PROJECT_DOTENV_SDK_ENV_NAMES`` so backend/.env cannot
# relocate the global Claude config home.
_CLAUDE_CONFIG_DIR_ENV_NAME = "CLAUDE_CONFIG_DIR"
_PLAN_MODE_CONFIG_HOME_DIRNAME = ".claude-home"

# Task v2 (file tasks) injection (claude-todo §5.1).  Both keys stay out of
# ``_PROJECT_DOTENV_SDK_ENV_NAMES`` so neither backend/.env nor user_sdk_env
# can flip the v1/v2 tool family or relocate the task list.
_TASK_V2_ENABLED_ENV_NAME = "INK_AGENT_TASK_V2_ENABLED"
_CLAUDE_CODE_ENABLE_TASKS_ENV_NAME = "CLAUDE_CODE_ENABLE_TASKS"
_CLAUDE_CODE_TASK_LIST_ID_ENV_NAME = "CLAUDE_CODE_TASK_LIST_ID"
# Fixed taskListId (claude-todo §5.1): without it the CLI falls back to its
# own sessionId, scattering one thread's tasks across per-session subdirs.
# workspace.get_tasks_dir() resolves the same constant — single source.
CLAUDE_CODE_TASK_LIST_ID_VALUE = "main"
_TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def task_v2_enabled() -> bool:
    """Return whether the legacy v2 opt-in gate is set (claude-todo §5.1).

    Historical note: enabling v2 used to make the CLI expose
    ``TaskCreate``/``TaskUpdate``/``TaskList``/``TaskGet`` and disable v1
    ``TodoWrite`` (official mutual exclusion), so it was an explicit opt-in
    via ``INK_AGENT_TASK_V2_ENABLED``.  The claude-agent-sdk 0.2.128 bundled
    CLI enables task tools **by default** (``CLAUDE_CODE_ENABLE_TASKS !==
    "0"``), so the gate no longer controls tool availability — it only
    forces an explicit ``CLAUDE_CODE_ENABLE_TASKS=1`` injection.  The fixed
    taskListId pinning no longer depends on this gate (see
    :func:`apply_task_v2_env_to_options`).
    """

    raw = os.getenv(_TASK_V2_ENABLED_ENV_NAME, "").strip().lower()
    return raw in _TRUE_ENV_VALUES


def _is_project_dotenv_sdk_env_key(key: str) -> bool:
    """Return whether a backend .env key should be passed to Claude Code."""

    return key in _PROJECT_DOTENV_SDK_ENV_NAMES


def project_dotenv_env(env_file: Optional[Path | str] = None) -> dict[str, str]:
    """Return backend ``.env`` values suitable for ``ClaudeAgentOptions.env``."""
    path = Path(env_file) if env_file is not None else _PROJECT_ENV_FILE
    if not path.exists():
        return {}

    values = dotenv_values(path)
    return {
        str(key): str(value)
        for key, value in values.items()
        if key and value is not None and _is_project_dotenv_sdk_env_key(str(key))
    }


def process_sdk_env(process_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Return process env values suitable for ``ClaudeAgentOptions.env``.

    Cloud Run injects Secret Manager values as regular environment variables,
    not as a ``backend/.env`` file.  These values still need to be copied into
    ``ClaudeAgentOptions.env`` because setting that field makes the SDK
    subprocess use the explicit map instead of inheriting the whole parent env.
    """

    source = os.environ if process_env is None else process_env
    return {
        str(key): str(value)
        for key, value in source.items()
        if key and value is not None and _is_project_dotenv_sdk_env_key(str(key))
    }


def merge_project_dotenv_env(
    existing_env: Optional[Mapping[str, str]] = None,
    env_file: Optional[Path | str] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Merge backend ``.env``, process env, and caller-provided SDK env overrides."""
    merged = project_dotenv_env(env_file)
    merged.update(process_sdk_env(process_env))
    if existing_env:
        merged.update(
            {
                str(key): str(value)
                for key, value in existing_env.items()
                if value is not None
            }
        )
    for key in _REMOVED_PROJECT_DOTENV_SDK_ENV_NAMES:
        merged.pop(key, None)
    return merged


def apply_project_dotenv_to_options(
    options: Any,
    env_file: Optional[Path | str] = None,
) -> Any:
    """Ensure a ClaudeAgentOptions-like object carries project/runtime SDK vars."""
    existing_env = getattr(options, "env", None) or {}
    options.env = merge_project_dotenv_env(existing_env, env_file)
    return options


def apply_project_setting_sources_to_options(options: Any) -> Any:
    """Force Claude Code to load settings from the project source only.

    The TypeScript SDK exposes this as ``settingSources: ["project"]``.
    The Python SDK version used by this repo has no typed field yet, but its
    ``extra_args`` map is passed through to the Claude CLI.  The equivalent CLI
    flag is ``--setting-sources project``.
    """
    existing_extra_args = getattr(options, "extra_args", None)
    if existing_extra_args is None:
        existing_extra_args = {}
    if isinstance(existing_extra_args, dict):
        options.extra_args = existing_extra_args
    else:
        options.extra_args = dict(existing_extra_args)
    options.extra_args[_CLAUDE_SETTING_SOURCES_ARG] = _CLAUDE_PROJECT_SETTING_SOURCE
    return options


def apply_project_sdk_runtime_options(
    options: Any,
    env_file: Optional[Path | str] = None,
) -> Any:
    """Apply all project-level Claude SDK runtime defaults."""
    apply_project_dotenv_to_options(options, env_file)
    apply_project_setting_sources_to_options(options)
    return options


def apply_plan_mode_env_to_options(
    options: Any,
    cwd: Optional[str | Path] = None,
) -> Any:
    """Point the Claude Code config home at the per-thread workspace.

    Sets ``CLAUDE_CONFIG_DIR={cwd}/.claude-home`` so Plan Mode plan files
    land under ``{workspace}/.claude-home/plans/`` (claude-plan §5.1).

    Priority: lowest in the SDK env chain — call *after*
    ``apply_project_sdk_runtime_options`` and *before*
    ``apply_user_sdk_env_to_options``.  An explicitly provided
    ``CLAUDE_CONFIG_DIR`` already present in ``options.env`` is preserved.
    No-op when *cwd* is falsy (Workspace Mode disabled).
    """
    if not cwd:
        return options
    existing_env = getattr(options, "env", None) or {}
    if not isinstance(existing_env, dict):
        existing_env = dict(existing_env)
    if existing_env.get(_CLAUDE_CONFIG_DIR_ENV_NAME):
        options.env = existing_env
        return options
    options.env = {
        **existing_env,
        _CLAUDE_CONFIG_DIR_ENV_NAME: str(
            Path(str(cwd)) / _PLAN_MODE_CONFIG_HOME_DIRNAME
        ),
    }
    return options


def apply_task_v2_env_to_options(options: Any) -> Any:
    """Pin the v2 file-task list location for every run (claude-todo §5.1).

    Always injects ``CLAUDE_CODE_TASK_LIST_ID=main`` (lowest priority) so v2
    task JSON lands under ``{CLAUDE_CONFIG_DIR}/tasks/main/`` — i.e.
    ``{workspace}/.claude-home/tasks/main/`` once
    ``apply_plan_mode_env_to_options`` has redirected the config home.
    Fixing taskListId prevents the CLI's sessionId/teamName fallback from
    scattering one thread's tasks across per-session subdirectories that
    ``workspace.get_tasks_dir()`` never finds.

    Why unconditional: the claude-agent-sdk 0.2.128 bundled CLI enables task
    tools **by default** (``CLAUDE_CODE_ENABLE_TASKS !== "0"``), so without
    this injection a run with the legacy ``INK_AGENT_TASK_V2_ENABLED`` gate
    off would still execute TaskCreate/TaskUpdate but write them to a
    per-session list dir — the panel then shows nothing (2026-07-26
    production bug).  ``CLAUDE_CODE_ENABLE_TASKS=1`` is additionally injected
    when the legacy gate is truthy (belt-and-braces with the CLI default;
    preserves an explicit opt-out path via the CLI's own
    ``CLAUDE_CODE_ENABLE_TASKS=0``).

    Priority: lowest in the SDK env chain — call *after*
    ``apply_plan_mode_env_to_options`` and *before*
    ``apply_user_sdk_env_to_options``.  Explicit values already present in
    ``options.env`` are preserved.
    """

    existing_env = getattr(options, "env", None) or {}
    if not isinstance(existing_env, dict):
        existing_env = dict(existing_env)
    merged = dict(existing_env)
    merged.setdefault(
        _CLAUDE_CODE_TASK_LIST_ID_ENV_NAME, CLAUDE_CODE_TASK_LIST_ID_VALUE
    )
    if task_v2_enabled():
        merged.setdefault(_CLAUDE_CODE_ENABLE_TASKS_ENV_NAME, "1")
    options.env = merged
    return options


# CLI binary resolution (2026-07-26, Docker apply-seccomp fix).  The
# claude-agent-sdk transport prefers its bundled CLI over any system install
# (``_find_cli``: bundled first).  Production Docker patches the npm CLI's
# vendor apply-seccomp into a passthrough to survive nested userns, so the
# patched binary must win over the bundled one.
_CLAUDE_CODE_CLI_PATH_ENV_NAME = "CLAUDE_CODE_CLI_PATH"


def apply_cli_path_to_options(options: Any) -> Any:
    """Pin ``options.cli_path`` to the system/npm CLI when available.

    Resolution order (first hit wins):

    1. ``CLAUDE_CODE_CLI_PATH`` env var, when set and the path exists.
       A set-but-missing path logs a warning and falls through — a stale
       override must never shadow a working CLI.
    2. ``shutil.which("claude")`` — the system/npm install.  Production
       Docker ships the npm CLI with the vendor apply-seccomp passthrough
       patch (nested-userns ``/proc/self/setgroups`` workaround); pinning it
       prevents the SDK's bundled CLI from silently shadowing the patched
       binary (2026-07-26 recurrence).  Local dev likewise stays on the
       developer's own npm claude.
    3. Leave ``cli_path`` unset — documented escape hatch: the SDK then
       falls back to its bundled CLI (usable when no system claude exists).

    An explicitly pre-set ``options.cli_path`` always wins over this helper.
    """

    if getattr(options, "cli_path", None):
        return options
    override = os.getenv(_CLAUDE_CODE_CLI_PATH_ENV_NAME, "").strip()
    if override:
        if os.path.isfile(override):
            options.cli_path = override
            return options
        logger.warning(
            "%s=%r is set but the file does not exist; falling back to "
            "system/bundled CLI resolution.",
            _CLAUDE_CODE_CLI_PATH_ENV_NAME,
            override,
        )
    system_cli = shutil.which("claude")
    if system_cli:
        options.cli_path = system_cli
    return options


def apply_user_sdk_env_to_options(
    options: Any,
    user_env: Optional[Mapping[str, str]] = None,
) -> Any:
    """Overlay user-stored SDK env vars onto options, filtered to the allowlist.

    Must be called *after* apply_project_sdk_runtime_options so that
    user values take precedence over backend/.env defaults.
    """
    if not user_env:
        return options
    existing_env = getattr(options, "env", None) or {}
    if not isinstance(existing_env, dict):
        existing_env = dict(existing_env)
    # Only forward keys on the SDK allowlist to the subprocess.
    filtered = {
        str(k): str(v)
        for k, v in user_env.items()
        if k and v is not None and _is_project_dotenv_sdk_env_key(str(k))
    }
    # Merge: filtered user env overlays existing (which already has backend/.env).
    merged = {**existing_env, **filtered}
    # Remove any deprecated keys.
    for key in _REMOVED_PROJECT_DOTENV_SDK_ENV_NAMES:
        merged.pop(key, None)
    options.env = merged
    return options
