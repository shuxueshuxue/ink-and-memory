# [Input] Notion connector state and snapshot resource helpers.
# [Output] Build canonical snapshots and materialize them into workspace files.
# [Pos] sync node in backend/notion
# [Sync] 2026-07-04: initial canonical snapshot builder + workspace materializer.

"""Canonical Notion snapshot assembly and workspace file materialization."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

from libs.claude_agent_kit.server.notion_snapshot import (
    CanonicalWorkspaceSnapshot,
    SnapshotLifecycleState,
    SnapshotMetadata,
    get_notion_snapshot_resource_data,
)

from .operations import DatabaseQuery, NotionOperationClient, normalize_page_item

NOTION_DIRNAME = ".notion"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _resource_title(resource: Mapping[str, Any]) -> str:
    return str(resource.get("title") or resource.get("name") or resource.get("external_id") or "").strip()


def _build_page_payload(
    page_summary: Mapping[str, Any],
    page_result: Mapping[str, Any],
) -> dict[str, Any]:
    page = _mapping(page_result.get("page"))
    blocks = page_result.get("blocks")
    page_id = str(
        page_summary.get("page_id")
        or page.get("id")
        or page.get("page_id")
        or ""
    ).strip()
    title = _resource_title(page_summary) or str(page.get("title") or page.get("name") or page_id)
    payload = {
        "page_id": page_id,
        "title": title or page_id,
        "url": page.get("url") or page_summary.get("url") or "",
        "last_edited": page_summary.get("last_edited") or page.get("last_edited_time") or "",
        "properties": page.get("properties") or {},
        "blocks": list(blocks or []),
    }
    parent = page.get("parent")
    if isinstance(parent, Mapping):
        payload["parent"] = dict(parent)
    return payload


def _build_index_entry(page_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "page_id": page_payload.get("page_id") or "",
        "title": page_payload.get("title") or "",
        "url": page_payload.get("url") or "",
        "last_edited": page_payload.get("last_edited") or "",
    }


def _build_database_summary(resource: Mapping[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "database_id": str(resource.get("external_id") or ""),
        "title": _resource_title(resource),
        "page_count": len(pages),
        "properties_schema": _mapping(resource.get("metadata")).get("properties_schema") or {},
        "last_edited": _mapping(resource.get("metadata")).get("last_edited") or "",
        "url": _mapping(resource.get("metadata")).get("url") or "",
    }


async def build_canonical_snapshot(
    *,
    connector: Mapping[str, Any],
    selected_resources: Iterable[Mapping[str, Any]],
    workspace_id: str,
    operations: NotionOperationClient,
    page_size: int = 100,
) -> dict[str, Any]:
    """Materialize a canonical snapshot from the selected Notion resources."""

    selected = [dict(item) for item in selected_resources]
    selected_databases = [item for item in selected if item.get("resource_type") == "notion_database"]
    selected_pages = [item for item in selected if item.get("resource_type") == "notion_page"]

    fetched_at = _utcnow_iso()
    index_entries: list[dict[str, Any]] = []
    databases_payload: list[dict[str, Any]] = []
    database_pages_payload: dict[str, list[dict[str, Any]]] = {}
    pages_payload: dict[str, dict[str, Any]] = {}
    source_revisions: list[str] = []
    sync_cursor = ""

    for database_resource in selected_databases:
        database_id = str(database_resource.get("external_id") or "").strip()
        if not database_id:
            continue
        query_result = await operations.query_database(
            DatabaseQuery(database_id=database_id, page_size=page_size)
        )
        page_summaries = [normalize_page_item(item) for item in query_result.results]
        materialized_pages: list[dict[str, Any]] = []
        for page_summary in page_summaries:
            page_id = str(page_summary.get("page_id") or "").strip()
            if not page_id:
                continue
            page_result = await operations.get_page(page_id)
            page_payload = _build_page_payload(page_summary, page_result.data or {})
            pages_payload[page_id] = page_payload
            index_entries.append(_build_index_entry(page_payload))
            materialized_pages.append(
                {
                    "page_id": page_payload["page_id"],
                    "title": page_payload["title"],
                    "last_edited": page_payload["last_edited"],
                    "status": _mapping(page_summary.get("raw")).get("status") or "",
                }
            )
            if page_payload.get("last_edited"):
                source_revisions.append(str(page_payload["last_edited"]))
        database_pages_payload[database_id] = materialized_pages
        databases_payload.append(_build_database_summary(database_resource, materialized_pages))
        if query_result.next_cursor:
            sync_cursor = str(query_result.next_cursor)

    for page_resource in selected_pages:
        page_id = str(page_resource.get("external_id") or "").strip()
        if not page_id:
            continue
        page_result = await operations.get_page(page_id)
        page_summary = normalize_page_item(
            {
                "id": page_id,
                "title": page_resource.get("title"),
                "url": _mapping(page_resource.get("metadata")).get("url") or "",
                "last_edited": _mapping(page_resource.get("metadata")).get("last_edited") or "",
                "parent": _mapping(page_resource.get("metadata")).get("parent") or {},
            }
        )
        page_payload = _build_page_payload(page_summary, page_result.data or {})
        pages_payload[page_id] = page_payload
        index_entries.append(_build_index_entry(page_payload))
        if page_payload.get("last_edited"):
            source_revisions.append(str(page_payload["last_edited"]))

    snapshot_version = f"snap-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    source_revision = max(source_revisions) if source_revisions else snapshot_version
    sync_cursor = sync_cursor or f"cursor-{uuid4().hex[:8]}"

    metadata = SnapshotMetadata(
        workspace_id=workspace_id,
        resource_connector_id=str(connector.get("id") or ""),
        snapshot_version=snapshot_version,
        source_revision=source_revision,
        sync_cursor=sync_cursor,
        fetched_at=fetched_at,
        state=SnapshotLifecycleState.SNAPSHOT_READY,
    )
    CanonicalWorkspaceSnapshot(
        metadata=metadata,
        connector=dict(connector),
        index=index_entries,
        databases=databases_payload,
        database_pages=database_pages_payload,
        pages=pages_payload,
    )
    payload = {
        "metadata": {
            **metadata.__dict__,
            "state": metadata.state.value,
        },
        "connector": dict(connector),
        "index": index_entries,
        "databases": databases_payload,
        "database_pages": database_pages_payload,
        "pages": pages_payload,
    }
    payload["identity"] = {
        "snapshot_version": snapshot_version,
        "source_revision": source_revision,
        "sync_cursor": sync_cursor,
        "workspace_id": workspace_id,
        "resource_connector_id": str(connector.get("id") or ""),
    }
    return payload


def clear_workspace_snapshot(workspace_path: Path) -> None:
    """Remove the workspace-local `.notion/` materialization."""

    notion_dir = workspace_path / NOTION_DIRNAME
    if notion_dir.exists():
        shutil.rmtree(notion_dir, ignore_errors=True)


def materialize_workspace_snapshot(
    workspace_path: Path,
    *,
    connector: Optional[Mapping[str, Any]] = None,
    snapshot: Optional[Mapping[str, Any]] = None,
) -> None:
    """Write the canonical snapshot into workspace-local `.notion/` files."""

    notion_dir = workspace_path / NOTION_DIRNAME
    pages_dir = notion_dir / "pages"
    databases_dir = notion_dir / "databases"
    notion_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)
    databases_dir.mkdir(parents=True, exist_ok=True)

    readme = (
        "# Notion connector snapshot\n\n"
        "This directory is materialized from the connector data layer and is read-only.\n"
        "Agents should treat these files as the source of truth for the attached snapshot.\n"
    )
    (notion_dir / "README.md").write_text(readme, encoding="utf-8")

    snapshot_payload = _mapping(snapshot)
    snapshot_meta = _mapping(snapshot_payload.get("metadata"))
    connector_payload = dict(connector or snapshot_payload.get("connector") or {})

    if snapshot_payload:
        _json_write(notion_dir / "snapshot.json", get_notion_snapshot_resource_data(".notion/snapshot.json", snapshot_payload))
        _json_write(notion_dir / "connector.json", get_notion_snapshot_resource_data(".notion/connector.json", snapshot_payload))
        _json_write(notion_dir / "index.json", get_notion_snapshot_resource_data(".notion/index.json", snapshot_payload))
        _json_write(notion_dir / "databases.json", get_notion_snapshot_resource_data(".notion/databases.json", snapshot_payload))

        keep_database_ids = set()
        for database_item in snapshot_payload.get("databases") or []:
            if not isinstance(database_item, Mapping):
                continue
            database_id = str(database_item.get("database_id") or "").strip()
            if not database_id:
                continue
            keep_database_ids.add(database_id)
            _json_write(
                databases_dir / f"{database_id}.json",
                get_notion_snapshot_resource_data(
                    f".notion/databases/{database_id}.json",
                    snapshot_payload,
                ),
            )

        keep_page_ids = set()
        for page_id in (snapshot_payload.get("pages") or {}).keys():
            page_id = str(page_id).strip()
            if not page_id:
                continue
            keep_page_ids.add(page_id)
            _json_write(
                pages_dir / f"{page_id}.json",
                get_notion_snapshot_resource_data(
                    f".notion/pages/{page_id}.json",
                    snapshot_payload,
                ),
            )

        for stale_path in databases_dir.glob("*.json"):
            if stale_path.stem not in keep_database_ids:
                stale_path.unlink(missing_ok=True)
        for stale_path in pages_dir.glob("*.json"):
            if stale_path.stem not in keep_page_ids:
                stale_path.unlink(missing_ok=True)
        return

    # No snapshot attached yet: keep the connector metadata visible and write
    # empty canonical placeholders so workspace_context can report status.
    _json_write(notion_dir / "snapshot.json", snapshot_meta)
    _json_write(
        notion_dir / "connector.json",
        {
            **connector_payload,
            "snapshot": snapshot_meta,
        },
    )
    _json_write(notion_dir / "index.json", {"pages": [], "snapshot": snapshot_meta})
    _json_write(notion_dir / "databases.json", {"databases": [], "snapshot": snapshot_meta})
    for stale_path in databases_dir.glob("*.json"):
        stale_path.unlink(missing_ok=True)
    for stale_path in pages_dir.glob("*.json"):
        stale_path.unlink(missing_ok=True)
