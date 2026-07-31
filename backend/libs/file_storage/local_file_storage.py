"""
Local filesystem file storage backend.

Used for local development when no cloud storage service is configured.
Stores files under a configurable base directory and serves them via the
/api/storage/file/ proxy endpoint.
"""

from __future__ import annotations

import logging
import os
import posixpath
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .interface import (
    FileMetadata,
    FileNotFoundError,
    FileStorage,
    UploadOptions,
    UploadResult,
    UploadUrlOptions,
)
from .storage_utils import (
    get_content_type_from_filename,
    resolve_storage_prefix,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path(__file__).resolve().parents[3] / "data" / "file-storage"


def _resolve_base_dir() -> Path:
    raw = os.environ.get("FILE_STORAGE_LOCAL_DIR", "")
    return Path(raw) if raw.strip() else _DEFAULT_BASE_DIR


class LocalFileStorage(FileStorage):
    """
    Simple local-disk storage backend.

    Files are written to ``<base_dir>/<prefix>/<uuid>-<filename>``.
    Public URLs are served via ``/api/storage/file/<base64key>``.
    """

    def __init__(self, public_base_url: str = "/api/storage/file") -> None:
        self._base_dir = _resolve_base_dir()
        self._prefix = resolve_storage_prefix()
        self._public_base_url = public_base_url.rstrip("/")

    def _key_to_path(self, key: str) -> Path:
        return self._base_dir / key

    def _build_key(self, filename: str) -> str:
        safe_name = sanitize_filename(filename or "file")
        uid = uuid.uuid4().hex
        return posixpath.join(self._prefix, f"{uid}-{safe_name}") if self._prefix else f"{uid}-{safe_name}"

    def _public_url(self, key: str) -> str:
        import base64
        encoded = base64.b64encode(key.encode()).decode("ascii")
        return f"{self._public_base_url}/{encoded}"

    # ------------------------------------------------------------------
    # FileStorage interface
    # ------------------------------------------------------------------

    async def upload(self, content: bytes, options: Optional[UploadOptions] = None) -> UploadResult:
        opts = options or UploadOptions()
        filename = opts.filename or "file"
        key = self._build_key(filename)
        content_type = opts.content_type or get_content_type_from_filename(filename)

        dest = self._key_to_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

        metadata = FileMetadata(
            key=key,
            filename=posixpath.basename(key),
            content_type=content_type,
            size=len(content),
            uploaded_at=datetime.now(tz=timezone.utc),
        )
        return UploadResult(key=key, source_url=self._public_url(key), metadata=metadata)

    async def download(self, key: str) -> bytes:
        path = self._key_to_path(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return self._key_to_path(key).exists()

    async def get_metadata(self, key: str) -> Optional[FileMetadata]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        stat = path.stat()
        return FileMetadata(
            key=key,
            filename=path.name,
            content_type=get_content_type_from_filename(path.name),
            size=stat.st_size,
            uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )

    async def get_source_url(self, key: str) -> Optional[str]:
        if not await self.exists(key):
            return None
        return self._public_url(key)
