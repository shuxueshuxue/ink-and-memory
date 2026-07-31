# [Input] Notion connector config and CLI runtime environment.
# [Output] Provide ntn login/poll/status helpers for Notion authentication.
# [Pos] auth node in backend/notion
# [Sync] 2026-07-04: initial Notion CLI auth flow — `ntn login --no-browser`,
#                    `ntn login poll`, and `ntn auth status` wrappers.
# [Sync] 2026-07-05: classify `no pending login session` and `authorization session already consumed`
#                    as terminal-pending signals for idempotent poll behavior.

"""Notion authentication helpers backed by the `ntn` CLI."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .errors import (
    NotionAuthError,
    NotionAuthTimeoutError,
    NotionCLIUnavailableError,
    NotionConfigError,
)

_DEFAULT_NOTION_HOME = Path.home() / ".config" / "notion"
_DEFAULT_LOGIN_TIMEOUT_S = 20.0
_DEFAULT_POLL_TIMEOUT_S = 15.0
_DEFAULT_STATUS_TIMEOUT_S = 10.0
_URL_RE = re.compile(r"https?://\S+")
_VERIFICATION_CODE_RE = re.compile(r"\b[A-Z0-9]{3,5}(?:-[A-Z0-9]{2,5})+\b")
_NO_PENDING_SESSION_TOKENS = (
    "no pending login session found",
    "authorization session already consumed",
)


@dataclass(frozen=True)
class LoginInitResult:
    """Parsed response from `ntn login --no-browser`."""

    verification_url: str
    verification_code: str
    poll_interval_seconds: int = 5
    notion_home: str = ""


@dataclass(frozen=True)
class AuthStatusResult:
    """Authentication status returned by the CLI wrapper."""

    status: str
    notion_home: str
    detail: str = ""
    verification_url: str = ""
    verification_code: str = ""


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def resolve_notion_home(config: Any = None) -> Path:
    """Return the configured Notion home directory.

    The connector config may expose ``notion_home`` directly or inside a nested
    ``config`` object.  Empty values fall back to the standard user-local path.
    """

    config_map = _mapping(config)
    notion_home = config_map.get("notion_home")
    if not notion_home:
        nested = config_map.get("config")
        if isinstance(nested, Mapping):
            notion_home = nested.get("notion_home")
    if not notion_home:
        notion_home = os.environ.get("NOTION_HOME") or _DEFAULT_NOTION_HOME
    return Path(str(notion_home)).expanduser()


def build_notion_env(config: Any = None, extra_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Return a subprocess environment with ``NOTION_HOME`` set."""

    notion_home = resolve_notion_home(config)
    notion_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["NOTION_HOME"] = str(notion_home)
    if extra_env:
        for key, value in extra_env.items():
            if value is not None:
                env[str(key)] = str(value)
    return env


def _timeout_seconds(config: Any, key: str, default: float) -> float:
    config_map = _mapping(config)
    raw = config_map.get(key)
    if raw is None:
        nested = config_map.get("config")
        if isinstance(nested, Mapping):
            raw = nested.get(key)
    try:
        if raw is None:
            return default
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return default


def _parse_login_output(stdout: str, notion_home: Path) -> LoginInitResult:
    url_match = _URL_RE.search(stdout or "")
    code_match = _VERIFICATION_CODE_RE.search(stdout or "")
    if not url_match or not code_match:
        raise NotionAuthError(
            "Failed to parse verification URL/code from `ntn login` output."
        )
    return LoginInitResult(
        verification_url=url_match.group(0).rstrip(").,"),
        verification_code=code_match.group(0).strip(),
        poll_interval_seconds=5,
        notion_home=str(notion_home),
    )


async def _run_ntn_command(
    *args: str,
    config: Any = None,
    timeout_seconds: float,
) -> tuple[int, str, str]:
    env = build_notion_env(config)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ntn",
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on host env
        raise NotionCLIUnavailableError("`ntn` CLI is not installed or not on PATH.") from exc

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except TimeoutError as exc:
        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        raise NotionAuthTimeoutError("Notion CLI command timed out.") from exc

    return proc.returncode or 0, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


