# [Input] Consume EditorState dicts passed through AgentRunOptions.editor_state.
# [Output] Provide EDITOR_RESOURCES, is_editor_index_path, resolve_editor_resource,
#          get_editor_resource_data to the PreToolUse hook in agent_runner.py.
# [Pos] virtual-index-adapter node in libs/claude_agent_kit/server
# [Sync] 2026-05-28: initial implementation — .editor/ virtual index helper functions.

"""EditorState virtual index adapter helpers.

Implements the data-extraction side of the ``.editor/`` virtual index described
in ``docs/design/claude-agent/edit-point/workspace-adapter.md``.

The PreToolUse hook in ``agent_runner.py`` calls these helpers to:
1. Detect whether a ``Read`` tool path targets the ``.editor/`` virtual directory.
2. Resolve the path to a named resource key.
3. Extract the matching slice of ``AgentRunOptions.editor_state`` to write into
   a temporary file that gets redirected to the agent.
"""
from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------------------
# Resource registry
# ---------------------------------------------------------------------------

# Maps virtual filename stem → EditorState extraction key.
# Special keys beginning with "__" are handled by get_editor_resource_data.
EDITOR_RESOURCES: dict[str, str] = {
    "cells": "cells",
    "commentors": "commentors",
    "tasks": "tasks",
    "session": "__session__",
    "full_state": "__full__",
}

# Normalised prefix used to detect virtual index paths.
_EDITOR_PREFIX = ".editor/"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def is_editor_index_path(path: str) -> bool:
    """Return True if *path* targets a virtual ``.editor/`` resource.

    Accepts absolute paths (e.g. ``/workspace/abc/.editor/cells.json``) and
    workspace-relative paths (e.g. ``.editor/cells.json``).  Only paths whose
    basename (without extension) is a key in :data:`EDITOR_RESOURCES` match.
    """
    if not path:
        return False
    # Normalise path separators and strip leading slashes for the relative check.
    normalised = path.replace("\\", "/")
    # Find the .editor/ segment anywhere in the path.
    idx = normalised.find(_EDITOR_PREFIX)
    if idx == -1:
        return False
    remainder = normalised[idx + len(_EDITOR_PREFIX):]
    # Strip any trailing sub-path — only top-level .editor/ files are virtual.
    if "/" in remainder:
        return False
    # Strip extension and check against registry.
    stem = remainder.split(".")[0]
    return stem in EDITOR_RESOURCES


def resolve_editor_resource(path: str) -> Optional[str]:
    """Return the resource key for *path*, or ``None`` if not a virtual path.

    Example::

        >>> resolve_editor_resource(".editor/cells.json")
        'cells'
        >>> resolve_editor_resource("/workspace/abc/.editor/session.json")
        'session'
    """
    if not path:
        return None
    normalised = path.replace("\\", "/")
    idx = normalised.find(_EDITOR_PREFIX)
    if idx == -1:
        return None
    remainder = normalised[idx + len(_EDITOR_PREFIX):]
    if "/" in remainder:
        return None
    stem = remainder.split(".")[0]
    return stem if stem in EDITOR_RESOURCES else None


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


def get_editor_resource_data(
    path: str,
    editor_state: dict[str, Any],
) -> Any:
    """Extract the data slice for *path* from *editor_state*.

    :param path:         A ``.editor/`` virtual path (e.g. ``.editor/cells.json``).
    :param editor_state: The full ``editor_state`` dict from ``AgentRunOptions``.
    :returns:            The extracted data — a dict or list.
                         Returns ``{}`` when *path* does not resolve to a known resource.

    Special resource mappings:

    * ``"session"``    → ``{id, selectedState, createdAt}`` from the top-level state.
    * ``"full_state"`` → the entire *editor_state* dict unchanged.
    * Any other mapped key → ``{key: editor_state[key]}`` (defaults to empty list).
    """
    resource = resolve_editor_resource(path)
    if resource is None:
        return {}

    mapped = EDITOR_RESOURCES.get(resource)
    if mapped is None:
        return {}

    if mapped == "__full__":
        return editor_state

    if mapped == "__session__":
        return {
            "id": editor_state.get("id"),
            "selectedState": editor_state.get("selectedState"),
            "createdAt": editor_state.get("createdAt"),
        }

    return {mapped: editor_state.get(mapped, [])}
