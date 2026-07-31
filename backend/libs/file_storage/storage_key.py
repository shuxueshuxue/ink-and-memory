"""
Storage key validation and encoding helpers.

Mirrors app/lib/file-storage/storage-key.ts from claude-agent-next-kit.
"""

from __future__ import annotations

import base64
import re
from typing import Optional

STORAGE_KEY_BASE64_PREFIX = "k64_"
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F\x7F]")
_MAX_SEGMENT_LEN = 1024
_MAX_KEY_LEN = 4096


def _is_valid_segment(segment: str) -> bool:
    if not segment or len(segment) > _MAX_SEGMENT_LEN:
        return False
    if segment in (".", ".."):
        return False
    if "/" in segment or "\\" in segment:
        return False
    if _CONTROL_CHAR_RE.search(segment):
        return False
    return True


def is_valid_storage_key(key: str) -> bool:
    """Return True if *key* is a well-formed storage key."""
    if not key or len(key) > _MAX_KEY_LEN:
        return False
    return all(_is_valid_segment(seg) for seg in key.split("/"))


def decode_storage_key_segments(segments: list[str]) -> Optional[str]:
    """
    URL-decode each path segment, validate it, and return the assembled key.
    Returns None if any segment fails validation.
    """
    from urllib.parse import unquote

    decoded: list[str] = []
    for seg in segments:
        try:
            value = unquote(seg)
        except Exception:
            return None
        if not _is_valid_segment(value):
            return None
        decoded.append(value)

    key = "/".join(decoded)
    return key if is_valid_storage_key(key) else None


def encode_storage_key_for_path(key: str) -> Optional[str]:
    """
    Percent-encode each segment of a storage key for safe embedding in a URL path.
    Returns None if the key is invalid.
    """
    from urllib.parse import quote

    if not is_valid_storage_key(key):
        return None
    return "/".join(quote(seg, safe="") for seg in key.split("/"))


def _to_base64url(b64: str) -> str:
    return b64.replace("+", "-").replace("/", "_").rstrip("=")


def _from_base64url(b64url: str) -> str:
    b64 = b64url.replace("-", "+").replace("_", "/")
    return b64 + "=" * ((4 - len(b64) % 4) % 4)


def encode_storage_key_to_base64_segment(key: str) -> Optional[str]:
    """
    Encode a storage key as a single URL-path segment using base64url.
    Returns None if the key is invalid.
    Segment is prefixed with STORAGE_KEY_BASE64_PREFIX.
    """
    if not is_valid_storage_key(key):
        return None
    b64 = base64.b64encode(key.encode("utf-8")).decode("ascii")
    return f"{STORAGE_KEY_BASE64_PREFIX}{_to_base64url(b64)}"


def decode_storage_key_from_base64_segment(raw_segment: str) -> Optional[str]:
    """
    Decode a base64-segment produced by encode_storage_key_to_base64_segment.
    Returns None if the segment is malformed or decodes to an invalid key.
    """
    if not raw_segment.startswith(STORAGE_KEY_BASE64_PREFIX):
        return None
    encoded = raw_segment[len(STORAGE_KEY_BASE64_PREFIX):]
    if not encoded:
        return None
    try:
        utf8 = base64.b64decode(_from_base64url(encoded)).decode("utf-8")
    except Exception:
        return None
    return utf8 if is_valid_storage_key(utf8) else None