async def start_login(config: Any = None) -> LoginInitResult:
    """Run `ntn login --no-browser` and parse the verification payload."""

    notion_home = resolve_notion_home(config)
    code, stdout, stderr = await _run_ntn_command(
        "login",
        "--no-browser",
        config=config,
        timeout_seconds=_timeout_seconds(config, "auth_login_timeout_seconds", _DEFAULT_LOGIN_TIMEOUT_S),
    )
    if code != 0:
        raise NotionAuthError(stderr.strip() or stdout.strip() or "Notion login failed.")
    return _parse_login_output(stdout or stderr, notion_home)


async def poll_login(config: Any = None) -> AuthStatusResult:
    """Run `ntn login poll` and classify the authentication state."""

    notion_home = resolve_notion_home(config)
    code, stdout, stderr = await _run_ntn_command(
        "login",
        "poll",
        config=config,
        timeout_seconds=_timeout_seconds(config, "auth_poll_timeout_seconds", _DEFAULT_POLL_TIMEOUT_S),
    )
    combined = f"{stdout}\n{stderr}".lower()
    if code == 0:
        return AuthStatusResult(status="authenticated", notion_home=str(notion_home))
    if any(token in combined for token in _NO_PENDING_SESSION_TOKENS):
        return AuthStatusResult(
            status="pending",
            notion_home=str(notion_home),
            detail=stdout.strip() or stderr.strip() or "No pending login session found.",
        )
    if "slow_down" in combined or "authorization_pending" in combined or "pending" in combined:
        return AuthStatusResult(status="pending", notion_home=str(notion_home), detail=stdout.strip() or stderr.strip())
    if "expired" in combined or "timeout" in combined:
        return AuthStatusResult(status="expired", notion_home=str(notion_home), detail=stdout.strip() or stderr.strip())
    return AuthStatusResult(status="expired", notion_home=str(notion_home), detail=stdout.strip() or stderr.strip() or "Notion login poll failed.")


async def verify_status(config: Any = None) -> AuthStatusResult:
    """Run `ntn auth status` to verify the current token."""

    notion_home = resolve_notion_home(config)
    code, stdout, stderr = await _run_ntn_command(
        "auth",
        "status",
        config=config,
        timeout_seconds=_timeout_seconds(config, "auth_status_timeout_seconds", _DEFAULT_STATUS_TIMEOUT_S),
    )
    detail = stdout.strip() or stderr.strip()
    if code == 0:
        return AuthStatusResult(status="authenticated", notion_home=str(notion_home), detail=detail)
    if "expired" in detail.lower() or "unauthorized" in detail.lower() or "invalid" in detail.lower():
        return AuthStatusResult(status="expired", notion_home=str(notion_home), detail=detail)
    return AuthStatusResult(status="expired", notion_home=str(notion_home), detail=detail or "Notion auth status check failed.")


def ensure_notion_home(config: Any = None) -> Path:
    """Create the configured Notion home directory and return it."""

    notion_home = resolve_notion_home(config)
    notion_home.mkdir(parents=True, exist_ok=True)
    return notion_home


def normalize_login_result(result: Any) -> dict[str, Any]:
    """Return a serialisable dict for a login or poll result."""

    if isinstance(result, LoginInitResult):
        return {
            "verificationUrl": result.verification_url,
            "verificationCode": result.verification_code,
            "pollIntervalSeconds": result.poll_interval_seconds,
            "notionHome": result.notion_home,
        }
    if isinstance(result, AuthStatusResult):
        payload = {
            "status": result.status,
            "notionHome": result.notion_home,
        }
        if result.detail:
            payload["detail"] = result.detail
        if result.verification_url:
            payload["verificationUrl"] = result.verification_url
        if result.verification_code:
            payload["verificationCode"] = result.verification_code
        return payload
    raise NotionConfigError(f"Unsupported auth result type: {type(result)!r}")


import contextlib  # noqa: E402  # imported late for the timeout cleanup path
