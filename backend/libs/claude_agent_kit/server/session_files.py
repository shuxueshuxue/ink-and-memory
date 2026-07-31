# [Input] None — standalone session JSONL file reader.
# [Output] Provide locate_session_file, read_session_messages,
#          parse_session_messages_from_jsonl to simple_cas_client.
# [Pos] utility node in libs/claude_agent_kit/server
# [Sync] 2026-05-01: initial Python port from server/utils/session-files.ts

"""Session file utilities.

Python translation of TypeScript:
  server/utils/session-files.ts

Session files are JSONL files stored at:
  ~/.claude/projects/<project-dir>/<session-id>.jsonl
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

SESSION_FILE_EXTENSION = ".jsonl"


def get_projects_root() -> Optional[str]:
    """Return the Claude projects root directory (``~/.claude/projects``).

    Maps to TypeScript ``getProjectsRoot``.
    """
    home_dir = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if not home_dir:
        return None
    return str(Path(home_dir) / ".claude" / "projects")


def normalize_session_id(value: str) -> str:
    """Strip the ``.jsonl`` extension from a session ID if present.

    Maps to TypeScript ``normalizeSessionId``.
    """
    if value.lower().endswith(SESSION_FILE_EXTENSION):
        return value[: -len(SESSION_FILE_EXTENSION)]
    return value


async def locate_session_file(
    projects_root: str,
    session_id: str,
) -> Optional[str]:
    """Search for the JSONL session file across all project sub-directories.

    Maps to TypeScript ``locateSessionFile``.
    Returns the absolute path to the file, or ``None`` if not found.
    """
    candidate_dirs = await _collect_candidate_project_dirs(projects_root)
    for project_dir in candidate_dirs:
        session_path = str(Path(project_dir) / f"{session_id}{SESSION_FILE_EXTENSION}")
        if os.path.isfile(session_path):
            return session_path
    return None


async def read_session_messages(file_path: str) -> list[Any]:
    """Read and parse session messages from a JSONL file on disk.

    Maps to TypeScript ``readSessionMessages``.
    """
    try:
        with open(file_path, encoding="utf-8") as fh:
            file_content = fh.read()
    except FileNotFoundError:
        return []

    if not file_content:
        return []

    return parse_session_messages_from_jsonl(file_content)


def parse_session_messages_from_jsonl(file_content: str) -> list[Any]:
    """Parse session messages from raw JSONL text.

    Maps to TypeScript ``parseSessionMessagesFromJsonl``.
    """
    if not file_content:
        return []

    messages: list[Any] = []
    for raw_line in file_content.splitlines():
        trimmed = raw_line.strip()
        if not trimmed:
            continue
        try:
            parsed = json.loads(trimmed)
            message = _normalize_session_log_entry(parsed)
            if message is not None:
                messages.append(message)
        except json.JSONDecodeError:
            continue

    return messages


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _collect_candidate_project_dirs(projects_root: str) -> list[str]:
    """Enumerate sub-directories inside ``projects_root`` as candidates.

    Maps to TypeScript ``collectCandidateProjectDirs``.
    """
    root_path = Path(projects_root)
    if not root_path.is_dir():
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    try:
        for entry in root_path.iterdir():
            if entry.is_dir():
                full_path = str(entry)
                if full_path not in seen:
                    candidates.append(full_path)
                    seen.add(full_path)
    except PermissionError:
        return []

    return candidates


def _normalize_session_log_entry(entry: Any) -> Optional[dict[str, Any]]:
    """Normalize a raw JSONL record into a canonical message dict.

    Maps to TypeScript ``normalizeSessionLogEntry``.
    Returns ``None`` for records that should be skipped (summaries, malformed).
    """
    if not entry or not isinstance(entry, dict):
        return None

    raw_type = entry.get("type")
    if not isinstance(raw_type, str):
        return None

    if raw_type.lower() == "summary":
        return None

    normalized: dict[str, Any] = {}
    for key, value in entry.items():
        # Rename camelCase key kept by some older session files
        if key == "sessionId":
            normalized["session_id"] = value
        else:
            normalized[key] = value

    if "message" not in normalized:
        return None

    message_value = normalized["message"]
    if not isinstance(message_value, (str, dict)):
        return None

    if _is_summary_message(message_value):
        return None

    normalized["type"] = raw_type
    return normalized


def _is_summary_message(value: Any) -> bool:
    """Return ``True`` if *value* looks like a summary message.

    Maps to TypeScript ``isSummaryMessage``.
    """
    if not value or not isinstance(value, dict):
        return False
    raw_type = value.get("type")
    return isinstance(raw_type, str) and raw_type.lower() == "summary"
