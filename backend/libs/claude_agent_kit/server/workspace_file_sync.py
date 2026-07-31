# [Input] Consume workspace_path from libs/claude_agent_kit/server/workspace.py.
# [Output] Provide sync_skills_symlinks, _clean_stale_skill_symlinks,
#          WorkspaceFileSyncError, save_buffer_to_workspace_files,
#          sync_attachments_to_workspace_files, inject_attachment_message_parts,
#          normalize_workspace_file_sync_error to workspace.py and the API layer.
# [Pos] symlink-sync node in libs/claude_agent_kit/server
# [Sync] 2026-05-06: initial implementation — WSK-02 skills symlink sync
# [Sync] 2026-05-25: add WorkspaceFileSyncError, save_buffer_to_workspace_files,
#         normalize_workspace_file_sync_error ported from claude-agent-next-kit workspace-file-sync.ts.
# [Sync] 2026-05-25: add sync_attachments_to_workspace_files, inject_attachment_message_parts
#         ported from claude-agent-next-kit chat-attachment-processing.ts (WeKnora excluded).
# [Sync] 2026-06-16: import real files/directories created directly under
#         .claude/skills back into workspace/skills before rebuilding symlinks.

"""Skills symlink synchronisation for Claude Agent workspaces.

Maintains a 1-to-1 mapping between ``{workspace}/skills/*`` and
``{workspace}/.claude/skills/*`` using filesystem symbolic links so that the
Claude Agent always discovers skills at the canonical ``.claude/skills/``
location while the workspace file browser can show the user-facing
``skills/`` directory.

Rules
-----
- Only non-dot-prefixed entries in ``skills/`` are exposed.
- Real non-dot-prefixed files/directories created directly in
  ``.claude/skills/`` are first moved into ``skills/`` so direct Claude Code
  writes become visible in the workspace.
- If a symlink in ``.claude/skills/`` already points to the correct source,
  it is left unchanged (no unnecessary re-creation).
- If the target slot is occupied by a symlink pointing elsewhere, or by a
  plain file/directory, the slot is cleared and the correct symlink is created.
- After syncing, any symlink in ``.claude/skills/`` whose source entry no
  longer exists in ``skills/`` is removed (stale-link cleanup).
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


def sync_skills_symlinks(workspace_path: Path) -> None:
    """Synchronise workspace skills with Claude's canonical skills directory.

    First imports real files/directories written directly under
    ``.claude/skills/`` into ``skills/``. Then creates, updates, and cleans up
    symbolic links so that every non-hidden entry in ``skills/`` has a
    matching symlink in ``.claude/skills/``.

    Raises ``OSError`` if the filesystem does not support symlinks (the error
    propagates so callers can log or surface it — no silent failure).
    """
    skills_src = workspace_path / "skills"
    skills_dst = workspace_path / ".claude" / "skills"

    if not skills_src.is_dir():
        logger.debug(
            "sync_skills_symlinks: skills source dir does not exist: %s", skills_src
        )
        return

    skills_dst.mkdir(parents=True, exist_ok=True)

    _import_real_claude_skill_entries(skills_dst, skills_src)

    # Build set of current source entries (excluding dot-prefixed names).
    src_entries = _collect_skill_source_entries(skills_src)

    # -----------------------------------------------------------------------
    # Step 1: create / update symlinks for current source entries.
    # -----------------------------------------------------------------------
    for name, src in src_entries.items():
        dst_link = skills_dst / name
        _ensure_symlink(src, dst_link)

    # -----------------------------------------------------------------------
    # Step 2: remove stale symlinks (source entry was deleted or renamed).
    # -----------------------------------------------------------------------
    _clean_stale_skill_symlinks(skills_dst, src_entries)


def _collect_skill_source_entries(skills_src: Path) -> dict[str, Path]:
    """Return visible workspace skill entries keyed by basename."""
    src_entries: dict[str, Path] = {}
    for entry in skills_src.iterdir():
        if not entry.name.startswith("."):
            src_entries[entry.name] = entry
    return src_entries


def _import_real_claude_skill_entries(
    skills_link_dir: Path,
    skills_src_dir: Path,
) -> None:
    """Move real ``.claude/skills`` entries into ``workspace/skills``.

    Claude Code may create or replace a skill directly in its canonical
    discovery directory. Those entries must become workspace-owned sources
    before symlinks are rebuilt, otherwise the next sync would hide or remove
    the direct write.
    """
    if not skills_link_dir.is_dir():
        return

    skills_src_dir.mkdir(parents=True, exist_ok=True)

    for entry in sorted(
        list(skills_link_dir.iterdir()),
        key=lambda item: item.name.lower(),
    ):
        if entry.name.startswith(".") or entry.is_symlink():
            continue
        if not entry.is_file() and not entry.is_dir():
            logger.warning("Skipping unsupported .claude/skills entry: %s", entry)
            continue

        dst_entry = skills_src_dir / entry.name
        if dst_entry.exists() or dst_entry.is_symlink():
            _remove_path(dst_entry)
            logger.debug(
                "Replaced workspace skill source from direct .claude/skills write: %s",
                dst_entry,
            )

        shutil.move(str(entry), str(dst_entry))
        logger.debug(
            "Imported direct .claude/skills entry: %s → %s",
            entry,
            dst_entry,
        )


def _remove_path(path: Path) -> None:
    """Remove a file, symlink, or directory without following symlinks."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _ensure_symlink(src: Path, dst_link: Path) -> None:
    """Ensure *dst_link* is a symlink pointing to *src*.

    If *dst_link* already points to *src*, it is left unchanged.
    If *dst_link* exists but points elsewhere, or is a plain file/directory,
    it is removed and recreated.
    """
    # Use absolute path for the symlink target.
    target = src.resolve()

    if dst_link.is_symlink():
        try:
            existing_target = Path(os.readlink(dst_link)).resolve()
        except OSError:
            existing_target = None
        if existing_target == target:
            return  # already correct — nothing to do
        # Wrong target — remove and recreate.
        dst_link.unlink()
        logger.debug("Removed mismatched symlink: %s", dst_link)
    elif dst_link.exists():
        # Plain file or directory occupying the slot — clear it.
        _remove_path(dst_link)
        logger.warning(
            "Removed non-symlink occupying .claude/skills slot: %s", dst_link
        )

    dst_link.symlink_to(target)
    logger.debug("Created symlink: %s → %s", dst_link, target)


