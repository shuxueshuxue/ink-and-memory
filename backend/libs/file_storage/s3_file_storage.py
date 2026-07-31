"""
AWS S3 (and S3-compatible, e.g. MinIO) file storage backend.

Mirrors app/lib/file-storage/s3-file-storage.ts from claude-agent-next-kit.
Requires boto3 (already present in the runtime environment).
"""

from __future__ import annotations

import logging
import os
import posixpath
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .interface import (
    FileMetadata,
    FileNotFoundError,
    FileStorage,
    UploadOptions,
    UploadResult,
    UploadUrl,
    UploadUrlOptions,
)
from .storage_utils import (
    get_content_type_from_filename,
    resolve_storage_prefix,
    sanitize_filename,
)

logger = logging.getLogger(__name__)


def _required(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_key(filename: str, prefix: str) -> str:
    safe_name = sanitize_filename(filename or "file")
    uid = uuid.uuid4().hex
    base = posixpath.join(prefix, f"{uid}-{safe_name}") if prefix else f"{uid}-{safe_name}"
    return base


def _build_public_url(
    bucket: str,
    region: str,
    key: str,
    public_base_url: Optional[str] = None,
    endpoint: Optional[str] = None,
    force_path_style: bool = False,
) -> str:
    if public_base_url:
        return f"{public_base_url.rstrip('/')}/{key}"

    if endpoint:
        base = endpoint.rstrip("/")
        if force_path_style:
            return f"{base}/{bucket}/{key}"
        from urllib.parse import urlparse
        parsed = urlparse(base)
        return f"{parsed.scheme}://{bucket}.{parsed.netloc}/{key}"

    # AWS standard virtual-hosted–style URL
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


class S3FileStorage(FileStorage):
    """File storage backend backed by AWS S3 or an S3-compatible service."""

    def __init__(self) -> None:
        self._bucket = _required("FILE_STORAGE_S3_BUCKET", os.environ.get("FILE_STORAGE_S3_BUCKET"))
        region = os.environ.get("FILE_STORAGE_S3_REGION") or os.environ.get("AWS_REGION")
        if not region:
            raise RuntimeError(
                "Missing required environment variable: FILE_STORAGE_S3_REGION or AWS_REGION"
            )
        self._region = region
        self._endpoint = os.environ.get("FILE_STORAGE_S3_ENDPOINT") or None
        self._force_path_style = os.environ.get("FILE_STORAGE_S3_FORCE_PATH_STYLE", "").lower() in (
            "1", "true", "yes",
        )
        self._public_base_url = os.environ.get("FILE_STORAGE_S3_PUBLIC_BASE_URL") or None
        self._prefix = resolve_storage_prefix()

        client_kwargs: dict = {
            "region_name": self._region,
        }
        if self._endpoint:
            client_kwargs["endpoint_url"] = self._endpoint
        if self._force_path_style:
            client_kwargs["config"] = boto3.session.Config(s3={"addressing_style": "path"})

        self._s3 = boto3.client("s3", **client_kwargs)

    # ------------------------------------------------------------------
    # FileStorage interface
    # ------------------------------------------------------------------

    async def upload(self, content: bytes, options: Optional[UploadOptions] = None) -> UploadResult:
        opts = options or UploadOptions()
        filename = opts.filename or "file"
        key = _build_key(filename, self._prefix)
        content_type = opts.content_type or get_content_type_from_filename(filename)

        extra_args: dict = {"ContentType": content_type}
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=content, **extra_args)

        metadata = FileMetadata(
            key=key,
            filename=posixpath.basename(key),
            content_type=content_type,
            size=len(content),
            uploaded_at=datetime.now(tz=timezone.utc),
        )
        source_url = _build_public_url(
            self._bucket,
            self._region,
            key,
            self._public_base_url,
            self._endpoint,
            self._force_path_style,
        )
        return UploadResult(key=key, source_url=source_url, metadata=metadata)

    async def create_upload_url(self, options: UploadUrlOptions) -> Optional[UploadUrl]:
        key = _build_key(options.filename, self._prefix)
        expires = max(60, min(43200, options.expires_in_seconds))

        url = self._s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": options.content_type,
            },
            ExpiresIn=expires,
        )

        from datetime import timedelta

        return UploadUrl(
            key=key,
            url=url,
            method="PUT",
            expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=expires),
            headers={"Content-Type": options.content_type},
        )

    async def download(self, key: str) -> bytes:
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                raise FileNotFoundError(key, exc) from exc
            raise

    async def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    async def get_metadata(self, key: str) -> Optional[FileMetadata]:
        try:
            resp = self._s3.head_object(Bucket=self._bucket, Key=key)
            return FileMetadata(
                key=key,
                filename=posixpath.basename(key),
                content_type=resp.get("ContentType", "application/octet-stream"),
                size=int(resp.get("ContentLength", 0)),
                uploaded_at=resp.get("LastModified"),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return None
            raise

    async def get_source_url(self, key: str) -> Optional[str]:
        if not await self.exists(key):
            return None
        return _build_public_url(
            self._bucket,
            self._region,
            key,
            self._public_base_url,
            self._endpoint,
            self._force_path_style,
        )

    async def get_download_url(self, key: str) -> Optional[str]:
        try:
            url = self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=3600,
            )
            return url
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return None
            raise
