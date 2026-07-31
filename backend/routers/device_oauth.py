#!/usr/bin/env python3
# [Input] Consume auth/database helpers and OAuth Device Flow HTTP requests.
# [Output] Register Device Authorization Grant code, verification, and token routes.
# [Pos] device-oauth route node in backend/routers
# [Sync] 2026-06-23: expose OAuth protocol errors as top-level JSON responses
#                    and anchor Device Flow behavior on Authlib RFC8628 classes.

from datetime import datetime, timedelta
import os
from typing import Optional

from authlib.oauth2.rfc6749.errors import AccessDeniedError
from authlib.oauth2.rfc8628 import (
    AuthorizationPendingError,
    DeviceAuthorizationEndpoint,
    DeviceCodeGrant,
    ExpiredTokenError,
    SlowDownError,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import auth
import database

from .deps import get_current_user
from .oauth import issue_local_token_pair

router = APIRouter()

DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


class OAuthProtocolError(HTTPException):
    """HTTP exception rendered as an OAuth-compatible error response."""

    def __init__(self, error: str, description: str, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={
                "error": error,
                "error_description": description,
            },
        )
        self.error = error
        self.description = description


class InkDeviceCredential:
    """Authlib DeviceCodeGrant credential adapter backed by a SQLite row."""

    def __init__(self, authorization: dict):
        self.authorization = authorization

    def get_client_id(self) -> str:
        return str(self.authorization["client_id"])

    def get_scope(self) -> str:
        return str(self.authorization.get("scope") or "")

    def get_user_code(self) -> str:
        return str(self.authorization["user_code_hash"])

    def is_expired(self) -> bool:
        return database.device_authorization_is_expired(self.authorization)


class InkDeviceAuthorizationEndpoint(DeviceAuthorizationEndpoint):
    """Authlib RFC8628 device authorization endpoint using project storage."""

    def __init__(self, expires_in: int, interval: int):
        super().__init__(server=None)
        self.EXPIRES_IN = expires_in
        self.INTERVAL = interval

    def get_verification_uri(self) -> str:
        return f"{_frontend_url()}/oauth/device/verify"

    def save_device_credential(self, client_id, scope, data):
        database.create_device_authorization(
            client_id=client_id,
            device_code_hash=auth.hash_token(data["device_code"]),
            user_code_hash=auth.hash_token(_normalize_user_code(data["user_code"])),
            scope=scope or "",
            interval_seconds=self.INTERVAL,
            expires_at=datetime.utcnow() + timedelta(seconds=self.EXPIRES_IN),
        )

    def create_device_response(self, client_id: str, scope: str) -> dict:
        for _ in range(5):
            device_code = self.generate_device_code()
            user_code = self.generate_user_code()
            verification_uri = self.get_verification_uri()
            data = {
                "device_code": device_code,
                "user_code": _normalize_user_code(user_code),
                "verification_uri": verification_uri,
                "verification_uri_complete": (
                    f"{verification_uri}?user_code={_normalize_user_code(user_code)}"
                ),
                "expires_in": self.EXPIRES_IN,
                "interval": self.INTERVAL,
            }
            try:
                self.save_device_credential(client_id, scope, data)
                return data
            except Exception:
                continue
        raise RuntimeError("device_code_generation_failed")


class InkDeviceCodeGrant(DeviceCodeGrant):
    """Authlib RFC8628 token-grant adapter for the existing route contract."""

    def __init__(self, authorization: dict):
        self.authorization = authorization

    def query_device_credential(self, device_code):
        return InkDeviceCredential(self.authorization)

    def query_user_grant(self, user_code):
        status = self.authorization["status"]
        if status == "approved":
            user = database.get_user_by_id(int(self.authorization["user_id"]))
            return user, True
        if status == "denied":
            return None, False
        return None

    def should_slow_down(self, credential):
        authorization = credential.authorization
        if database.device_authorization_poll_too_fast(authorization):
            next_interval = int(authorization["interval_seconds"] or 5) + 5
            database.record_device_authorization_poll(
                authorization["id"], interval_seconds=next_interval
            )
            return True
        database.record_device_authorization_poll(authorization["id"])
        return False


class DeviceCodeRequest(BaseModel):
    client_id: str
    scope: Optional[str] = None


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceVerifyRequest(BaseModel):
    user_code: str
    approve: bool = True


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _frontend_url() -> str:
    return os.environ.get("WEBUI_URL", "http://localhost:5173").rstrip("/")


def _allowed_client(client_id: str) -> bool:
    raw = os.environ.get("OAUTH_DEVICE_ALLOWED_CLIENT_IDS", "").strip()
    if not raw:
        return bool(client_id.strip())
    allowed = {item.strip() for item in raw.split(",") if item.strip()}
    return client_id in allowed


def _normalize_user_code(value: str) -> str:
    compact = "".join(ch for ch in value.upper() if ch.isalnum())
    if len(compact) == 8:
        return f"{compact[:4]}-{compact[4:]}"
    return value.strip().upper()


def _oauth_error(error: str, description: str, status_code: int = 400):
    raise OAuthProtocolError(error, description, status_code)


def _expires_in_seconds() -> int:
    return _int_env("DEVICE_CODE_EXPIRES_IN", 600)


def _interval_seconds() -> int:
    return _int_env("DEVICE_CODE_INTERVAL", 5)


@router.post("/oauth/device/code", response_model=DeviceCodeResponse)
def create_device_code(request: DeviceCodeRequest):
    """Create an OAuth Device Authorization request."""

    client_id = request.client_id.strip()
    if not _allowed_client(client_id):
        _oauth_error("invalid_client", "Client is not allowed.", 401)

    expires_in = _expires_in_seconds()
    interval = _interval_seconds()
    endpoint = InkDeviceAuthorizationEndpoint(expires_in=expires_in, interval=interval)
    try:
        return endpoint.create_device_response(client_id, request.scope or "")
    except RuntimeError:
        raise HTTPException(status_code=500, detail="device_code_generation_failed")


@router.get("/oauth/device/verify")
def get_device_verification(user_code: Optional[str] = None):
    """Return verification metadata for a user code."""

    if not user_code:
        return {"user_code_required": True}

    normalized_code = _normalize_user_code(user_code)
    authorization = database.get_device_authorization_by_user_code_hash(
        auth.hash_token(normalized_code)
    )
    if not authorization:
        raise HTTPException(status_code=404, detail="invalid_user_code")
    if database.device_authorization_is_expired(authorization):
        database.update_device_authorization_status(authorization["id"], "expired")
        raise HTTPException(status_code=400, detail="expired_token")

    return {
        "client_id": authorization["client_id"],
        "scope": authorization.get("scope") or "",
        "status": authorization["status"],
        "user_code": normalized_code,
        "expires_at": authorization["expires_at"],
    }


@router.post("/oauth/device/verify")
def verify_device_code(
    request: DeviceVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Approve or deny a Device Flow user code."""

    normalized_code = _normalize_user_code(request.user_code)
    authorization = database.get_device_authorization_by_user_code_hash(
        auth.hash_token(normalized_code)
    )
    if not authorization:
        raise HTTPException(status_code=404, detail="invalid_user_code")
    if database.device_authorization_is_expired(authorization):
        database.update_device_authorization_status(authorization["id"], "expired")
        raise HTTPException(status_code=400, detail="expired_token")
    if authorization["status"] != "pending":
        raise HTTPException(status_code=400, detail="invalid_grant")

    if request.approve:
        database.update_device_authorization_status(
            authorization["id"],
            "approved",
            user_id=current_user["user_id"],
        )
        return {"success": True, "status": "approved"}

    database.update_device_authorization_status(authorization["id"], "denied")
    return {"success": True, "status": "denied"}


async def _token_request_data(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    return dict(form)


def _issue_token_response(user: dict) -> dict:
    access_token, refresh_token = issue_local_token_pair(user["id"], user["email"])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": int(auth.ACCESS_TOKEN_EXPIRE_DELTA.total_seconds()),
    }


def _handle_device_code_grant(data: dict) -> dict:
    device_code = str(data.get("device_code") or "").strip()
    client_id = str(data.get("client_id") or "").strip()
    if not device_code:
        _oauth_error("invalid_grant", "Missing device_code.")
    if not _allowed_client(client_id):
        _oauth_error("invalid_client", "Client is not allowed.", 401)

    authorization = database.get_device_authorization_by_device_code_hash(
        auth.hash_token(device_code)
    )
    if not authorization or authorization["client_id"] != client_id:
        _oauth_error("invalid_grant", "Invalid device_code.")

    status = authorization["status"]
    if status == "consumed":
        _oauth_error("invalid_grant", "Device code has already been consumed.")
    if status not in {"pending", "approved", "denied"}:
        _oauth_error("invalid_grant", "Device code is not valid.")

    credential = InkDeviceCredential(authorization)
    grant = InkDeviceCodeGrant(authorization)
    try:
        user = grant.validate_device_credential(credential)
    except ExpiredTokenError:
        database.update_device_authorization_status(authorization["id"], "expired")
        _oauth_error("expired_token", "Device code has expired.")
    except SlowDownError:
        _oauth_error("slow_down", "Polling too quickly.")
    except AuthorizationPendingError:
        _oauth_error("authorization_pending", "Authorization has not completed yet.")
    except AccessDeniedError:
        _oauth_error("access_denied", "The user denied authorization.")

    if not user:
        _oauth_error("invalid_grant", "Authorized user no longer exists.")

    response = _issue_token_response(user)
    database.update_device_authorization_status(authorization["id"], "consumed")
    return response


def _handle_refresh_token_grant(data: dict) -> dict:
    refresh_token = str(data.get("refresh_token") or "").strip()
    if not refresh_token:
        _oauth_error("invalid_grant", "Missing refresh_token.")

    token_row = database.get_refresh_token(auth.hash_token(refresh_token))
    if not token_row:
        _oauth_error("invalid_grant", "Invalid refresh_token.", 401)

    expires_at = database.parse_sql_datetime(token_row.get("expires_at"))
    if expires_at and expires_at <= datetime.utcnow():
        database.revoke_refresh_token(auth.hash_token(refresh_token))
        _oauth_error("invalid_grant", "Refresh token has expired.", 401)

    user = database.get_user_by_id(int(token_row["user_id"]))
    if not user:
        database.revoke_refresh_token(auth.hash_token(refresh_token))
        _oauth_error("invalid_grant", "Refresh token user does not exist.", 401)

    database.revoke_refresh_token(auth.hash_token(refresh_token))
    return _issue_token_response(user)


@router.post("/oauth/token")
async def oauth_token(request: Request):
    """Token endpoint for Device Code and refresh-token grants."""

    data = await _token_request_data(request)
    grant_type = str(data.get("grant_type") or "").strip()
    if grant_type == DEVICE_CODE_GRANT_TYPE:
        return _handle_device_code_grant(data)
    if grant_type == "refresh_token":
        return _handle_refresh_token_grant(data)
    _oauth_error("unsupported_grant_type", "Grant type is not supported.")