def _clean_stale_skill_symlinks(
    skills_link_dir: Path,
    current_src_entries: dict[str, Path],
) -> None:
    """Remove symlinks in *skills_link_dir* whose source no longer exists.

    Only symbolic links are touched — real files or directories in
    ``.claude/skills/`` that were not created by this sync mechanism are
    left untouched to avoid data loss.
    """
    if not skills_link_dir.is_dir():
        return

    for entry in list(skills_link_dir.iterdir()):
        if not entry.is_symlink():
            continue  # never touch real files/directories
        if entry.name not in current_src_entries:
            entry.unlink()
            logger.debug("Removed stale symlink: %s", entry)


# ---------------------------------------------------------------------------
# Workspace file-sync: upload helpers (ported from claude-agent-next-kit
# workspace-file-sync.ts)
# ---------------------------------------------------------------------------

MAX_WORKSPACE_SYNC_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

# MIME types that are explicitly allowed for workspace file uploads.
_WORKSPACE_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/csv",
    "application/json",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-gzip",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/ogg",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/octet-stream",
})

# MIME type prefixes accepted in addition to the explicit allowlist.
_WORKSPACE_ALLOWED_MIME_PREFIXES: tuple[str, ...] = ("image/",)


class WorkspaceFileSyncErrorCode(str, Enum):
    """Machine-readable error codes for workspace file-sync failures."""

    INVALID_ATTACHMENT = "INVALID_ATTACHMENT"
    INVALID_WORKSPACE_PATH = "INVALID_WORKSPACE_PATH"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    MIME_TYPE_NOT_ALLOWED = "MIME_TYPE_NOT_ALLOWED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    WRITE_FAILED = "WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class WorkspaceFileSyncError(Exception):
    """Raised when a workspace file-sync operation fails.

    Attributes:
        code:    Machine-readable error category (``WorkspaceFileSyncErrorCode``).
        status:  Suggested HTTP status code.
        details: Optional structured diagnostic payload.
    """

    def __init__(
        self,
        code: WorkspaceFileSyncErrorCode,
        message: str,
        status: int,
        details: Optional[object] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


def _normalize_mime_type(mime_type: Optional[str]) -> str:
    return (mime_type or "application/octet-stream").strip().lower()


def _is_mime_type_allowed(mime_type: str) -> bool:
    if mime_type in _WORKSPACE_ALLOWED_MIME_TYPES:
        return True
    return any(mime_type.startswith(prefix) for prefix in _WORKSPACE_ALLOWED_MIME_PREFIXES)


def _sanitize_upload_file_name(file_name: Optional[str]) -> str:
    """Return a filesystem-safe file name, guaranteed non-empty."""
    import re
    import time
    from pathlib import Path as _Path

    fallback = f"upload-{int(time.time() * 1000)}"
    base = _Path(file_name or "").name.strip() if file_name else ""
    if not base:
        return fallback

    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
    sanitized = re.sub(r"\s+", " ", sanitized).strip().lstrip(".")
    return sanitized or fallback


def _resolve_unique_workspace_file_path(
    workspace_path: Path,
    file_name: str,
) -> str:
    """Return a unique relative path under ``files/`` that does not yet exist."""
    from pathlib import PurePosixPath

    stem = PurePosixPath(file_name).stem
    suffix = PurePosixPath(file_name).suffix
    candidate = file_name
    counter = 1

    while (workspace_path / "files" / candidate).exists():
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1

    return f"files/{candidate}"


def save_buffer_to_workspace_files(
    workspace_path: Path,
    file_name: Optional[str],
    mime_type: Optional[str],
    content: bytes,
) -> dict:
    """Save *content* to ``{workspace_path}/files/`` with deduplication.

    Validates MIME type and size before writing.  Returns a dict with
    workspace file metadata (compatible with the ``workspace-file`` message
    part schema used by claude-agent-next-kit).

    Raises :class:`WorkspaceFileSyncError` on validation or write failure.
    """
    from datetime import datetime, timezone

    normalized_mime = _normalize_mime_type(mime_type)

    if not _is_mime_type_allowed(normalized_mime):
        raise WorkspaceFileSyncError(
            WorkspaceFileSyncErrorCode.MIME_TYPE_NOT_ALLOWED,
            f"File MIME type is not allowed: {normalized_mime}",
            400,
            {"mimeType": normalized_mime},
        )

    if len(content) > MAX_WORKSPACE_SYNC_FILE_SIZE_BYTES:
        raise WorkspaceFileSyncError(
            WorkspaceFileSyncErrorCode.FILE_TOO_LARGE,
            f"File exceeds max size limit ({MAX_WORKSPACE_SYNC_FILE_SIZE_BYTES} bytes)",
            400,
            {
                "maxSize": MAX_WORKSPACE_SYNC_FILE_SIZE_BYTES,
                "actualSize": len(content),
            },
        )

    sanitized_name = _sanitize_upload_file_name(file_name)
    workspace_relative_path = _resolve_unique_workspace_file_path(workspace_path, sanitized_name)
    saved_at = datetime.now(tz=timezone.utc).isoformat()
    content_hash = hashlib.sha256(content).hexdigest()

    from .workspace import write_workspace_file  # local import avoids circular

    try:
        write_workspace_file(workspace_path, workspace_relative_path, content)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Failed to save %s into workspace: %s", sanitized_name, exc
        )
        raise WorkspaceFileSyncError(
            WorkspaceFileSyncErrorCode.WRITE_FAILED,
            "Failed to save file into workspace",
            500,
            {"fileName": sanitized_name, "workspacePath": workspace_relative_path},
        ) from exc

    return {
        "type": "workspace-file",
        "fileName": sanitized_name,
        "mimeType": normalized_mime,
        "size": len(content),
        "workspacePath": workspace_relative_path,
        "savedAt": saved_at,
        "hash": content_hash,
    }


