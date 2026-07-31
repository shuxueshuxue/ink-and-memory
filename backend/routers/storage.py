#!/usr/bin/env python3
# [Input] Consume file storage backends, shared bearer auth, and upload/download helpers.
# [Output] Register storage config, upload, upload-url, and file-serving endpoints.
# [Pos] storage route node in backend/routers
# [Sync] 2026-05-25: extracted storage routes from backend/server.py.
# [Sync] 2026-07-21: storage auth also accepts login cookies and a ?token= query
#                    param so browser-embedded file URLs (<img src>, download links)
#                    that cannot send Authorization headers no longer get 401.

import os
from typing import Optional

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

import auth
from libs.file_storage import (
    UploadOptions,
    UploadUrlOptions,
    decode_base64_key,
    encode_key_to_base64,
    get_content_type_from_filename,
    is_valid_storage_key,
    server_file_storage,
    storage_driver,
)
from libs.file_storage.interface import FileNotFoundError as StorageFileNotFoundError

from .deps import http_bearer

router = APIRouter()

_ALLOWED_CONTENT_TYPES: set[str] = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv", "text/markdown", "application/json",
    "application/zip", "application/x-tar", "application/gzip",
    "audio/mpeg", "audio/wav", "video/mp4", "video/webm",
    "application/octet-stream",
}


class UploadUrlRequest(BaseModel):
    filename: Optional[str] = None
    contentType: Optional[str] = None


def _require_storage_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get("access_token") or request.cookies.get("token")
    if not token:
        # Browser-embedded file URLs (<img src>, <a href download>) cannot set
        # Authorization headers, so accept the token as a query parameter.
        token = request.query_params.get("token")
    user_data = auth.verify_access_token(token) if token else None
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_data


def _validate_content_type(provided_type: str, filename: str) -> str:
    """Normalise content type; fall back to extension inference then octet-stream."""
    normalized = provided_type.lower().split(";")[0].strip() if provided_type else ""
    if normalized in _ALLOWED_CONTENT_TYPES:
        return normalized
    inferred = get_content_type_from_filename(filename)
    return inferred if inferred in _ALLOWED_CONTENT_TYPES else "application/octet-stream"


def _check_storage_configuration() -> dict:
    """Return a dict describing whether storage is properly configured."""
    if storage_driver == "s3":
        missing = []
        if not os.environ.get("FILE_STORAGE_S3_BUCKET"):
            missing.append("FILE_STORAGE_S3_BUCKET")
        if not os.environ.get("FILE_STORAGE_S3_REGION") and not os.environ.get("AWS_REGION"):
            missing.append("FILE_STORAGE_S3_REGION or AWS_REGION")
        if missing:
            return {
                "is_valid": False,
                "error": f"Missing S3 configuration: {', '.join(missing)}",
                "solution": (
                    "Add required env vars for S3 file storage:\n"
                    "- FILE_STORAGE_TYPE=s3\n"
                    "- FILE_STORAGE_S3_BUCKET=your-bucket\n"
                    "- FILE_STORAGE_S3_REGION=your-region (e.g., us-east-1)\n"
                    "(Optional) FILE_STORAGE_S3_PUBLIC_BASE_URL=https://cdn.example.com\n"
                    "(Optional) FILE_STORAGE_S3_ENDPOINT for S3-compatible stores (e.g., MinIO)\n"
                    "(Optional) FILE_STORAGE_S3_FORCE_PATH_STYLE=1 for path-style endpoints"
                ),
            }
    return {"is_valid": True}


@router.get("/api/storage")
async def get_storage_config(current_user: dict = Depends(_require_storage_auth)):
    """
    GET /api/storage

    Returns current storage configuration status.
    Used by clients to determine upload strategy.
    """
    del current_user

    check = _check_storage_configuration()
    response: dict = {
        "type": storage_driver,
        "supportsDirectUpload": storage_driver == "s3",
        "isConfigured": check["is_valid"],
    }
    if not check["is_valid"]:
        response["error"] = check.get("error")
        response["solution"] = check.get("solution")
    return response


@router.post("/api/storage/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    current_user: dict = Depends(_require_storage_auth),
):
    """
    POST /api/storage/upload

    Direct file upload endpoint.
    Accepts multipart/form-data with a 'file' field.
    """
    del current_user

    check = _check_storage_configuration()
    if not check["is_valid"]:
        raise HTTPException(
            status_code=500,
            detail={
                "error": check.get("error"),
                "solution": check.get("solution"),
                "storageDriver": storage_driver,
            },
        )

    if not file:
        raise HTTPException(status_code=400, detail={"error": "No file provided. Use 'file' field in FormData."})

    content_type = _validate_content_type(file.content_type or "", file.filename or "file")

    try:
        content = await file.read()
        result = await server_file_storage.upload(
            content,
            UploadOptions(filename=file.filename or "file", content_type=content_type),
        )
        return {
            "success": True,
            "key": result.key,
            "url": f"/api/storage/file/{encode_key_to_base64(result.key)}",
            "metadata": {
                "key": result.metadata.key,
                "filename": result.metadata.filename,
                "contentType": result.metadata.content_type,
                "size": result.metadata.size,
                "uploadedAt": result.metadata.uploaded_at.isoformat() if result.metadata.uploaded_at else None,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Failed to upload file"}) from exc


@router.post("/api/storage/upload-url")
async def get_upload_url(
    body: UploadUrlRequest,
    current_user: dict = Depends(_require_storage_auth),
):
    """
    POST /api/storage/upload-url

    Returns a pre-signed URL for direct client-side upload (S3) or a fallback
    server-upload URL when direct upload is not supported.
    """
    del current_user

    check = _check_storage_configuration()
    if not check["is_valid"]:
        raise HTTPException(
            status_code=500,
            detail={
                "error": check.get("error"),
                "solution": check.get("solution"),
                "storageDriver": storage_driver,
            },
        )

    try:
        upload_url = await server_file_storage.create_upload_url(
            UploadUrlOptions(
                filename=body.filename or "file",
                content_type=body.contentType or "application/octet-stream",
                expires_in_seconds=3600,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Failed to create upload URL"}) from exc

    if upload_url is None:
        return {
            "directUploadSupported": False,
            "fallbackUrl": "/api/storage/upload",
            "message": "Use multipart/form-data upload to fallbackUrl",
        }

    return {
        "directUploadSupported": True,
        "key": upload_url.key,
        "url": upload_url.url,
        "method": upload_url.method,
        "expiresAt": upload_url.expires_at.isoformat(),
        "headers": upload_url.headers or {},
    }


@router.get("/api/storage/file/{encoded_key}")
async def serve_file(
    encoded_key: str,
    current_user: dict = Depends(_require_storage_auth),
):
    """
    GET /api/storage/file/{encoded_key}

    Proxy endpoint that decodes the base64 storage key and streams the file
    content from the backend storage (used by local and S3 backends).
    For S3 with a public bucket, clients may use the direct source URL instead.
    """
    del current_user

    try:
        key = decode_base64_key(encoded_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file key encoding")

    if not is_valid_storage_key(key):
        raise HTTPException(status_code=400, detail="Invalid storage key")

    try:
        content = await server_file_storage.download(key)
    except StorageFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to retrieve file") from exc

    metadata = await server_file_storage.get_metadata(key)
    content_type = metadata.content_type if metadata else get_content_type_from_filename(key)
    filename = metadata.filename if metadata else key.rsplit("/", 1)[-1]

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
