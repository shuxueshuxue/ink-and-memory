# [Input] None - consumes caller-provided partition memory_workspace_config.
#          Prompt template files are sourced exclusively from partition config.
# [Output] Provide init_memory_workspace to the workspace file-interface route,
#          and get_memory_context_block to claude_agent/context_builder.py.
# [Pos] memory-workspace node in libs/claude_agent_kit/server
# [Sync] 2026-06-05: initial implementation - Memory Workspace initialization,
#                    per-voice config application, and memory context injection.
# [Sync] 2026-06-06: all five core prompt files now come from the partition config
#                    table; removed project .claude/memory/ fallback and long-term
#                    summary starter creation. Memory workspace is procedural-only.

"""Memory Workspace manager for Claude Agent session directories.

Memory workspace type: **procedural**.  The directory stores structured
operating rules, prompt resources, and state files that teach the agent how to
perform memory work.  It is not a short-term chat cache and not a long-term
summary bucket.

Each session workspace may gain a ``memory/`` subdirectory that holds five core
prompt/rule files.  All five are sourced from the caller-provided partition
configuration, normally ``voices.memory_workspace_config``.  Files absent from
the config are not written, and there is no fallback to project
``.claude/memory/`` templates.

The preferred config shape is::

    {
        "workspace_type": "procedural",
        "prompt_files": {
            "WORKFLOW.md": "...",
            "MEMORY_QUERY_PROMPT.md": "...",
            "MEMORY_Distiller_PROMPT.md": "...",
            "MEMORY_ANSWER_PROMPT.md": "...",
            "DEFAULT_UPDATE_MEMORY_PROMPT.md": "..."
        }
    }

Legacy ``*_prompt_override`` keys are still accepted for one migration window.

Usage::

    from libs.claude_agent_kit.server.memory_workspace import (
        init_memory_workspace,
        get_memory_context_block,
    )

    workspace = get_or_create_workspace(session_id)
    memory_config = database.get_voice_memory_config_by_thread(thread_id)
    init_memory_workspace(workspace, memory_config)  # /api/workspace/memory-init
    block = get_memory_context_block(workspace)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Names of the five core prompt/rule files in the memory/ directory.
MEMORY_PROMPT_FILES: tuple[str, ...] = (
    "WORKFLOW.md",
    "MEMORY_QUERY_PROMPT.md",
    "MEMORY_Distiller_PROMPT.md",
    "MEMORY_ANSWER_PROMPT.md",
    "DEFAULT_UPDATE_MEMORY_PROMPT.md",
)

# Canonical memory_workspace_config JSON key -> file name in memory/.
_CONFIG_KEY_TO_FILE: dict[str, str] = {
    "workflow_prompt": "WORKFLOW.md",
    "query_prompt": "MEMORY_QUERY_PROMPT.md",
    "distiller_prompt": "MEMORY_Distiller_PROMPT.md",
    "answer_prompt": "MEMORY_ANSWER_PROMPT.md",
    "update_prompt": "DEFAULT_UPDATE_MEMORY_PROMPT.md",
}

# Legacy config key aliases kept so rows written by the 2026-06-05 prototype
# migrate without requiring immediate DB rewrites.
_LEGACY_CONFIG_KEY_TO_FILE: dict[str, str] = {
    "workflow_prompt_override": "WORKFLOW.md",
    "query_prompt_override": "MEMORY_QUERY_PROMPT.md",
    "distiller_prompt_override": "MEMORY_Distiller_PROMPT.md",
    "answer_prompt_override": "MEMORY_ANSWER_PROMPT.md",
    "update_prompt_override": "DEFAULT_UPDATE_MEMORY_PROMPT.md",
}

# Reverse mapping: file name -> canonical config key.
_FILE_TO_CONFIG_KEY: dict[str, str] = {v: k for k, v in _CONFIG_KEY_TO_FILE.items()}

# Names of the runtime-generated procedural memory JSON files.
PROCEDURAL_MEMORY_FILES: tuple[str, ...] = (
    "user_preferences.json",
    "important_events.json",
    "timeline.json",
)

# Starter content for runtime-generated procedural files (first-init only).
_PROCEDURAL_DEFAULTS: dict[str, Any] = {
    "user_preferences.json": {
        "writing_style": None,
        "preferred_language": None,
        "active_hours": None,
        "response_length": None,
        "topics_of_interest": [],
        "avoid_topics": [],
        "updated_at": None,
    },
    "important_events.json": [],
    "timeline.json": [],
}

def _resolve_safe_memory_dir(workspace: Path) -> Optional[Path]:
    """Resolve and verify the ``memory/`` path is safely inside the workspace root.

    Returns the resolved absolute ``memory/`` Path, or ``None`` when:
    - the workspace cannot be resolved, or
    - the resolved workspace lies outside the configured workspace root.

    This follows the same guard pattern as ``_init_editor_index`` in workspace.py
    to prevent path-traversal attacks when *workspace* contains a user-controlled
    session_id component.
    """
    try:
        from .workspace import get_workspace_root  # local import avoids circular
        workspace_root_abs = get_workspace_root().resolve()
        workspace_abs = workspace.resolve()
        if not workspace_abs.is_relative_to(workspace_root_abs):
            logger.warning(
                "_resolve_safe_memory_dir: workspace %r is outside workspace root %r; aborting.",
                workspace_abs,
                workspace_root_abs,
            )
            return None
        # "memory" is a fixed subdirectory name; no user input involved.
        return workspace_abs / "memory"
    except Exception:  # noqa: BLE001
        logger.warning(
            "_resolve_safe_memory_dir: could not resolve workspace path; aborting.",
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_memory_workspace(workspace: Path, memory_config: Optional[dict[str, Any]] = None) -> Path:
    """Create (or repair) the ``memory/`` subdirectory in *workspace*.

    Memory workspace type: **procedural** - stores structured behavioural
    rules, prompt templates, and state files.

    Steps:
    1. Create ``memory/`` (idempotent).
    2. Sync all prompt/rule files from *memory_config* (the partition's
       ``memory_workspace_config`` from the ``voices`` DB table). Files absent
       from the config are skipped; there is no filesystem fallback.
    3. Create ``memory/procedural/`` subdirectory (idempotent).
    4. Write starter procedural JSON files (first-init only - existing files
       are preserved to avoid losing runtime-accumulated memories).

    Args:
        workspace:     Session workspace root directory.
        memory_config: Partition (voice) ``memory_workspace_config`` dict.
                       Prompt files are written only when present in this
                       config; missing keys are skipped.

    Returns the absolute ``memory/`` directory path.
    Raises ``ValueError`` when *workspace* resolves outside the configured workspace root.
    """
    memory_dir = _resolve_safe_memory_dir(workspace)
    if memory_dir is None:
        raise ValueError(
            f"init_memory_workspace: workspace {workspace!r} is outside the configured "
            "workspace root or could not be resolved."
        )
    memory_dir.mkdir(exist_ok=True)

    # Sync prompt/rule files from partition config only.
    _sync_memory_templates(memory_dir, memory_config)

    # Ensure procedural/ subdirectory exists.
    procedural_dir = memory_dir / "procedural"
    procedural_dir.mkdir(exist_ok=True)

    # Write starter procedural JSON files (first-init only).
    for filename, default_content in _PROCEDURAL_DEFAULTS.items():
        dest = procedural_dir / filename
        if dest.exists():
            continue
        try:
            dest.write_text(
                json.dumps(default_content, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug("Created memory/procedural/%s", filename)
        except OSError:
            logger.warning(
                "Failed to create memory/procedural/%s; skipping.",
                filename,
                exc_info=True,
            )

    logger.debug("Memory workspace initialised: %s", memory_dir)
    return memory_dir


def apply_memory_config(
    workspace: Path,
    memory_config: Optional[dict[str, Any]],
) -> None:
    """Apply per-voice ``memory_workspace_config`` overrides to *workspace*.

    When *memory_config* is ``None`` or empty, this function is a no-op.

    Preferred config: ``{"prompt_files": {"WORKFLOW.md": "...", ...}}``.
    Canonical ``*_prompt`` keys and legacy ``*_prompt_override`` aliases are
    also accepted.
    """
    if not memory_config:
        return

    memory_dir = _resolve_safe_memory_dir(workspace)
    if memory_dir is None or not memory_dir.is_dir():
        logger.warning(
            "apply_memory_config: memory/ dir not reachable at %s; skipping.", workspace
        )
        return

    for filename, override_content in get_memory_prompt_files(memory_config).items():
        # filename is from the fixed MEMORY_PROMPT_FILES whitelist.
        dest = memory_dir / filename
        try:
            dest.write_text(override_content.strip() + "\n", encoding="utf-8")
            logger.debug(
                "Applied memory_workspace_config prompt file: %s", filename
            )
        except OSError:
            logger.warning(
                "Failed to write memory config override %s; skipping.",
                filename,
                exc_info=True,
            )


def get_memory_context_block(workspace: Path) -> str:
    """Return a ``<memory_context>`` text block for injection into user messages.

    The block tells the agent about the memory workspace layout (type:
    **procedural**) and the available prompt/state files so the agent can
    decide whether to read them.

    Returns an empty string when the ``memory/`` directory does not exist or
    when *workspace* resolves outside the configured workspace root.
    """
    memory_dir = _resolve_safe_memory_dir(workspace)
    if memory_dir is None or not memory_dir.is_dir():
        return ""

    procedural_dir = memory_dir / "procedural"
    procedural_files: list[str] = []
    if procedural_dir.is_dir():
        procedural_files = sorted(
            f.name
            for f in procedural_dir.iterdir()
            if f.is_file() and f.suffix == ".json"
        )

    lines: list[str] = [
        "<memory_context>",
        f"Memory workspace (type: procedural only): {memory_dir}",
        "This is a procedural memory workspace, not a short-term chat cache or long-term summary store.",
        "",
        "Memory prompt files (read for instructions):",
        *[
            f"  memory/{filename}  - {'available' if (memory_dir / filename).is_file() else 'missing'}"
            for filename in MEMORY_PROMPT_FILES
        ],
        "",
    ]

    if procedural_files:
        files_list = ", ".join(procedural_files)
        lines.append(f"Procedural state files: {files_list}")
        lines.append("  Located in memory/procedural/  (read only when relevant)")
    else:
        lines.append("Procedural state files: none yet")

    lines.append("</memory_context>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def get_memory_prompt_files(memory_config: Optional[dict[str, Any]]) -> dict[str, str]:
    """Return whitelisted prompt file contents from a partition config.

    Preferred source:
      ``memory_config["prompt_files"][<filename>]``

    Migration-compatible sources:
      canonical ``*_prompt`` keys and legacy ``*_prompt_override`` keys.

    Values are returned as ``filename -> content`` for filenames present in
    ``MEMORY_PROMPT_FILES`` only.  This keeps partition configuration flexible
    without allowing arbitrary workspace paths.
    """
    if not memory_config or not isinstance(memory_config, dict):
        return {}

    prompt_files: dict[str, str] = {}
    configured_files = memory_config.get("prompt_files")
    if isinstance(configured_files, dict):
        for filename in MEMORY_PROMPT_FILES:
            content = configured_files.get(filename)
            if isinstance(content, str) and content.strip():
                prompt_files[filename] = content.strip()

    for config_key, filename in {
        **_CONFIG_KEY_TO_FILE,
        **_LEGACY_CONFIG_KEY_TO_FILE,
    }.items():
        if filename in prompt_files:
            continue
        content = memory_config.get(config_key)
        if isinstance(content, str) and content.strip():
            prompt_files[filename] = content.strip()

    return prompt_files


def _sync_memory_templates(
    memory_dir: Path,
    memory_config: Optional[dict[str, Any]] = None,
) -> None:
    """Write prompt/rule files into *memory_dir* from the partition config.

    Template source rules:
    - All five core files are written from *memory_config* only.
    - Missing config values are skipped.
    - There is no filesystem fallback to project ``.claude/memory/``.

    Runtime state files (``procedural/``) are never touched by this function.
    """
    for filename, content in get_memory_prompt_files(memory_config).items():
        dest = memory_dir / filename
        try:
            dest.write_text(content.strip() + "\n", encoding="utf-8")
            logger.debug(
                "_sync_memory_templates: wrote %s from partition config", filename
            )
        except OSError:
            logger.warning(
                "_sync_memory_templates: failed to write %s from partition config; skipping.",
                filename,
                exc_info=True,
            )


__all__ = [
    "init_memory_workspace",
    "apply_memory_config",
    "get_memory_context_block",
    "get_memory_prompt_files",
    "MEMORY_PROMPT_FILES",
    "PROCEDURAL_MEMORY_FILES",
]
