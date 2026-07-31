# [Input] Notion connector auth, operation, store, and sync helpers.
# [Output] Provide a compact facade for routes and Claude Agent workspace attach.
# [Pos] factory node in backend/notion
# [Sync] 2026-07-04: initial Notion connector facade for auth, discovery, selection,
#                    snapshot sync, and workspace materialization.
# [Sync] 2026-07-05: add backend auth-session lifecycle tracking to avoid poll-induced
#                    state regression and maintain frontend-safe auth session state.

"""Connector facade for the Notion resource connector backend."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

from . import auth, operations, store, sync
from .errors import NotionConnectorNotFoundError, NotionSnapshotNotReadyError


_SESSION_TTL_SECONDS = 15 * 60
_SESSION_POLL_IN_FLIGHT_SECONDS = 20
_NO_PENDING_TOKENS = (
    "no pending login session found",
    "authorization session already consumed",
)
_SESSION_VALID_STATUSES = {"running", "pending", "authenticated", "consumed", "expired", "failed"}


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_session(raw: Any) -> dict[str, Any]:
    now = _utcnow_iso()
    session = {
        "auth_session_id": None,
        "auth_session_status": "pending",
        "auth_session_started_at": now,
        "auth_session_last_polled_at": None,
        "auth_session_poll_in_flight": False,
        "auth_session_expires_at": now,
    }
    session.update(_mapping(raw))
    if session["auth_session_status"] not in _SESSION_VALID_STATUSES:
        session["auth_session_status"] = "pending"
    if not session["auth_session_id"]:
        session["auth_session_id"] = None
    if isinstance(session["auth_session_poll_in_flight"], str):
        session["auth_session_poll_in_flight"] = session["auth_session_poll_in_flight"].strip().lower() in {"1", "true", "yes", "on"}
    else:
        session["auth_session_poll_in_flight"] = bool(session["auth_session_poll_in_flight"])
    return session


def _is_no_pending_message(detail: str) -> bool:
    low = (detail or "").lower()
    return any(token in low for token in _NO_PENDING_TOKENS)


def _build_auth_session() -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "auth_session_id": uuid4().hex,
        "auth_session_status": "running",
        "auth_session_started_at": now.isoformat().replace("+00:00", "Z"),
        "auth_session_last_polled_at": None,
        "auth_session_poll_in_flight": False,
        "auth_session_expires_at": (now + timedelta(seconds=_SESSION_TTL_SECONDS)).isoformat().replace("+00:00", "Z"),
    }


def _session_expired(session: Mapping[str, Any]) -> bool:
    expires_at = _parse_iso(session.get("auth_session_expires_at"))
    if expires_at is None:
        return False
    return datetime.now(timezone.utc) >= expires_at


@dataclass
class NotionConnectorFacade:
    """Thin orchestration wrapper for a user-owned Notion connector."""

    user_id: int
    connector_id: Optional[str] = None

    def _resolve_connector(self, connector_id: Optional[str] = None) -> dict[str, Any]:
        resolved = connector_id or self.connector_id
        if resolved:
            connector = store.get_connector(resolved, self.user_id)
            if connector is None:
                raise NotionConnectorNotFoundError(
                    f"Connector {resolved!r} not found for user_id={self.user_id}"
                )
            return connector
        active = store.get_active_connector_for_user(self.user_id)
        if active is None:
            raise NotionConnectorNotFoundError(
                f"No Notion connector found for user_id={self.user_id}"
            )
        self.connector_id = str(active["id"])
        return active

    def _session(self, connector: Mapping[str, Any]) -> dict[str, Any]:
        return _normalize_session(_mapping(connector.get("config")).get("auth_session"))

    def _session_in_flight(self, session: Mapping[str, Any]) -> bool:
        if not session.get("auth_session_poll_in_flight"):
            return False
        last_polled = _parse_iso(session.get("auth_session_last_polled_at"))
        if last_polled is None:
            return False
        return (datetime.now(timezone.utc) - last_polled).total_seconds() < _SESSION_POLL_IN_FLIGHT_SECONDS

    def _persist_auth_state(
        self,
        connector_id: str,
        *,
        auth_status: str,
        session: Mapping[str, Any],
        detail: Optional[str] = None,
        verification_url: Optional[str] = None,
        verification_code: Optional[str] = None,
        poll_interval_seconds: Optional[int] = None,
    ) -> dict[str, Any]:
        config_patch: dict[str, Any] = {
            "auth_session": dict(session),
        }
        if verification_url is not None:
            config_patch["verification_url"] = verification_url
        if verification_code is not None:
            config_patch["verification_code"] = verification_code
        if poll_interval_seconds is not None:
            config_patch["poll_interval_seconds"] = poll_interval_seconds
        if detail is not None:
            config_patch["auth_error"] = detail
        return store.save_auth_state(
            connector_id,
            self.user_id,
            auth_status=auth_status,
            config_patch=config_patch,
            error_detail=detail,
        )

    def create_connector(
        self,
        name: str,
        platform: str = "notion",
        config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return store.create_connector(self.user_id, name=name, platform=platform, config=config)

    def list_connectors(self) -> list[dict[str, Any]]:
        return store.list_connectors(self.user_id)

    def get_connector(self, connector_id: Optional[str] = None) -> dict[str, Any]:
        return self._resolve_connector(connector_id)

    def update_connector(self, updates: Mapping[str, Any], connector_id: Optional[str] = None) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        return store.update_connector(str(connector["id"]), self.user_id, updates)

    def delete_connector(self, connector_id: Optional[str] = None) -> bool:
        connector = self._resolve_connector(connector_id)
        return store.delete_connector(str(connector["id"]), self.user_id)

    async def start_auth(self, connector_id: Optional[str] = None) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        session = _build_auth_session()
        result = await auth.start_login(connector.get("config"))
        session.update(
            {
                "auth_session_status": "pending",
                "auth_session_started_at": _utcnow_iso(),
                "auth_session_last_polled_at": None,
                "auth_session_poll_in_flight": False,
            }
        )
        updated = self._persist_auth_state(
            str(connector["id"]),
            auth_status="pending",
            session=session,
            detail="",
            verification_url=result.verification_url,
            verification_code=result.verification_code,
            poll_interval_seconds=result.poll_interval_seconds,
        )
        return {
            "connector": updated,
            "verificationUrl": result.verification_url,
            "verificationCode": result.verification_code,
            "pollIntervalSeconds": result.poll_interval_seconds,
            "notionHome": result.notion_home,
            "auth_status": "pending",
        }

    async def poll_auth(self, connector_id: Optional[str] = None) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        session = self._session(connector)

        if session.get("auth_session_status") == "authenticated":
            return {
                "connector": connector,
                "auth_status": "authenticated",
                "status": "authenticated",
                "detail": connector.get("config", {}).get("auth_error") or "Session already authenticated.",
                "notionHome": _mapping(connector.get("config")).get("notion_home") or "",
            }

        if _session_expired(session) and str(connector.get("auth_status") or "") != "authenticated":
            session["auth_session_status"] = "expired"
            updated = self._persist_auth_state(
                str(connector["id"]),
                auth_status="expired",
                session=session,
                detail="Auth session expired.",
            )
            return {
                "connector": updated,
                "auth_status": "expired",
                "status": "expired",
                "detail": "Auth session expired.",
                "notionHome": _mapping(connector.get("config")).get("notion_home") or "",
            }

        if self._session_in_flight(session):
            return {
                "connector": connector,
                "auth_status": session.get("auth_session_status") or "pending",
                "status": session.get("auth_session_status") or "pending",
                "detail": "Authorization poll already in progress.",
                "notionHome": _mapping(connector.get("config")).get("notion_home") or "",
            }

        session = dict(session)
        session["auth_session_poll_in_flight"] = True
        session["auth_session_last_polled_at"] = _utcnow_iso()
        saved = self._persist_auth_state(
            str(connector["id"]),
            auth_status=str(connector.get("auth_status") or "pending"),
            session=session,
            detail=_mapping(connector.get("config")).get("auth_error") or "",
        )

        try:
            poll_result = await auth.poll_login(connector.get("config"))
        except Exception as exc:
            session["auth_session_poll_in_flight"] = False
            self._persist_auth_state(
                str(connector["id"]),
                auth_status=str(saved.get("auth_status") or "pending"),
                session=session,
                detail=str(exc),
            )
            raise

        session["auth_session_last_polled_at"] = _utcnow_iso()
        session["auth_session_poll_in_flight"] = False

        detail = poll_result.detail or ""
        auth_status = str(connector.get("auth_status") or "pending").strip().lower() or "pending"
        if poll_result.status == "authenticated":
            auth_status = "authenticated"
            session["auth_session_status"] = "authenticated"
            detail = detail or "authenticated"
            saved = self._persist_auth_state(
                str(connector["id"]),
                auth_status=auth_status,
                session=session,
                detail=detail,
            )
            return {
                "connector": saved,
                "auth_status": auth_status,
                "status": "authenticated",
                "detail": detail,
                "notionHome": poll_result.notion_home,
            }

        if poll_result.status == "pending" and _is_no_pending_message(detail):
            # 已消费/无可用会话时不回退到未认证
            if str(session.get("auth_session_status")) == "authenticated":
                auth_status = "authenticated"
            elif str(saved.get("auth_status") or "") == "authenticated":
                auth_status = "authenticated"
            else:
                session["auth_session_status"] = "consumed"
                auth_status = "error"
            saved = self._persist_auth_state(
                str(connector["id"]),
                auth_status=auth_status,
                session=session,
                detail=detail or "No pending login session found.",
            )
            return {
                "connector": saved,
                "auth_status": auth_status,
                "status": auth_status if auth_status == "authenticated" else "error",
                "detail": detail or "No pending login session found.",
                "notionHome": poll_result.notion_home,
            }

        if poll_result.status == "pending":
            session["auth_session_status"] = session.get("auth_session_status") or "pending"
            if auth_status != "authenticated":
                auth_status = "pending"
            saved = self._persist_auth_state(
                str(connector["id"]),
                auth_status=auth_status,
                session=session,
                detail=detail or "No pending authorization yet.",
            )
            return {
                "connector": saved,
                "auth_status": auth_status,
                "status": poll_result.status,
                "detail": detail or "No pending authorization yet.",
                "notionHome": poll_result.notion_home,
            }

        if poll_result.status == "expired":
            session["auth_session_status"] = "expired"
            auth_status = "expired"
            saved = self._persist_auth_state(
                str(connector["id"]),
                auth_status=auth_status,
                session=session,
                detail=detail or "Auth session expired.",
            )
            return {
                "connector": saved,
                "auth_status": auth_status,
                "status": "expired",
                "detail": detail or "Auth session expired.",
                "notionHome": poll_result.notion_home,
            }

        # fail-open fallback
        session["auth_session_status"] = "failed"
        auth_status = "error"
        saved = self._persist_auth_state(
            str(connector["id"]),
            auth_status=auth_status,
            session=session,
            detail=detail or "Authentication unknown error.",
        )
        return {
            "connector": saved,
            "auth_status": auth_status,
            "status": "error",
            "detail": detail or "Authentication unknown error.",
            "notionHome": poll_result.notion_home,
        }

    async def verify_auth(self, connector_id: Optional[str] = None) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        poll_result = await auth.verify_status(connector.get("config"))
        session = self._session(connector)
        if poll_result.status == "authenticated":
            session["auth_session_status"] = "authenticated"
        updated = self._persist_auth_state(
            str(connector["id"]),
            auth_status=poll_result.status,
            session=session,
            detail=poll_result.detail or "",
            verification_url=poll_result.notion_home,
        )
        return {
            "connector": updated,
            "auth_status": poll_result.status,
            "status": poll_result.status,
            "detail": poll_result.detail,
            "notionHome": poll_result.notion_home,
        }

    async def list_databases(self, connector_id: Optional[str] = None, query: Optional[str] = None) -> list[dict[str, Any]]:
        connector = self._resolve_connector(connector_id)
        selected_ids = {
            str(resource.get("external_id") or "")
            for resource in store.list_connector_resources(str(connector["id"]), self.user_id)
            if resource.get("resource_type") == "notion_database"
        }
        records = await operations.discover_databases(connector.get("config"), query=query)
        for record in records:
            record["selected"] = record.get("database_id") in selected_ids
        return records

    async def list_pages(self, connector_id: Optional[str] = None, query: Optional[str] = None) -> list[dict[str, Any]]:
        connector = self._resolve_connector(connector_id)
        selected_ids = {
            str(resource.get("external_id") or "")
            for resource in store.list_connector_resources(str(connector["id"]), self.user_id)
            if resource.get("resource_type") == "notion_page"
        }
        records = await operations.discover_pages(connector.get("config"), query=query)
        for record in records:
            record["selected"] = record.get("page_id") in selected_ids
        return records

    def list_selected_resources(self, connector_id: Optional[str] = None) -> list[dict[str, Any]]:
        connector = self._resolve_connector(connector_id)
        return store.list_connector_resources(str(connector["id"]), self.user_id)

    async def select_resources(
        self,
        databases: Iterable[Mapping[str, Any]],
        pages: Iterable[Mapping[str, Any]],
        connector_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        store.replace_connector_resources(str(connector["id"]), self.user_id, databases, pages)
        return await self.sync(connector_id=str(connector["id"]), workspace_id=workspace_id)

    async def sync(
        self,
        connector_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        connector = self._resolve_connector(connector_id)
        if str(connector.get("auth_status") or "") != "authenticated":
            raise NotionSnapshotNotReadyError("Connector is not authenticated yet.")

        selected_resources = store.list_connector_resources(str(connector["id"]), self.user_id)
        if not selected_resources:
            raise NotionSnapshotNotReadyError("No selected Notion resources available.")

        ops = operations.NotionOperationClient(connector.get("config"))
        effective_workspace_id = workspace_id or str(connector.get("current_workspace_id") or connector["id"])
        snapshot = await sync.build_canonical_snapshot(
            connector=connector,
            selected_resources=selected_resources,
            workspace_id=effective_workspace_id,
            operations=ops,
        )
        saved_snapshot = store.save_snapshot(
            str(connector["id"]),
            self.user_id,
            effective_workspace_id,
            snapshot,
        )
        return {
            "connector": store.get_connector(str(connector["id"]), self.user_id) or connector,
            "snapshot": saved_snapshot,
            "snapshotIdentity": saved_snapshot.get("identity") if isinstance(saved_snapshot, dict) else None,
            "databaseCount": len(saved_snapshot.get("databases") or []),
            "pageCount": len(saved_snapshot.get("pages") or {}),
            "synced": True,
        }

    def get_current_snapshot(
        self,
        connector_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        connector = self._resolve_connector(connector_id)
        return store.get_current_snapshot(
            workspace_id or str(connector.get("current_workspace_id") or connector["id"]),
            str(connector["id"]),
            self.user_id,
        )

    def materialize_workspace(
        self,
        workspace_path: Path,
        connector_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> None:
        connector = self._resolve_connector(connector_id)
        snapshot = self.get_current_snapshot(connector_id=str(connector["id"]), workspace_id=workspace_id)
        if snapshot is None:
            sync.materialize_workspace_snapshot(workspace_path, connector=connector, snapshot=None)
            return
        sync.materialize_workspace_snapshot(workspace_path, connector=connector, snapshot=snapshot)


def build_notion_facade(user_id: int, connector_id: Optional[str] = None) -> NotionConnectorFacade:
    """Convenience constructor for router/service callers."""

    return NotionConnectorFacade(user_id=user_id, connector_id=connector_id)
