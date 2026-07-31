#!/usr/bin/env python3
# [Input] Consume database system-config APIs and shared auth dependency.
# [Output] Register GET/PUT /api/system-config endpoints.
# [Pos] system-config route node in backend/routers
# [Sync] 2026-05-27: initial implementation — system config (model, theme, env_vars, etc.).
# [Sync] 2026-06-09: accept im_full_access_enabled for Settings-controlled
#                    Claude-agent full-access tool approval.
# [Sync] 2026-06-13: workspace_enabled also controls per-thread Claude Code
#                    Bash sandbox settings written into .claude/settings.json.
# [Sync] 2026-06-21: accept sandbox network policy and allowed domains.
# [Sync] 2026-06-25: return merged config from PUT so Settings can hydrate
#                    sanitized sandbox-network values after save.
# [Sync] 2026-07-26: accept sandbox_fs_allowed_write_paths — extra absolute
#                    writable paths for the per-thread Bash sandbox
#                    (absolute-only, trailing-slash stripped, deduped, capped).

"""System configuration API.

Endpoints
---------
GET  /api/system-config  — retrieve the caller's system config
PUT  /api/system-config  — merge a partial update into the caller's system config

The system config is a freeform dict stored per user.  Known fields:

  provider         : str  — LLM provider ("anthropic" | "openai")
  model            : str  — model name
  system_prompt    : str  — custom system prompt for the AI agent
  workspace_enabled: bool — whether the workspace file sidebar and per-thread
                            Bash sandbox are active
  sandbox_network_mode: str — per-thread Bash sandbox network policy
                            ("disabled" | "allowlist" | "open")
  sandbox_network_allowed_domains: list[str] — domains pre-allowed when the
                            sandbox network policy is "allowlist"
  sandbox_fs_allowed_write_paths: list[str] — additional absolute paths the
                            per-thread Bash sandbox may write (appended to
                            filesystem.allowWrite after the thread workspace
                            and Claude Code's own sandbox TMPDIR)
  im_full_access_enabled: bool — whether Claude-agent PreToolUse approvals
                            should allow exposed tools automatically except
                            AskUserQuestion-style answer forms
  theme            : str  — UI theme ("light" | "dark" | "system")
  env_vars         : dict — user-supplied env vars forwarded to skills/MCP servers
                            as key→value string pairs
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

import database
from .deps import get_current_user

router = APIRouter()

# Keys that must be string→string when present in env_vars to prevent injection
_ENV_VAR_KEY_MAX_LEN = 256
_ENV_VAR_VALUE_MAX_LEN = 4096
_ENV_VARS_MAX_ENTRIES = 64
_SANDBOX_NETWORK_MODES = {"disabled", "allowlist", "open"}
_SANDBOX_NETWORK_ALLOWED_DOMAIN_MAX_ENTRIES = 64
_SANDBOX_NETWORK_ALLOWED_DOMAIN_MAX_LEN = 253
_SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_ENTRIES = 32
_SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_LEN = 512
_SANDBOX_DOMAIN_PATTERN = re.compile(
    r"^(?:\*\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def _sanitize_env_vars(raw: object) -> dict[str, str]:
    """Validate and normalise env_vars from the request body.

    Accepts only a flat dict[str, str].  Keys and values are trimmed and
    truncated; keys must be non-empty after trimming.  At most
    ``_ENV_VARS_MAX_ENTRIES`` entries are accepted (excess entries are
    silently dropped).
    """
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).strip()[: _ENV_VAR_KEY_MAX_LEN]
        v = str(value).strip()[: _ENV_VAR_VALUE_MAX_LEN]
        if k:
            result[k] = v
        if len(result) >= _ENV_VARS_MAX_ENTRIES:
            break
    return result


def _domain_candidate(raw: object) -> str:
    """Extract a hostname-like sandbox domain pattern from user input."""

    value = str(raw).strip().lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = parsed.hostname or value.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.strip().rstrip(".")[:_SANDBOX_NETWORK_ALLOWED_DOMAIN_MAX_LEN]
    if value.startswith("*.") and not host.startswith("*."):
        host = f"*.{host}"
    return host


def _sanitize_sandbox_network_allowed_domains(raw: object) -> list[str]:
    """Validate and normalize sandbox network allowed-domain patterns."""

    if isinstance(raw, str):
        items: list[object] = re.split(r"[\s,;]+", raw)
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    result: list[str] = []
    for item in items:
        domain = _domain_candidate(item)
        if (
            domain
            and domain != "*"
            and _SANDBOX_DOMAIN_PATTERN.match(domain)
            and domain not in result
        ):
            result.append(domain)
        if len(result) >= _SANDBOX_NETWORK_ALLOWED_DOMAIN_MAX_ENTRIES:
            break
    return result


def _sanitize_sandbox_fs_allowed_write_paths(raw: object) -> list[str]:
    """Validate and normalize sandbox filesystem extra writable paths.

    Mirrors the domains sanitizer's reject-silently policy: accepts a list
    (or a whitespace/comma/semicolon separated string), keeps only absolute
    paths, strips trailing slashes (except the root ``/``), dedupes
    preserving order, and caps entry count / path length.
    """

    if isinstance(raw, str):
        items: list[object] = re.split(r"[\n,;]+", raw)
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    result: list[str] = []
    for item in items:
        path = str(item).strip()
        if not path or not path.startswith("/"):
            continue
        path = (path.rstrip("/") or "/")[: _SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_LEN]
        if path not in result:
            result.append(path)
        if len(result) >= _SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_ENTRIES:
            break
    return result


@router.get("/api/system-config")
def get_system_config(current_user: dict = Depends(get_current_user)):
    """Return the caller's system configuration."""
    user_id = current_user["user_id"]
    return database.get_system_config(user_id)


