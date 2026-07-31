"""
File storage interface and data types.

Mirrors the TypeScript interface in app/lib/file-storage/file-storage.interface.ts
from the claude-agent-next-kit reference project.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass
class FileMetadata:
    """Metadata describing a stored file."""

    key: str
    filename: str
    content_type: str
    size: int
    uploaded_at: Optional[datetime] = field(default=None)


@dataclass
class UploadOptions:
    """Options for server-side file upload."""

    filename: Optional[str] = None
    content_type: Optional[str] = None


@dataclass
class UploadResult:
    """Result returned after a successful upload."""

    key: str
    # Public URL accessible by anyone (CDN / bucket URL)
    source_url: str
    metadata: FileMetadata


UploadUrlMethod = Literal["PUT", "POST"]


@dataclass
class UploadUrl:
    """Pre-signed / client-side direct upload descriptor."""

    key: str
    url: str
    method: UploadUrlMethod
    expires_at: datetime
    headers: Optional[dict[str, str]] = field(default=None)
    fields: Optional[dict[str, str]] = field(default=None)


@dataclass
class UploadUrlOptions:
    """Options for creating a pre-signed upload URL."""

    filename: str
    content_type: str
    expires_in_seconds: int = 900


class FileStorage(ABC):
    """Abstract base class for file storage backends."""

    @abstractmethod
    async def upload(
        self, content: bytes, options: Optional[UploadOptions] = None
    ) -> UploadResult:
        """Upload file bytes from the server and return public URL + metadata."""

    async def create_upload_url(
        self, options: UploadUrlOptions
    ) -> Optional[UploadUrl]:
        """
        Create a short-lived direct-upload target for clients (e.g. pre-signed URL).
        Return None if the backend does not support client-side uploads.
        """
        return None

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Retrieve file bytes by storage key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file from storage."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether a file exists without downloading it."""

    @abstractmethod
    async def get_metadata(self, key: str) -> Optional[FileMetadata]:
        """Fetch stored metadata for a key, or None if not found."""

    @abstractmethod
    async def get_source_url(self, key: str) -> Optional[str]:
        """Return the public URL for a key, or None if not found."""

    async def get_download_url(self, key: str) -> Optional[str]:
        """
        Return a forced-download URL if the backend supports it.
        Falls back to the public source URL by default.
        """
        return await self.get_source_url(key)


class FileNotFoundError(Exception):
    """Raised when a requested file does not exist in storage."""

    def __init__(self, key: str, cause: Optional[Exception] = None) -> None:
        super().__init__(f"File not found: {key}")
        self.key = key
        self.cause = cause
