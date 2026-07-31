#!/usr/bin/env python3
# [Input] Consume workspace lib from libs/claude_agent_kit/server/workspace*,
#         shared bearer auth, and FastAPI form/file helpers.
# [Output] Register workspace file management endpoints:
#          GET/POST/DELETE/PATCH /api/workspace/files
#          GET /api/workspace/files/download
# [Pos] workspace route node in backend/routers
# [Sync] 2026-05-25: initial implementation — ported from claude-agent-next-kit
#         app/api/workspace/files/route.ts and app/api/workspace/files/download/route.ts.
# [Sync] 2026-06-06: remove POST /api/workspace/memory-init (Voice scenario memory
#         workspace initialisation removed; Reflections uses /api/reflections/memory-init).
#         project .claude/memory/ filesystem fallback also removed from memory_workspace.py.
# [Sync] 2026-06-13: download responses use ASCII Content-Disposition fallback
#         plus RFC 8187 filename* so non-Latin filenames do not crash ASGI headers.
# [Sync] 2026-06-21: workspace file APIs initialize workspaces with Settings-backed
#                    sandbox filesystem and network policy, avoiding default-policy
#                    rewrites after Settings changes.
# [Sync] 2026-07-26: pass sandbox_fs_allowed_write_paths through workspace
#                    init kwargs so file-API refreshes do not drop user fs
#                    write paths from settings.json.

