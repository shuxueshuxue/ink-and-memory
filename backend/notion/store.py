# [Input] Notion connector persistence and canonical snapshot storage.
# [Output] Provide SQLite-backed connector, resource, and snapshot helpers.
# [Pos] store node in backend/notion
# [Sync] 2026-07-04: initial Notion connector persistence layer with selected
#                    resource persistence, snapshot history, and workspace attach
#                    helpers for canonical snapshot materialization.
# [Sync] 2026-07-08: expose selected connector resources on connector rows so
#                    Settings refreshes and Chat linked-resource summaries use
#                    persisted database state instead of optimistic UI state.

"""SQLite-backed persistence for Notion resource connectors."""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

from libs.claude_agent_kit.server.notion_snapshot import (
    CanonicalWorkspaceSnapshot,
    SnapshotLifecycleState,
    SnapshotMetadata,
    get_notion_snapshot_resource_data,
    snapshot_identity,
)

from .errors import NotionConnectorNotFoundError, NotionSnapshotNotReadyError


def _default_db_path() -> Path:
    configured = os.environ.get("INK_AGENT_NOTION_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / "data" / "notion-connectors.db"


DB_PATH = _default_db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        parsed = json.loads(value)
        return parsed if parsed is not None else default
    except Exception:  # noqa: BLE001
        return default


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _snapshot_payload(snapshot: CanonicalWorkspaceSnapshot | dict[str, Any]) -> dict[str, Any]:
    if is_dataclass(snapshot):
        return asdict(snapshot)
    if isinstance(snapshot, dict):
        return dict(snapshot)
    return {}


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    _create_tables(db)
    return db


def _create_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_connectors (
          id TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          platform TEXT NOT NULL,
          auth_status TEXT NOT NULL DEFAULT 'pending',
          config_json TEXT NOT NULL DEFAULT '{}',
          current_snapshot_version TEXT,
          current_source_revision TEXT,
          current_sync_cursor TEXT,
          last_synced_at TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_resource_connectors_user_updated "
        "ON resource_connectors(user_id, updated_at DESC)"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_resources (
          id TEXT PRIMARY KEY,
          connector_id TEXT NOT NULL,
          resource_type TEXT NOT NULL,
          external_id TEXT,
          title TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          sync_status TEXT NOT NULL DEFAULT 'synced',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (connector_id) REFERENCES resource_connectors(id) ON DELETE CASCADE,
          UNIQUE(connector_id, resource_type, external_id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_connector_resources_connector "
        "ON connector_resources(connector_id, resource_type, updated_at DESC)"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_resource_pages (
          id TEXT PRIMARY KEY,
          resource_id TEXT NOT NULL,
          page_id TEXT NOT NULL,
          title TEXT NOT NULL,
          last_edited TEXT,
          properties_json TEXT,
          page_json TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (resource_id) REFERENCES connector_resources(id) ON DELETE CASCADE,
          UNIQUE(resource_id, page_id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_connector_resource_pages_resource "
        "ON connector_resource_pages(resource_id, last_edited DESC)"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_snapshots (
          id TEXT PRIMARY KEY,
          connector_id TEXT NOT NULL,
          snapshot_version TEXT NOT NULL,
          source_revision TEXT NOT NULL,
          sync_cursor TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'snapshot_ready',
          snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (connector_id) REFERENCES resource_connectors(id) ON DELETE CASCADE,
          UNIQUE(connector_id, snapshot_version)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_connector_snapshots_connector "
        "ON connector_snapshots(connector_id, created_at DESC)"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_chat_threads (
          id TEXT PRIMARY KEY,
          connector_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (connector_id) REFERENCES resource_connectors(id) ON DELETE CASCADE,
          UNIQUE(connector_id, thread_id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_connector_chat_threads_connector "
        "ON connector_chat_threads(connector_id, updated_at DESC)"
    )
    db.commit()


def _connector_from_row(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    config = _json_loads(data.get("config_json"), {})
    if not isinstance(config, dict):
        config = {}
    data["config"] = config
    data["selected_databases"] = list(config.get("selected_databases") or [])
    data["selected_pages"] = list(config.get("selected_pages") or [])
    data.pop("config_json", None)
    return data


def _attach_connector_resources(connector: dict[str, Any] | None, user_id: int) -> dict[str, Any] | None:
    if connector is None:
        return None
    connector = dict(connector)
    connector["sources"] = _list_connector_resources_unchecked(str(connector["id"]))
    return connector


def _resource_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = _json_loads(data.get("metadata_json"), {})
    data.pop("metadata_json", None)
    return data


def _snapshot_from_row(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    snapshot = _json_loads(data.get("snapshot_json"), {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    return snapshot


def _require_connector(connector_id: str, user_id: int) -> dict[str, Any]:
    connector = get_connector(connector_id, user_id)
    if connector is None:
        raise NotionConnectorNotFoundError(
            f"Connector {connector_id!r} not found for user_id={user_id}"
        )
    return connector


def create_connector(
    user_id: int,
    name: str,
    platform: str = "notion",
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a connector row and return the persisted record."""

    connector_id = str(uuid4())
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO resource_connectors (
              id, user_id, name, platform, auth_status, config_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                connector_id,
                user_id,
                name.strip() or "Notion Connector",
                platform.strip() or "notion",
                _json_dumps(config or {}),
                _utcnow_iso(),
                _utcnow_iso(),
            ),
        )
        db.commit()
        return get_connector(connector_id, user_id) or {}
    finally:
        db.close()


def list_connectors(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT *
            FROM resource_connectors
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        connectors = []
        for row in rows:
            connector = _connector_from_row(row)
            with_resources = _attach_connector_resources(connector, user_id)
            if with_resources:
                connectors.append(with_resources)
        return connectors
    finally:
        db.close()


def get_connector(connector_id: str, user_id: Optional[int] = None) -> Optional[dict[str, Any]]:
    db = get_db()
    try:
        if user_id is None:
            row = db.execute(
                "SELECT * FROM resource_connectors WHERE id = ? LIMIT 1",
                (connector_id,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM resource_connectors WHERE id = ? AND user_id = ? LIMIT 1",
                (connector_id, user_id),
            ).fetchone()
        connector = _connector_from_row(row)
        if connector is None:
            return None
        if user_id is None:
            user_id = int(connector["user_id"])
        return _attach_connector_resources(connector, int(user_id))
    finally:
        db.close()


def get_active_connector_for_user(user_id: int) -> Optional[dict[str, Any]]:
    """Return the most recently updated connector, preferring authenticated rows."""

    db = get_db()
    try:
        row = db.execute(
            """
            SELECT *
            FROM resource_connectors
            WHERE user_id = ?
            ORDER BY
              CASE auth_status
                WHEN 'authenticated' THEN 0
                WHEN 'pending' THEN 1
                WHEN 'expired' THEN 2
                ELSE 3
              END,
              updated_at DESC,
              created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return _connector_from_row(row)
    finally:
        db.close()


def update_connector(
    connector_id: str,
    user_id: int,
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    connector = _require_connector(connector_id, user_id)
    config = dict(connector.get("config") or {})
    assignments: list[str] = []
    params: list[Any] = []

    if "name" in updates and str(updates["name"]).strip():
        assignments.append("name = ?")
        params.append(str(updates["name"]).strip())
    if "platform" in updates and str(updates["platform"]).strip():
        assignments.append("platform = ?")
        params.append(str(updates["platform"]).strip())
    if "auth_status" in updates and str(updates["auth_status"]).strip():
        assignments.append("auth_status = ?")
        params.append(str(updates["auth_status"]).strip())
    if "config" in updates and isinstance(updates["config"], Mapping):
        config.update(dict(updates["config"]))

    if "current_snapshot_version" in updates:
        assignments.append("current_snapshot_version = ?")
        params.append(updates["current_snapshot_version"])
    if "current_source_revision" in updates:
        assignments.append("current_source_revision = ?")
        params.append(updates["current_source_revision"])
    if "current_sync_cursor" in updates:
        assignments.append("current_sync_cursor = ?")
        params.append(updates["current_sync_cursor"])
    if "last_synced_at" in updates:
        assignments.append("last_synced_at = ?")
        params.append(updates["last_synced_at"])

    assignments.append("config_json = ?")
    params.append(_json_dumps(config))
    assignments.append("updated_at = ?")
    params.append(_utcnow_iso())
    params.extend([connector_id, user_id])

    db = get_db()
    try:
        db.execute(
            f"UPDATE resource_connectors SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )
        db.commit()
        return get_connector(connector_id, user_id) or {}
    finally:
        db.close()


def delete_connector(connector_id: str, user_id: int) -> bool:
    db = get_db()
    try:
        cursor = db.execute(
            "DELETE FROM resource_connectors WHERE id = ? AND user_id = ?",
            (connector_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0
    finally:
        db.close()


def save_auth_state(
    connector_id: str,
    user_id: int,
    *,
    auth_status: str,
    config_patch: Optional[Mapping[str, Any]] = None,
    verification_url: Optional[str] = None,
    verification_code: Optional[str] = None,
    poll_interval_seconds: Optional[int] = None,
    error_detail: Optional[str] = None,
) -> dict[str, Any]:
    """Persist auth state and optional login metadata in the connector config."""

    connector = _require_connector(connector_id, user_id)
    config = dict(connector.get("config") or {})
    if config_patch:
        config.update({k: v for k, v in config_patch.items() if v is not None})
    if verification_url is not None:
        config["verification_url"] = verification_url
    if verification_code is not None:
        config["verification_code"] = verification_code
    if poll_interval_seconds is not None:
        config["poll_interval_seconds"] = int(poll_interval_seconds)
    if error_detail is not None:
        config["auth_error"] = error_detail

    db = get_db()
    try:
        db.execute(
            """
            UPDATE resource_connectors
            SET auth_status = ?, config_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (auth_status, _json_dumps(config), _utcnow_iso(), connector_id, user_id),
        )
        db.commit()
        return get_connector(connector_id, user_id) or {}
    finally:
        db.close()


def replace_connector_resources(
    connector_id: str,
    user_id: int,
    databases: Iterable[Mapping[str, Any]],
    pages: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Replace the selected notion_database/notion_page resources."""

    _require_connector(connector_id, user_id)
    selected_databases = [dict(item) for item in databases]
    selected_pages = [dict(item) for item in pages]
    config_patch = {
        "selected_databases": [item.get("database_id") or item.get("id") for item in selected_databases if item.get("database_id") or item.get("id")],
        "selected_pages": [item.get("page_id") or item.get("id") for item in selected_pages if item.get("page_id") or item.get("id")],
    }

    db = get_db()
    try:
        db.execute(
            "DELETE FROM connector_resources WHERE connector_id = ? AND resource_type IN ('notion_database', 'notion_page')",
            (connector_id,),
        )
        now = _utcnow_iso()
        for item in selected_databases:
            external_id = str(item.get("database_id") or item.get("id") or "").strip()
            if not external_id:
                continue
            resource_id = str(uuid4())
            metadata = {
                "page_count": item.get("page_count"),
                "properties_schema": item.get("properties_schema") or {},
                "url": item.get("url") or "",
                "last_edited": item.get("last_edited") or "",
                "raw": item.get("raw") or {},
            }
            db.execute(
                """
                INSERT INTO connector_resources (
                  id, connector_id, resource_type, external_id, title,
                  metadata_json, sync_status, created_at, updated_at
                )
                VALUES (?, ?, 'notion_database', ?, ?, ?, 'synced', ?, ?)
                """,
                (
                    resource_id,
                    connector_id,
                    external_id,
                    str(item.get("title") or external_id),
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )

        for item in selected_pages:
            external_id = str(item.get("page_id") or item.get("id") or "").strip()
            if not external_id:
                continue
            resource_id = str(uuid4())
            metadata = {
                "url": item.get("url") or "",
                "last_edited": item.get("last_edited") or "",
                "parent": item.get("parent") or {},
                "raw": item.get("raw") or {},
            }
            db.execute(
                """
                INSERT INTO connector_resources (
                  id, connector_id, resource_type, external_id, title,
                  metadata_json, sync_status, created_at, updated_at
                )
                VALUES (?, ?, 'notion_page', ?, ?, ?, 'synced', ?, ?)
                """,
                (
                    resource_id,
                    connector_id,
                    external_id,
                    str(item.get("title") or external_id),
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )

        db.execute(
            """
            UPDATE resource_connectors
            SET config_json = ?, auth_status = COALESCE(auth_status, 'pending'), updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                _json_dumps(
                    {
                        **dict(_require_connector(connector_id, user_id).get("config") or {}),
                        **config_patch,
                    }
                ),
                now,
                connector_id,
                user_id,
            ),
        )
        db.commit()
        return {
            "connector": get_connector(connector_id, user_id) or {},
            "resources": list_connector_resources(connector_id, user_id),
        }
    finally:
        db.close()


def _list_connector_resources_unchecked(connector_id: str) -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT *
            FROM connector_resources
            WHERE connector_id = ?
            ORDER BY resource_type, title COLLATE NOCASE, created_at DESC
            """,
            (connector_id,),
        ).fetchall()
        resources = []
        for row in rows:
            item = _resource_from_row(row)
            item["selected"] = True
            resources.append(item)
        return resources
    finally:
        db.close()


def list_connector_resources(connector_id: str, user_id: int) -> list[dict[str, Any]]:
    _require_connector(connector_id, user_id)
    return _list_connector_resources_unchecked(connector_id)


def delete_connector_resource(connector_id: str, user_id: int, resource_id: str) -> bool:
    _require_connector(connector_id, user_id)
    db = get_db()
    try:
        cursor = db.execute(
            "DELETE FROM connector_resources WHERE id = ? AND connector_id = ?",
            (resource_id, connector_id),
        )
        db.commit()
        return cursor.rowcount > 0
    finally:
        db.close()


def save_snapshot(
    connector_id: str,
    user_id: int,
    workspace_id: str,
    snapshot: CanonicalWorkspaceSnapshot | dict[str, Any],
) -> dict[str, Any]:
    """Persist a canonical snapshot and update the connector pointer."""

    connector = _require_connector(connector_id, user_id)
    payload = _snapshot_payload(snapshot)
    metadata = _mapping(payload.get("metadata"))
    if not metadata:
        raise NotionSnapshotNotReadyError("Snapshot metadata is missing.")

    snapshot_version = str(metadata.get("snapshot_version") or "").strip()
    source_revision = str(metadata.get("source_revision") or "").strip()
    sync_cursor = str(metadata.get("sync_cursor") or "").strip()
    fetched_at = str(metadata.get("fetched_at") or "").strip() or _utcnow_iso()
    if not snapshot_version:
        raise NotionSnapshotNotReadyError("Snapshot version is missing.")

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO connector_snapshots (
              id, connector_id, snapshot_version, source_revision, sync_cursor,
              fetched_at, state, snapshot_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connector_id, snapshot_version) DO UPDATE SET
              source_revision = excluded.source_revision,
              sync_cursor = excluded.sync_cursor,
              fetched_at = excluded.fetched_at,
              state = excluded.state,
              snapshot_json = excluded.snapshot_json,
              updated_at = excluded.updated_at
            """,
            (
                str(uuid4()),
                connector_id,
                snapshot_version,
                source_revision,
                sync_cursor,
                fetched_at,
                str(metadata.get("state") or SnapshotLifecycleState.SNAPSHOT_READY.value),
                _json_dumps(payload),
                fetched_at,
                _utcnow_iso(),
            ),
        )

        db.execute(
            """
            UPDATE resource_connectors
            SET current_snapshot_version = ?,
                current_source_revision = ?,
                current_sync_cursor = ?,
                last_synced_at = ?,
                auth_status = 'authenticated',
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                snapshot_version,
                source_revision,
                sync_cursor,
                fetched_at,
                _utcnow_iso(),
                connector_id,
                user_id,
            ),
        )

        # Update the selected resource page materialization for database rows.
        database_pages = _mapping(payload.get("database_pages"))
        for database_id, pages in database_pages.items():
            if not isinstance(pages, list):
                continue
            resource_row = db.execute(
                """
                SELECT id
                FROM connector_resources
                WHERE connector_id = ? AND resource_type = 'notion_database' AND external_id = ?
                LIMIT 1
                """,
                (connector_id, str(database_id)),
            ).fetchone()
            if resource_row is None:
                continue
            resource_id = str(resource_row["id"])
            db.execute(
                "DELETE FROM connector_resource_pages WHERE resource_id = ?",
                (resource_id,),
            )
            for page in pages:
                if not isinstance(page, Mapping):
                    continue
                page_map = dict(page)
                page_id = str(page_map.get("page_id") or page_map.get("id") or "").strip()
                if not page_id:
                    continue
                db.execute(
                    """
                    INSERT INTO connector_resource_pages (
                      id, resource_id, page_id, title, last_edited,
                      properties_json, page_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        resource_id,
                        page_id,
                        str(page_map.get("title") or page_id),
                        str(page_map.get("last_edited") or ""),
                        _json_dumps(page_map.get("properties") or {}),
                        _json_dumps(page_map),
                        fetched_at,
                        _utcnow_iso(),
                    ),
                )

        db.commit()
        return get_current_snapshot(workspace_id, connector_id, user_id) or payload
    finally:
        db.close()


def get_current_snapshot(
    workspace_id: str,
    connector_id: str,
    user_id: int,
) -> Optional[dict[str, Any]]:
    """Return the current canonical snapshot for a connector and workspace."""

    connector = get_connector(connector_id, user_id)
    if connector is None:
        return None
    current_version = connector.get("current_snapshot_version") or ""
    if not current_version:
        return None
    snapshot = get_snapshot(connector_id, current_version, user_id)
    if not snapshot:
        return None
    return snapshot


def get_snapshot(
    connector_id: str,
    snapshot_version: str,
    user_id: int,
) -> Optional[dict[str, Any]]:
    connector = _require_connector(connector_id, user_id)
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT *
            FROM connector_snapshots
            WHERE connector_id = ? AND snapshot_version = ?
            LIMIT 1
            """,
            (connector_id, snapshot_version),
        ).fetchone()
        snapshot = _snapshot_from_row(row)
        if snapshot is None:
            return None
        return snapshot
    finally:
        db.close()


def list_snapshots(connector_id: str, user_id: int) -> list[dict[str, Any]]:
    _require_connector(connector_id, user_id)
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT *
            FROM connector_snapshots
            WHERE connector_id = ?
            ORDER BY created_at DESC
            """,
            (connector_id,),
        ).fetchall()
        snapshots = []
        for row in rows:
            item = dict(row)
            item["snapshot"] = _snapshot_from_row(row)
            item.pop("snapshot_json", None)
            snapshots.append(item)
        return snapshots
    finally:
        db.close()


def attach_thread_to_connector(connector_id: str, user_id: int, thread_id: str) -> dict[str, Any]:
    """Associate a chat thread with a connector for later workspace attach."""

    _require_connector(connector_id, user_id)
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO connector_chat_threads (id, connector_id, thread_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(connector_id, thread_id) DO UPDATE SET
              updated_at = excluded.updated_at
            """,
            (str(uuid4()), connector_id, thread_id, _utcnow_iso(), _utcnow_iso()),
        )
        db.commit()
        return get_connector(connector_id, user_id) or {}
    finally:
        db.close()


def get_connector_for_thread(thread_id: str, user_id: int) -> Optional[dict[str, Any]]:
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT c.*
            FROM connector_chat_threads t
            JOIN resource_connectors c ON c.id = t.connector_id
            WHERE t.thread_id = ? AND c.user_id = ?
            ORDER BY t.updated_at DESC
            LIMIT 1
            """,
            (thread_id, user_id),
        ).fetchone()
        return _connector_from_row(row)
    finally:
        db.close()