def normalize_workspace_file_sync_error(error: object) -> WorkspaceFileSyncError:
    """Coerce *error* to a :class:`WorkspaceFileSyncError`.

    If *error* is already a ``WorkspaceFileSyncError`` it is returned
    unchanged.  Any other exception is wrapped as ``INTERNAL_ERROR``.
    """
    if isinstance(error, WorkspaceFileSyncError):
        return error

    return WorkspaceFileSyncError(
        WorkspaceFileSyncErrorCode.INTERNAL_ERROR,
        "Unexpected workspace file sync error",
        500,
    )


# ---------------------------------------------------------------------------
# Attachment → workspace sync (ported from claude-agent-next-kit
# chat-attachment-processing.ts / workspace-file-sync.ts, WeKnora excluded)
# ---------------------------------------------------------------------------


def _resolve_workspace_part_from_attachment_metadata(
    workspace_path: Path,
    attachment: dict,
) -> Optional[dict]:
    """Return a ``workspace-file`` part dict if the attachment already names
    an existing file inside the workspace, otherwise return ``None``.

    This mirrors ``resolveWorkspacePartFromAttachmentMetadata`` from
    ``workspace-file-sync.ts`` in claude-agent-next-kit.
    """
    import os as _os

    raw_path = attachment.get("workspacePath")
    if not raw_path:
        return None

    # Normalize: strip leading slashes, convert backslashes.
    normalized = raw_path.replace("\\", "/").lstrip("/")
    full_path = (workspace_path / normalized).resolve()
    files_root = (workspace_path / "files").resolve()

    # Security: the resolved path must stay inside workspace/files/.
    try:
        full_path.relative_to(files_root)
    except ValueError:
        raise WorkspaceFileSyncError(
            WorkspaceFileSyncErrorCode.INVALID_WORKSPACE_PATH,
            "workspacePath must stay inside workspace files directory",
            400,
            {"workspacePath": raw_path},
        )

    if not full_path.exists():
        return None

    stat = full_path.stat()
    saved_at_raw = attachment.get("savedAt")
    try:
        from datetime import datetime, timezone
        saved_at = (
            datetime.fromisoformat(saved_at_raw).astimezone(timezone.utc).isoformat()
            if saved_at_raw
            else datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        )
    except (ValueError, OSError):
        from datetime import datetime, timezone
        saved_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    return {
        "type": "workspace-file",
        "fileName": attachment.get("filename") or _os.path.basename(normalized),
        "mimeType": _normalize_mime_type(attachment.get("mediaType")),
        "size": attachment.get("size") or stat.st_size,
        "workspacePath": normalized,
        "savedAt": saved_at,
        "hash": attachment.get("hash"),
    }