"""Workspace file management API.

Endpoints
---------
GET    /api/workspace/files          — list files in a workspace directory
POST   /api/workspace/files          — upload file(s) to a workspace
DELETE /api/workspace/files          — delete a file or directory
PATCH  /api/workspace/files          — move / rename a file
GET    /api/workspace/files/download — download a single workspace file
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re as _re
import socket
from typing import Annotated, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

import auth
import database
from libs.claude_agent_kit.server.workspace import (
    WorkspaceFileAccessError,
    delete_workspace_file,
    get_or_create_workspace,
    get_workspace_root,
    list_workspace_file_tree,
    list_workspace_files,
    move_workspace_file,
    read_workspace_file_content,
    write_workspace_file,
    WorkspaceFileInfo,
    WorkspaceFileTreeNode,
    WORKSPACE_SUBDIRS,
)
from libs.claude_agent_kit.server.workspace_file_sync import (
    WorkspaceFileSyncErrorCode,
    normalize_workspace_file_sync_error,
    save_buffer_to_workspace_files,
)

from .deps import http_bearer

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def _require_workspace_auth(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    token = credentials.credentials if credentials else None
    user_data = auth.verify_access_token(token) if token else None
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _debug_headers() -> dict[str, str]:
    """Return diagnostic headers identifying the server instance."""
    return {
        "x-workspace-instance-host": socket.gethostname(),
        "x-workspace-instance-pid": str(os.getpid()),
    }


_SESSION_ID_RE = _re.compile(r'^[A-Za-z0-9_-]{1,128}$')
_SANDBOX_NETWORK_MODES = {"disabled", "allowlist", "open"}


def _validate_session_id(session_id: str) -> str:
    """Validate that *session_id* is a safe alphanumeric identifier.

    Raises :class:`HTTPException` 400 if the value contains path separators,
    ``..``, or other characters that could be abused in filesystem operations.
    """
    if not session_id or not _SESSION_ID_RE.match(session_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid sessionId: must be 1-128 alphanumeric, dash, or underscore characters"},
        )
    return session_id


def _coerce_sandbox_network_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in _SANDBOX_NETWORK_MODES else "allowlist"


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _workspace_init_kwargs_for_user(current_user: dict) -> dict:
    """Return Settings-backed workspace initialization kwargs for a user."""

    try:
        user_id = int(current_user.get("user_id"))
        system_config = database.get_system_config(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to load workspace settings from system_config; using defaults. Error: %s",
            exc,
        )
        system_config = {}

    return {
        "sandbox_enabled": bool(system_config.get("workspace_enabled", True)),
        "sandbox_network_mode": _coerce_sandbox_network_mode(
            system_config.get("sandbox_network_mode")
        ),
        "sandbox_network_allowed_domains": _coerce_string_list(
            system_config.get("sandbox_network_allowed_domains")
        ),
        "sandbox_fs_allowed_write_paths": _coerce_string_list(
            system_config.get("sandbox_fs_allowed_write_paths")
        ),
    }


def _get_or_create_workspace_for_user(session_id: str, current_user: dict):
    """Create or refresh a workspace without reverting user sandbox settings."""

    return get_or_create_workspace(
        session_id,
        **_workspace_init_kwargs_for_user(current_user),
    )


def _normalize_incoming_relative_path(raw_path: str) -> str:
    """Sanitise an untrusted relative path from a request.

    Returns an empty string for any path that is blank, contains ``..``,
    or resolves to nothing.
    """
    normalized = (
        raw_path.replace("\\", "/")
        .lstrip("/")
        .replace("//", "/")
    )
    segments = [s for s in normalized.split("/") if s and s != "."]

    if not segments or any(s == ".." for s in segments):
        return ""

    return "/".join(segments)


def _file_info_to_dict(info: WorkspaceFileInfo) -> dict:
    return {
        "name": info.name,
        "path": info.path,
        "isDirectory": info.is_directory,
        "size": info.size,
        "modifiedAt": info.modified_at,
    }


def _tree_node_to_dict(node: WorkspaceFileTreeNode) -> dict:
    d = _file_info_to_dict(node)  # type: ignore[arg-type]
    if node.children is not None:
        d["children"] = [_tree_node_to_dict(c) for c in node.children]
    return d


def _get_content_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _download_content_disposition(filename: str) -> str:
    """Return a Latin-1-safe attachment disposition for any workspace filename."""
    fallback = _re.sub(r"[^A-Za-z0-9._ -]+", "_", filename).strip()
    if not fallback or fallback in {".", ".."}:
        fallback = "download"
    utf8_name = quote(filename, safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{utf8_name}'


# ---------------------------------------------------------------------------
# GET /api/workspace/files
# ---------------------------------------------------------------------------


@router.get("/api/workspace/files")
async def list_workspace_files_endpoint(
    session_id: Annotated[str, Query(alias="sessionId")],
    path: Annotated[str, Query()] = "",
    recursive: Annotated[str, Query()] = "",
    current_user: dict = Depends(_require_workspace_auth),
) -> Response:
    """List files in a workspace directory.

    Query params
    ------------
    sessionId : str   — workspace session identifier (required)
    path      : str   — subdirectory relative to workspace root (optional)
    recursive : str   — set to ``"1"`` or ``"true"`` to include a file tree
    """
    if not session_id:
        raise HTTPException(status_code=400, detail={"error": "sessionId is required"})
    _validate_session_id(session_id)

    is_recursive = recursive in ("1", "true")

    try:
        workspace_root = get_workspace_root()
        workspace_full_path = workspace_root / session_id
        workspace_existed_before = workspace_full_path.exists()
        workspace_path = _get_or_create_workspace_for_user(session_id, current_user)
        files = [_file_info_to_dict(f) for f in list_workspace_files(workspace_path, path)]
        tree = (
            [_tree_node_to_dict(n) for n in list_workspace_file_tree(workspace_path, path)]
            if is_recursive
            else None
        )
        workspace_created = not workspace_existed_before
        payload: dict = {
            "files": files,
            "recursive": is_recursive,
            "workspacePath": str(workspace_path),
            "workspaceCreated": workspace_created,
        }
        if tree is not None:
            payload["tree"] = tree
        if workspace_created and path:
            payload["warning"] = (
                "Workspace was created on this instance while listing a sub-path. "
                "This usually indicates non-shared storage or requests hitting different instances."
            )

        import json
        return Response(
            content=json.dumps(payload),
            media_type="application/json",
            headers=_debug_headers(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    except Exception as exc:
        logger.exception("Unexpected error listing workspace files")
        import json
        return Response(
            content=json.dumps({"error": "Internal server error"}),
            status_code=500,
            media_type="application/json",
            headers=_debug_headers(),
        )


# ---------------------------------------------------------------------------
# POST /api/workspace/files
# ---------------------------------------------------------------------------


@router.post("/api/workspace/files")
async def upload_workspace_files(
    session_id: Annotated[str, Form(alias="sessionId")],
    path: Annotated[Optional[str], Form()] = None,
    file: Annotated[List[UploadFile], FastAPIFile()] = (),
    relative_path: Annotated[Optional[List[str]], Form(alias="relativePath")] = None,
    current_user: dict = Depends(_require_workspace_auth),
) -> Response:
    """Upload one or more files into a workspace.

    Form fields
    -----------
    sessionId    : str         — workspace session identifier (required)
    path         : str         — target subdirectory inside the workspace (optional)
    file         : UploadFile+ — one or more files to upload (required)
    relativePath : str+        — per-file relative paths (optional; parallel to ``file``)
    """
    import json

    if not session_id:
        raise HTTPException(status_code=400, detail={"error": "sessionId is required"})
    _validate_session_id(session_id)

    target_path = (path or "").replace("\\", "/").strip("/")

    try:
        workspace_root = get_workspace_root()
        workspace_full_path = workspace_root / session_id
        workspace_existed_before = workspace_full_path.exists()
        workspace_path = _get_or_create_workspace_for_user(session_id, current_user)
        workspace_created = not workspace_existed_before
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    rel_paths: List[str] = list(relative_path or [])
    uploaded_files: List[str] = []
    uploaded_metadata: List[dict] = []

    files_dir = WORKSPACE_SUBDIRS[0]  # "files"

    for index, upload in enumerate(file):
        raw_rel = rel_paths[index] if index < len(rel_paths) else (upload.filename or "")
        normalized_rel = _normalize_incoming_relative_path(raw_rel)
        if not normalized_rel:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid relativePath for uploaded file #{index + 1}"},
            )

        content = await upload.read()
        file_path = f"{target_path}/{normalized_rel}" if target_path else normalized_rel

        is_single_to_files_dir = (
            target_path == files_dir and "/" not in normalized_rel
        )

        if is_single_to_files_dir:
            try:
                saved = save_buffer_to_workspace_files(
                    workspace_path,
                    file_name=upload.filename,
                    mime_type=upload.content_type or "application/octet-stream",
                    content=content,
                )
                uploaded_files.append(saved["workspacePath"])
                uploaded_metadata.append(saved)
            except Exception as exc:
                err = normalize_workspace_file_sync_error(exc)
                logger.warning("Workspace file upload failed: %s", err)
                return Response(
                    content=json.dumps({
                        "error": err.args[0] if err.args else "Upload failed",
                        "code": err.code.value if hasattr(err.code, "value") else str(err.code),
                    }),
                    status_code=err.status,
                    media_type="application/json",
                    headers=_debug_headers(),
                )
        else:
            try:
                write_workspace_file(workspace_path, file_path, content)
                uploaded_files.append(file_path)
            except Exception as exc:
                err = normalize_workspace_file_sync_error(exc)
                logger.warning("Workspace file write failed: %s", err)
                return Response(
                    content=json.dumps({
                        "error": err.args[0] if err.args else "Upload failed",
                        "code": err.code.value if hasattr(err.code, "value") else str(err.code),
                    }),
                    status_code=err.status,
                    media_type="application/json",
                    headers=_debug_headers(),
                )

    if not uploaded_files:
        raise HTTPException(status_code=400, detail={"error": "No files uploaded"})

    return Response(
        content=json.dumps({
            "uploaded": uploaded_files,
            "files": uploaded_metadata,
            "workspacePath": str(workspace_path),
            "workspaceCreated": workspace_created,
        }),
        media_type="application/json",
        headers=_debug_headers(),
    )


# ---------------------------------------------------------------------------
# DELETE /api/workspace/files
# ---------------------------------------------------------------------------


class _DeleteFilesRequest(BaseModel):
    sessionId: str
    path: str


@router.delete("/api/workspace/files")
async def delete_workspace_file_endpoint(
    body: _DeleteFilesRequest,
    current_user: dict = Depends(_require_workspace_auth),
) -> Response:
    """Delete a file or directory from a workspace.

    Body: ``{ "sessionId": "…", "path": "relative/path" }``
    """
    import json

    if not body.sessionId or not body.path:
        raise HTTPException(
            status_code=400,
            detail={"error": "sessionId and path are required"},
        )
    _validate_session_id(body.sessionId)

    try:
        workspace_path = _get_or_create_workspace_for_user(body.sessionId, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    deleted = delete_workspace_file(workspace_path, body.path)
    if not deleted:
        return Response(
            content=json.dumps({"error": "File not found"}),
            status_code=404,
            media_type="application/json",
            headers=_debug_headers(),
        )

    return Response(
        content=json.dumps({"deleted": True}),
        media_type="application/json",
        headers=_debug_headers(),
    )


# ---------------------------------------------------------------------------
# PATCH /api/workspace/files
# ---------------------------------------------------------------------------


class _MoveFilesRequest(BaseModel):
    sessionId: str
    fromPath: str
    toPath: str


@router.patch("/api/workspace/files")
async def move_workspace_file_endpoint(
    body: _MoveFilesRequest,
    current_user: dict = Depends(_require_workspace_auth),
) -> Response:
    """Move or rename a file within a workspace.

    Body: ``{ "sessionId": "…", "fromPath": "…", "toPath": "…" }``
    """
    import json

    if not body.sessionId or not body.fromPath or not body.toPath:
        raise HTTPException(
            status_code=400,
            detail={"error": "sessionId, fromPath, and toPath are required"},
        )
    _validate_session_id(body.sessionId)

    try:
        workspace_path = _get_or_create_workspace_for_user(body.sessionId, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    moved = move_workspace_file(workspace_path, body.fromPath, body.toPath)
    if not moved:
        return Response(
            content=json.dumps({"error": "File not found"}),
            status_code=404,
            media_type="application/json",
            headers=_debug_headers(),
        )

    return Response(
        content=json.dumps({"moved": True}),
        media_type="application/json",
        headers=_debug_headers(),
    )


# ---------------------------------------------------------------------------
# GET /api/workspace/files/download
# ---------------------------------------------------------------------------


@router.get("/api/workspace/files/download")
async def download_workspace_file(
    session_id: Annotated[str, Query(alias="sessionId")],
    path: Annotated[str, Query()],
    current_user: dict = Depends(_require_workspace_auth),
) -> Response:
    """Download a single workspace file.

    Query params
    ------------
    sessionId : str — workspace session identifier (required)
    path      : str — relative path of the file to download (required)
    """
    if not session_id or not path:
        raise HTTPException(
            status_code=400,
            detail={"error": "sessionId and path are required"},
        )
    _validate_session_id(session_id)

    try:
        workspace_path = _get_or_create_workspace_for_user(session_id, current_user)
        file_obj = read_workspace_file_content(workspace_path, path)
    except WorkspaceFileAccessError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"error": exc.args[0], "code": exc.code},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    content_type = _get_content_type(file_obj.file_name)
    disposition = _download_content_disposition(file_obj.file_name)

    return Response(
        content=file_obj.content,
        media_type=content_type,
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(file_obj.size),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
