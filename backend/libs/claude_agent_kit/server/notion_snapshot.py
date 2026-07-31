# [Input] Canonical Notion workspace snapshots materialized by the resource connector data layer.
# [Output] Provide snapshot contract types and .notion/ virtual path resolution helpers.
# [Pos] notion-snapshot-contract node in libs/claude_agent_kit/server
# [Sync] 2026-06-28: initial scheme code for connector-owned canonical Notion snapshots.

"""Canonical Notion snapshot contract helpers.

This module is intentionally a thin contract, not a Notion integration.  The
resource connector data layer owns remote sync, materializes a canonical
snapshot, and passes that immutable snapshot to the agent runtime.  Agent-local
derived context can be built from this data, but it is never the source of
truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Optional


class SnapshotLifecycleState(str, Enum):
    """Lifecycle states for connector-owned canonical snapshots."""

    PENDING_SYNC = "pending_sync"
    SYNCED = "synced"
    SNAPSHOT_READY = "snapshot_ready"
    AGENT_ATTACHED = "agent_attached"
    DERIVED_CONTEXT_READY = "derived_context_ready"
    WRITE_PROPOSED = "write_proposed"
    WRITE_PENDING_REMOTE = "write_pending_remote"
    WRITE_CONFIRMED = "write_confirmed"
    SNAPSHOT_SUPERSEDED = "snapshot_superseded"
    STALE = "stale"
    CONFLICT = "conflict"
    PERMISSION_DENIED = "permission_denied"
    CONNECTOR_UNAVAILABLE = "connector_unavailable"


@dataclass(frozen=True)
class ConnectorSyncCursor:
    """Remote-source cursor identity captured by the connector data layer."""

    resource_connector_id: str
    source_revision: str
    sync_cursor: str
    fetched_at: str


@dataclass(frozen=True)
class SnapshotMetadata:
    """Version metadata that makes snapshots comparable and auditable."""

    workspace_id: str
    resource_connector_id: str
    snapshot_version: str
    source_revision: str
    sync_cursor: str
    fetched_at: str
    state: SnapshotLifecycleState = SnapshotLifecycleState.SNAPSHOT_READY


@dataclass(frozen=True)
class CanonicalWorkspaceSnapshot:
    """Read-only snapshot returned to any agent attaching to the same version."""

    metadata: SnapshotMetadata
    connector: dict[str, Any] = field(default_factory=dict)
    index: list[dict[str, Any]] = field(default_factory=list)
    databases: list[dict[str, Any]] = field(default_factory=list)
    database_pages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    pages: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentDerivedContext:
    """Agent-local view derived from a canonical snapshot."""

    snapshot_version: str
    source_revision: str
    sync_cursor: str
    selected_paths: tuple[str, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class SnapshotWriteProposal:
    """A proposed write against a specific canonical snapshot version."""

    proposal_id: str
    workspace_id: str
    resource_connector_id: str
    base_snapshot_version: str
    base_source_revision: str
    base_sync_cursor: str
    operations: tuple[dict[str, Any], ...] = ()


NOTION_SNAPSHOT_RESOURCES: dict[str, str] = {
    "connector": "__connector__",
    "index": "__index__",
    "databases": "__databases__",
    "snapshot": "__snapshot__",
}

_NOTION_PREFIX = ".notion/"


def is_notion_snapshot_path(path: str) -> bool:
    """Return True when *path* targets a supported .notion/ snapshot resource."""

    return resolve_notion_snapshot_resource(path) is not None


def resolve_notion_snapshot_resource(path: str) -> Optional[str]:
    """Resolve a .notion/ virtual path to a canonical snapshot resource key."""

    if not path:
        return None

    normalised = path.replace("\\", "/")
    idx = normalised.find(_NOTION_PREFIX)
    if idx == -1:
        return None

    remainder = normalised[idx + len(_NOTION_PREFIX):]
    if remainder.startswith("databases/") and remainder.endswith(".json"):
        database_id = remainder[len("databases/"):-len(".json")]
        return f"databases/{database_id}" if database_id else None

    if remainder.startswith("pages/") and remainder.endswith(".json"):
        page_id = remainder[len("pages/"):-len(".json")]
        return f"pages/{page_id}" if page_id else None

    if "/" in remainder:
        return None

    stem = remainder.split(".")[0]
    return stem if stem in NOTION_SNAPSHOT_RESOURCES else None


def get_notion_snapshot_resource_data(
    path: str,
    snapshot: CanonicalWorkspaceSnapshot | dict[str, Any],
) -> Any:
    """Extract data for *path* from a connector-owned canonical snapshot."""

    resource = resolve_notion_snapshot_resource(path)
    if resource is None:
        return {}

    data = _snapshot_dict(snapshot)
    metadata = data.get("metadata") or {}

    if resource == "connector":
        connector = dict(data.get("connector") or {})
        connector["snapshot"] = metadata
        return connector

    if resource == "index":
        return {"pages": data.get("index") or [], "snapshot": metadata}

    if resource == "databases":
        return {"databases": data.get("databases") or [], "snapshot": metadata}

    if resource == "snapshot":
        return metadata

    if resource.startswith("databases/"):
        database_id = resource[len("databases/"):]
        pages = (data.get("database_pages") or {}).get(database_id, [])
        return {"database_id": database_id, "pages": pages, "snapshot": metadata}

    if resource.startswith("pages/"):
        page_id = resource[len("pages/"):]
        page = (data.get("pages") or {}).get(page_id)
        if page is None:
            return {
                "page_id": page_id,
                "missing": True,
                "reason": "not_materialized_in_snapshot",
                "snapshot": metadata,
            }
        return {**page, "snapshot": metadata}

    return {}


def snapshot_identity(snapshot: CanonicalWorkspaceSnapshot | dict[str, Any]) -> dict[str, str]:
    """Return the minimal identity tuple used by agents and write proposals."""

    metadata = (_snapshot_dict(snapshot).get("metadata") or {})
    return {
        "workspace_id": str(metadata.get("workspace_id") or ""),
        "resource_connector_id": str(metadata.get("resource_connector_id") or ""),
        "snapshot_version": str(metadata.get("snapshot_version") or ""),
        "source_revision": str(metadata.get("source_revision") or ""),
        "sync_cursor": str(metadata.get("sync_cursor") or ""),
    }


def write_proposal_is_stale(
    proposal: SnapshotWriteProposal,
    current_snapshot: CanonicalWorkspaceSnapshot | dict[str, Any],
) -> bool:
    """Return True when a write proposal no longer matches the current snapshot."""

    identity = snapshot_identity(current_snapshot)
    return (
        proposal.base_snapshot_version != identity["snapshot_version"]
        or proposal.base_source_revision != identity["source_revision"]
        or proposal.base_sync_cursor != identity["sync_cursor"]
    )


def _snapshot_dict(snapshot: CanonicalWorkspaceSnapshot | dict[str, Any]) -> dict[str, Any]:
    if isinstance(snapshot, dict):
        return snapshot
    if is_dataclass(snapshot):
        return asdict(snapshot)
    return {}