async def sync_attachments_to_workspace_files(
    workspace_path: Path,
    attachments: list,
    download_file: "Callable[[str, Optional[str]], Awaitable[tuple[bytes, str]]]",
) -> list:
    """Download each ``file``-type attachment and save it to the workspace.

    Parameters
    ----------
    workspace_path:
        Absolute path to the workspace root (from ``get_or_create_workspace``).
    attachments:
        List of attachment dicts matching the ``ChatAttachment`` schema
        ``{type, url, storageKey?, mediaType?, filename?, size?, workspacePath?, ...}``.
    download_file:
        Async callable ``(url, storage_key) -> (bytes, content_type)`` that
        retrieves the file content from the storage backend.

    Returns
    -------
    list of ``workspace-file`` part dicts, one per successfully synced file.

    Ported from ``syncAttachmentsToWorkspaceFiles`` in
    ``claude-agent-next-kit/app/lib/workspace-file-sync.ts`` (WeKnora excluded).
    """
    synced_parts: list = []

    for index, attachment in enumerate(attachments):
        if attachment.get("type") != "file":
            continue

        url = attachment.get("url")
        if not url:
            raise WorkspaceFileSyncError(
                WorkspaceFileSyncErrorCode.INVALID_ATTACHMENT,
                "Attachment url is required for file sync",
                400,
                {"index": index},
            )

        # Fast path: attachment already points to an existing workspace file.
        existing_part = _resolve_workspace_part_from_attachment_metadata(
            workspace_path, attachment
        )
        if existing_part:
            synced_parts.append(existing_part)
            continue

        # Download the file from storage.
        storage_key = attachment.get("storageKey")
        try:
            content, content_type = await download_file(url, storage_key)
        except WorkspaceFileSyncError:
            raise
        except Exception as exc:
            raise WorkspaceFileSyncError(
                WorkspaceFileSyncErrorCode.DOWNLOAD_FAILED,
                "Failed to download attachment before workspace sync",
                502,
                {
                    "index": index,
                    "url": url,
                    "reason": str(exc),
                },
            ) from exc

        inferred_mime = _normalize_mime_type(
            attachment.get("mediaType") or content_type or "application/octet-stream"
        )

        try:
            part = save_buffer_to_workspace_files(
                workspace_path,
                file_name=attachment.get("filename"),
                mime_type=inferred_mime,
                content=content,
            )
            synced_parts.append(part)
        except WorkspaceFileSyncError as exc:
            details = dict(exc.details) if isinstance(exc.details, dict) else {"details": exc.details}
            raise WorkspaceFileSyncError(
                exc.code,
                str(exc),
                exc.status,
                {"index": index, "fileName": attachment.get("filename"), "mimeType": inferred_mime, **details},
            ) from exc
        except Exception as exc:
            raise WorkspaceFileSyncError(
                WorkspaceFileSyncErrorCode.INTERNAL_ERROR,
                "Unexpected error while syncing file to workspace",
                500,
                {
                    "index": index,
                    "fileName": attachment.get("filename"),
                    "reason": str(exc),
                },
            ) from exc

    return synced_parts


def inject_attachment_message_parts(
    original_parts: Optional[list],
    attachment_parts: list,
) -> list:
    """Insert *attachment_parts* immediately before the last text part.

    If there are no text parts, the attachment parts are appended at the end.
    Empty *attachment_parts* returns *original_parts* unchanged.

    Ported from ``injectAttachmentMessageParts`` in
    ``claude-agent-next-kit/app/lib/chat-attachment-processing.ts``.
    """
    base_parts: list = list(original_parts or [])

    if not attachment_parts:
        return base_parts

    insertion_index = -1
    for i in range(len(base_parts) - 1, -1, -1):
        if isinstance(base_parts[i], dict) and base_parts[i].get("type") == "text":
            insertion_index = i
            break

    if insertion_index != -1:
        for i, part in enumerate(attachment_parts):
            base_parts.insert(insertion_index + i, part)
        return base_parts

    return base_parts + attachment_parts
