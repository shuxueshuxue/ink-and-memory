"""
Storage utility functions.

Mirrors app/lib/file-storage/storage-utils.ts from claude-agent-next-kit.
"""

from __future__ import annotations

import base64
import re
from typing import Optional
from urllib.parse import urlparse


def sanitize_filename(filename: str) -> str:
    """Remove path separators and replace non-safe characters with underscores."""
    # Take only the last path component
    base = re.split(r"[/\\]", filename)[-1] if filename else "file"
    # Allow alphanumeric, dot, underscore, hyphen
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return sanitized or "file"


# Map of lowercase file extensions to MIME types
_MIME_TYPES: dict[str, str] = {
    # Images
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    # Documents
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Text
    "txt": "text/plain",
    "html": "text/html",
    "css": "text/css",
    "js": "text/javascript",
    "json": "application/json",
    "xml": "application/xml",
    "csv": "text/csv",
    "md": "text/markdown",
    # Audio
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    # Video
    "mp4": "video/mp4",
    "webm": "video/webm",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    # Archives
    "zip": "application/zip",
    "rar": "application/x-rar-compressed",
    "7z": "application/x-7z-compressed",
    "tar": "application/x-tar",
    "gz": "application/gzip",
}


def get_content_type_from_filename(filename: str) -> str:
    """
    Infer a MIME content-type from the file extension.
    Returns 'application/octet-stream' for unknown types.
    """
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        ext = parts[1].lower()
        if ext in _MIME_TYPES:
            return _MIME_TYPES[ext]
    return "application/octet-stream"


def resolve_storage_prefix() -> str:
    """
    Read FILE_STORAGE_PREFIX from environment (default: 'uploads').
    Strips leading and trailing slashes/dots.
    """
    import os

    raw = os.environ.get("FILE_STORAGE_PREFIX", "uploads")
    return raw.strip("/.").strip()


def storage_key_from_url(url: str) -> Optional[str]:
    """Extract the storage key (path without leading slash) from a URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        return path or None
    except Exception:
        return None


def decode_base64_key(encoded: str) -> str:
    """
    Decode a storage key that was base64-encoded (used in file-proxy URLs).
    Accepts both standard and URL-safe base64 with optional padding.
    """
    # Normalise URL-safe characters
    b64 = encoded.replace("-", "+").replace("_", "/")
    # Re-add padding
    b64 += "=" * ((4 - len(b64) % 4) % 4)
    return base64.b64decode(b64).decode("utf-8")


def encode_key_to_base64(key: str) -> str:
    """Base64-encode a storage key for embedding in a URL path."""
    return base64.b64encode(key.encode("utf-8")).decode("ascii")
