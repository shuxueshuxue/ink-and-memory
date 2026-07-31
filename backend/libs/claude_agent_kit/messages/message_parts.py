# [Input] None — standalone utility.
# [Output] Provide extract_text_from_parts to context_builder and service layers.
# [Pos] utility node in libs/claude_agent_kit/messages
# [Sync] 2026-05-26: Python port of TypeScript message-parts.ts extractTextFromParts.
#                    Handles text, file, source-url, and workspace-file parts.

"""Extract text from AI-SDK UIMessage parts.

Python translation of TypeScript:
  app/lib/message-parts.ts  (extractTextFromParts)

Converts a Vercel AI SDK ``UIMessage.parts`` list into a single string
suitable for passing to the Claude agent.  Text parts are collected first;
metadata blocks for file/source-url/workspace-file parts follow, so that
attachment-only messages are still actionable.
"""
from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Internal helpers (mirrors private helpers in message-parts.ts)
# ---------------------------------------------------------------------------


def _read_string(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _read_non_negative_number(value: object) -> Optional[float]:
    if not isinstance(value, (int, float)):
        return None
    if value != value or value < 0:  # NaN or negative
        return None
    return float(value)


def _format_size(bytes_: float) -> str:
    if bytes_ < 1024:
        return f"{int(bytes_)} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def _infer_file_name_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        name = parts[-1] if parts else None
        return unquote(name) if name else None
    except Exception:
        without_query = url.split("?")[0]
        parts = without_query.split("/")
        name = parts[-1] if parts else None
        if not name:
            return None
        try:
            from urllib.parse import unquote
            return unquote(name)
        except Exception:
            return name


def _format_file_part(part: dict) -> str:
    url = _read_string(part.get("url"))
    file_name = (
        _read_string(part.get("filename"))
        or _infer_file_name_from_url(url)
        or "Unnamed file"
    )
    media_type = _read_string(part.get("mediaType"))
    size = _read_non_negative_number(part.get("size"))

    lines = [f"Attached file: {file_name}"]
    if media_type:
        lines.append(f"MIME type: {media_type}")
    if size is not None:
        lines.append(f"Size: {_format_size(size)}")
    if url:
        lines.append(f"URL: {url}")
    return "\n".join(lines)


def _format_source_url_part(part: dict) -> Optional[str]:
    url = _read_string(part.get("url"))
    if not url:
        return None
    title = _read_string(part.get("title"))
    media_type = _read_string(part.get("mediaType"))
    header = f"Attached source: {title}" if title else "Attached source URL"
    lines = [header, f"URL: {url}"]
    if media_type:
        lines.append(f"MIME type: {media_type}")
    return "\n".join(lines)


def _format_workspace_file_part(part: dict) -> str:
    file_name = _read_string(part.get("fileName")) or "Unnamed workspace file"
    workspace_path = _read_string(part.get("workspacePath"))
    mime_type = _read_string(part.get("mimeType"))
    saved_at = _read_string(part.get("savedAt"))
    hash_ = _read_string(part.get("hash"))
    size = _read_non_negative_number(part.get("size"))

    lines = [f"Workspace file: {file_name}"]
    if workspace_path:
        lines.append(f"Path: {workspace_path}")
    if mime_type:
        lines.append(f"MIME type: {mime_type}")
    if size is not None:
        lines.append(f"Size: {_format_size(size)}")
    if saved_at:
        lines.append(f"Saved at: {saved_at}")
    if hash_:
        lines.append(f"Hash (sha256): {hash_}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text_from_parts(
    parts: Optional[list],
    separator: str = "\n\n",
) -> str:
    """Extract text content from AI-SDK UIMessage parts for agent input.

    Includes metadata from file-related parts so attachment-only messages are
    still actionable.

    ``text`` parts are collected first; ``file``, ``source-url``, and
    ``workspace-file`` parts are rendered as metadata blocks that follow.

    Mirrors TypeScript ``extractTextFromParts`` in app/lib/message-parts.ts.
    """
    if not parts:
        return ""

    text_contents: list[str] = []
    attachment_contents: list[str] = []

    for part in parts:
        if not part or not isinstance(part, dict):
            continue

        part_type = part.get("type")

        if part_type == "text":
            text = _read_string(part.get("text"))
            if text:
                text_contents.append(text)
            continue

        if part_type == "file":
            attachment_contents.append(_format_file_part(part))
            continue

        if part_type == "source-url":
            source_content = _format_source_url_part(part)
            if source_content:
                attachment_contents.append(source_content)
            continue

        if part_type == "workspace-file":
            attachment_contents.append(_format_workspace_file_part(part))

    combined = [*text_contents, *attachment_contents]
    return separator.join(combined).strip()
