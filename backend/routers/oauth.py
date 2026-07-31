#!/usr/bin/env python3
# [Input] Consume Authlib Google OIDC config, auth/database helpers, and HTTP requests.
# [Output] Register Google OAuth login/callback routes and issue local system tokens.
# [Pos] google-oauth route node in backend/routers

from datetime import datetime
import os
import secrets
from typing import Optional
from urllib.parse import quote_plus

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import RedirectResponse

import auth
import database

router = APIRouter()

oauth = OAuth()
_google_client_registered = False


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _frontend_url() -> str:
    return os.environ.get("WEBUI_URL", "http://localhost:5173").rstrip("/")


def _api_base_url(request: Request) -> str:
    configured = os.environ.get("API_BASE_URL")
    if configured and configured.strip():
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _cookie_secure() -> bool:
    return _bool_env("COOKIE_SECURE", False)


def _cookie_samesite() -> str:
    value = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def _cookie_max_age_seconds() -> int:
    return int(auth.ACCESS_TOKEN_EXPIRE_DELTA.total_seconds())


def _refresh_cookie_max_age_seconds() -> int:
    return int(auth.REFRESH_TOKEN_EXPIRE_DELTA.total_seconds())


def _redirect_with_error(error: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{_frontend_url()}/?auth_error={quote_plus(error)}",
        status_code=302,
    )


def _safe_return_to(value: Optional[str]) -> str:
    if not value:
        return "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    if "#" in value:
        value = value.split("#", 1)[0]
    return value


def _google_client():
    global _google_client_registered

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured",
        )

    if not _google_client_registered:
        authorize_params = {}
        prompt = os.environ.get("GOOGLE_OAUTH_PROMPT", "select_account").strip()
        if prompt:
            authorize_params["prompt"] = prompt

        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=os.environ.get(
                "GOOGLE_OPENID_CONFIG_URL",
                "https://accounts.google.com/.well-known/openid-configuration",
            ),
            client_kwargs={
                "scope": os.environ.get(
                    "GOOGLE_OAUTH_SCOPE", "openid email profile"
                )
            },
            **({"authorize_params": authorize_params} if authorize_params else {}),
        )
        _google_client_registered = True

    return oauth.create_client("google")


def _allowed_domain(email: str) -> bool:
    raw = os.environ.get("OAUTH_ALLOWED_DOMAINS", "").strip()
    if not raw:
        return True
    allowed = {domain.strip().lower() for domain in raw.split(",") if domain.strip()}
    if "*" in allowed:
        return True
    return email.rsplit("@", 1)[-1].lower() in allowed


def issue_local_token_pair(user_id: int, email: str) -> tuple[str, str]:
    """Create local access/refresh tokens and persist the refresh-token hash."""

    access_token = auth.create_access_token(user_id, email)
    refresh_token, refresh_token_hash, refresh_expires_at = auth.create_refresh_token_value()
    database.create_refresh_token(user_id, refresh_token_hash, refresh_expires_at)
    return access_token, refresh_token


def set_auth_cookies(response: RedirectResponse, access_token: str, refresh_token: str) -> None:
    """Set browser cookies for local system tokens."""

    response.set_cookie(
        "access_token",
        access_token,
        max_age=_cookie_max_age_seconds(),
        secure=_cookie_secure(),
        httponly=True,
        samesite=_cookie_samesite(),
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=_refresh_cookie_max_age_seconds(),
        secure=_cookie_secure(),
        httponly=True,
        samesite=_cookie_samesite(),
        path="/",
    )


def _token_expiry(token: dict) -> Optional[datetime]:
    expires_at = token.get("expires_at")
    if not expires_at:
        return None
    try:
        return datetime.utcfromtimestamp(int(expires_at))
    except Exception:
        return None


async def _userinfo(client, token: dict) -> dict:
    userinfo = token.get("userinfo")
    if not userinfo or "email" not in userinfo or "sub" not in userinfo:
        userinfo = await client.userinfo(token=token)
    return dict(userinfo or {})


def _resolve_oauth_user(userinfo: dict, token: dict) -> dict:
    sub = str(userinfo.get("sub") or "").strip()
    email = str(userinfo.get("email") or "").strip().lower()
    if not sub or not email:
        raise HTTPException(status_code=400, detail="invalid_oauth_userinfo")
    if not _allowed_domain(email):
        raise HTTPException(status_code=403, detail="oauth_domain_not_allowed")

    provider = "google"
    user = database.get_user_by_oauth_account(provider, sub)
    if user:
        database.upsert_oauth_account(
            user["id"],
            provider,
            sub,
            email,
            expires_at=_token_expiry(token),
        )
        return user

    merge_by_email = _bool_env("OAUTH_MERGE_ACCOUNTS_BY_EMAIL", True)
    existing_user = database.get_user_by_email(email)
    if existing_user and merge_by_email:
        database.upsert_oauth_account(
            existing_user["id"],
            provider,
            sub,
            email,
            expires_at=_token_expiry(token),
        )
        return existing_user
    if existing_user and not merge_by_email:
        raise HTTPException(status_code=409, detail="email_already_exists")

    if not _bool_env("ENABLE_OAUTH_SIGNUP", True):
        raise HTTPException(status_code=403, detail="oauth_signup_disabled")

    display_name = (
        str(userinfo.get("name") or "").strip()
        or str(userinfo.get("given_name") or "").strip()
        or email
    )
    avatar_url = str(userinfo.get("picture") or "").strip() or None
    password_hash = auth.hash_password(secrets.token_urlsafe(32))
    user_id = database.create_user(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        avatar_url=avatar_url,
        role="user",
    )
    database.auto_fork_system_decks(user_id)
    database.upsert_oauth_account(
        user_id,
        provider,
        sub,
        email,
        expires_at=_token_expiry(token),
    )
    created = database.get_user_by_id(user_id)
    if not created:
        raise HTTPException(status_code=500, detail="create_user_failed")
    return created


@router.get("/oauth/google/login")
async def google_oauth_login(request: Request):
    """Start Google OAuth login from the Python auth center."""

    client = _google_client()
    request.session["oauth_return_to"] = _safe_return_to(
        request.query_params.get("return_to")
    )
    redirect_uri = f"{_api_base_url(request)}/oauth/google/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/oauth/google/callback")
async def google_oauth_callback(request: Request):
    """Handle Google callback, bind local user, and issue local tokens."""

    try:
        client = _google_client()
        token = await client.authorize_access_token(request)
        userinfo = await _userinfo(client, token)
        user = _resolve_oauth_user(userinfo, token)

        user_decks = database.get_user_decks(user["id"])
        if len(user_decks) == 0:
            database.auto_fork_system_decks(user["id"])

        access_token, refresh_token = issue_local_token_pair(user["id"], user["email"])
    except HTTPException as exc:
        return _redirect_with_error(str(exc.detail))
    except Exception:
        return _redirect_with_error("invalid_oauth_callback")

    return_to = _safe_return_to(request.session.pop("oauth_return_to", "/"))
    redirect_url = (
        f"{_frontend_url()}{return_to}"
        f"#access_token={quote_plus(access_token)}&auth=google"
    )
    response = RedirectResponse(url=redirect_url, status_code=302)
    set_auth_cookies(response, access_token, refresh_token)
    return response