@router.put("/api/system-config")
def put_system_config(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    """Merge *request* into the caller's system configuration.

    Accepted keys: ``provider``, ``model``, ``system_prompt``,
    ``workspace_enabled``, ``sandbox_network_mode``,
    ``sandbox_network_allowed_domains``, ``sandbox_fs_allowed_write_paths``,
    ``im_full_access_enabled``, ``theme``, ``env_vars``.
    Unknown keys are ignored.
    """
    user_id = current_user["user_id"]

    patch: dict = {}

    if "provider" in request:
        patch["provider"] = str(request["provider"])[:64]
    if "model" in request:
        patch["model"] = str(request["model"])[:256]
    if "system_prompt" in request:
        patch["system_prompt"] = str(request["system_prompt"])[:16_384]
    if "workspace_enabled" in request:
        patch["workspace_enabled"] = bool(request["workspace_enabled"])
    if "sandbox_network_mode" in request:
        mode = str(request["sandbox_network_mode"]).strip().lower()
        if mode in _SANDBOX_NETWORK_MODES:
            patch["sandbox_network_mode"] = mode
    if "sandbox_network_allowed_domains" in request:
        patch["sandbox_network_allowed_domains"] = (
            _sanitize_sandbox_network_allowed_domains(
                request["sandbox_network_allowed_domains"]
            )
        )
    if "sandbox_fs_allowed_write_paths" in request:
        patch["sandbox_fs_allowed_write_paths"] = (
            _sanitize_sandbox_fs_allowed_write_paths(
                request["sandbox_fs_allowed_write_paths"]
            )
        )
    if "im_full_access_enabled" in request:
        patch["im_full_access_enabled"] = bool(request["im_full_access_enabled"])
    if "theme" in request:
        theme = str(request["theme"])
        if theme in ("light", "dark", "system"):
            patch["theme"] = theme
    if "env_vars" in request:
        patch["env_vars"] = _sanitize_env_vars(request["env_vars"])

    if patch:
        database.save_system_config(user_id, patch)

    return {"success": True, "data": database.get_system_config(user_id)}
