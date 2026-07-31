# [Input] Notion connector facade, auth, discovery, and snapshot materialization.
# [Output] Register /api/connectors* endpoints for the Notion resource connector.
# [Pos] notion route node in backend/routers
# [Sync] 2026-07-04: initial Notion connector routes for create/auth/discover/
#                    select/sync/resource listing and connector CRUD.

"""Notion resource connector HTTP routes."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from notion import (
    NotionAuthError,
    NotionConnectorError,
    NotionConnectorNotFoundError,
    NotionSnapshotNotReadyError,
    build_notion_facade,
)

from .deps import get_current_user

router = APIRouter()


class ConnectorCreateRequest(BaseModel):
    name: str
    platform: str = "notion"
    config: dict[str, Any] = Field(default_factory=dict)
    notion_home: Optional[str] = None


class ConnectorUpdateRequest(BaseModel):
    name: Optional[str] = None
    platform: Optional[str] = None
    auth_status: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)


class ResourceSelectionRequest(BaseModel):
    selected_databases: list[Any] = Field(default_factory=list)
    selected_pages: list[Any] = Field(default_factory=list)
    workspace_id: Optional[str] = None


class SyncRequest(BaseModel):
    workspace_id: Optional[str] = None


def _user_id(current_user: dict) -> int:
    return int(current_user["user_id"])


def _connector_facade(current_user: dict, connector_id: Optional[str] = None):
    return build_notion_facade(_user_id(current_user), connector_id)


def _coerce_resource_item(item: Any, kind: str) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    identifier_key = "database_id" if kind == "database" else "page_id"
    return {
        identifier_key: str(item),
        "title": str(item),
    }


def _coerce_resource_list(items: Iterable[Any], kind: str) -> list[dict[str, Any]]:
    return [_coerce_resource_item(item, kind) for item in items]


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotionConnectorNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NotionSnapshotNotReadyError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, NotionAuthError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, NotionConnectorError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/api/connectors")
def list_connectors(current_user: dict = Depends(get_current_user)):
    facade = _connector_facade(current_user)
    return {"connectors": facade.list_connectors()}


@router.post("/api/connectors")
def create_connector(
    body: ConnectorCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user)
    config = dict(body.config or {})
    if body.notion_home:
        config["notion_home"] = body.notion_home
    connector = facade.create_connector(
        name=body.name,
        platform=body.platform or "notion",
        config=config,
    )
    return {"connector": connector}


@router.get("/api/connectors/{connector_id}")
def get_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    return {"connector": facade.get_connector(connector_id)}


@router.patch("/api/connectors/{connector_id}")
def update_connector(
    connector_id: str,
    body: ConnectorUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.platform is not None:
        updates["platform"] = body.platform
    if body.auth_status is not None:
        updates["auth_status"] = body.auth_status
    if body.config:
        updates["config"] = body.config
    return {"connector": facade.update_connector(updates, connector_id)}


@router.delete("/api/connectors/{connector_id}")
def delete_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    deleted = facade.delete_connector(connector_id)
    return {"deleted": deleted}


@router.post("/api/connectors/{connector_id}/auth/login")
async def auth_login(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        return await facade.start_auth(connector_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/api/connectors/{connector_id}/auth/poll")
async def auth_poll(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        return await facade.poll_auth(connector_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.get("/api/connectors/{connector_id}/databases")
async def list_databases(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        databases = await facade.list_databases(connector_id)
        return {"connectorId": connector_id, "databases": databases}
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.get("/api/connectors/{connector_id}/pages")
async def list_pages(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        pages = await facade.list_pages(connector_id)
        return {"connectorId": connector_id, "pages": pages}
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.get("/api/connectors/{connector_id}/resources")
def list_resources(
    connector_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        return {"connectorId": connector_id, "resources": facade.list_selected_resources(connector_id)}
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/api/connectors/{connector_id}/resources/select")
async def select_resources(
    connector_id: str,
    body: ResourceSelectionRequest,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        databases = _coerce_resource_list(body.selected_databases, "database")
        pages = _coerce_resource_list(body.selected_pages, "page")
        return await facade.select_resources(
            databases=databases,
            pages=pages,
            connector_id=connector_id,
            workspace_id=body.workspace_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/api/connectors/{connector_id}/sync")
async def sync_connector(
    connector_id: str,
    body: SyncRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        return await facade.sync(connector_id=connector_id, workspace_id=(body.workspace_id if body else None))
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.delete("/api/connectors/{connector_id}/resources/{resource_id}")
def delete_resource(
    connector_id: str,
    resource_id: str,
    current_user: dict = Depends(get_current_user),
):
    facade = _connector_facade(current_user, connector_id)
    try:
        from notion import delete_connector_resource

        deleted = delete_connector_resource(connector_id, _user_id(current_user), resource_id)
        return {"deleted": deleted}
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc

