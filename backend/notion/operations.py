# [Input] Notion connector auth env and read-only ntn API endpoints.
# [Output] Provide searchable resource discovery and page/database read helpers.
# [Pos] operations node in backend/notion
# [Sync] 2026-07-04: initial Notion CLI read-only operation layer for discovery,
#                    page retrieval, and database query support.
# [Sync] 2026-07-05: normalize database search filter value to `data_source` to match
#                    Notion API schema while preserving high-level `database` input.
# [Sync] 2026-07-08: filter Notion workspace People system data sources from user-selectable
#                    resource discovery results.

"""Notion read-only operations via the `ntn` CLI."""
from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .auth import build_notion_env
from .errors import NotionCLIUnavailableError, NotionOperationError


@dataclass(frozen=True)
class SearchFilter:
    """Search filter for Notion resource discovery."""

    object_type: Optional[str] = None
    query: Optional[str] = None
    page_size: int = 100
    start_cursor: Optional[str] = None


_SEARCH_FILTER_OBJECT_MAP = {
    "database": "data_source",
}


@dataclass(frozen=True)
class SearchResult:
    """Raw search result wrapper."""

    results: list[dict[str, Any]]
    has_more: bool
    next_cursor: Optional[str]


@dataclass(frozen=True)
class DatabaseQuery:
    """Database query payload."""

    database_id: str
    filter: Optional[dict[str, Any]] = None
    sorts: Optional[list[dict[str, Any]]] = None
    page_size: int = 100
    start_cursor: Optional[str] = None


@dataclass(frozen=True)
class OperationResult:
    """Generic operation response."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _extract_title(item: Mapping[str, Any]) -> str:
    title = item.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    if isinstance(title, list):
        texts = []
        for part in title:
            if isinstance(part, Mapping):
                text = part.get("plain_text") or part.get("text") or ""
                if text:
                    texts.append(str(text))
        combined = "".join(texts).strip()
        if combined:
            return combined

    properties = item.get("properties")
    if isinstance(properties, Mapping):
        for value in properties.values():
            if not isinstance(value, Mapping):
                continue
            nested_title = value.get("title")
            if isinstance(nested_title, list):
                texts = []
                for part in nested_title:
                    if isinstance(part, Mapping):
                        text = part.get("plain_text") or part.get("text") or ""
                        if text:
                            texts.append(str(text))
                combined = "".join(texts).strip()
                if combined:
                    return combined
            if isinstance(value.get("name"), str) and value.get("name").strip():
                return str(value.get("name")).strip()

    for key in ("name", "text", "page_title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return str(item.get("id") or item.get("database_id") or item.get("page_id") or "Untitled")


def _extract_id(item: Mapping[str, Any], kind: str) -> str:
    for key in ("id", f"{kind}_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_last_edited(item: Mapping[str, Any]) -> str:
    for key in ("last_edited_time", "last_edited", "updated_at", "edited_time"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_database_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact database discovery record."""

    raw = _mapping(item)
    properties_schema = raw.get("properties_schema")
    if not isinstance(properties_schema, dict):
        properties_schema = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    return {
        "database_id": _extract_id(raw, "database"),
        "title": _extract_title(raw),
        "url": raw.get("url") or "",
        "page_count": int(raw.get("page_count") or len(raw.get("pages") or []) or 0),
        "properties_schema": properties_schema or {},
        "last_edited": _extract_last_edited(raw),
        "raw": raw,
    }


def _is_people_system_database(item: Mapping[str, Any]) -> bool:
    raw = _mapping(item)
    title = _extract_title(raw).strip().lower()
    properties = raw.get("properties")
    if not isinstance(properties, Mapping):
        properties = raw.get("properties_schema")
    if not isinstance(properties, Mapping):
        return False

    person_field = False
    membership_field = False
    people_property_ids = 0
    for prop in properties.values():
        if not isinstance(prop, Mapping):
            continue
        prop_id = str(prop.get("id") or "").lower()
        prop_name = str(prop.get("name") or "").strip().lower()
        prop_type = str(prop.get("type") or "").strip().lower()
        if prop_id.startswith("people") or prop_id.startswith("people%3a"):
            people_property_ids += 1
        if prop_name == "person" and prop_type == "people":
            person_field = True
        if prop_name == "membership type" and prop_type == "select":
            select = prop.get("select")
            options = select.get("options") if isinstance(select, Mapping) else []
            option_names = {
                str(option.get("name") or "").strip().lower()
                for option in options
                if isinstance(option, Mapping)
            }
            if {"workspace owner", "membership admin", "member"} & option_names:
                membership_field = True

    return title == "people" and (person_field or membership_field or people_property_ids >= 2)


def normalize_page_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact page discovery record."""

    raw = _mapping(item)
    parent = raw.get("parent") if isinstance(raw.get("parent"), Mapping) else {}
    return {
        "page_id": _extract_id(raw, "page"),
        "title": _extract_title(raw),
        "url": raw.get("url") or "",
        "last_edited": _extract_last_edited(raw),
        "parent": dict(parent) if isinstance(parent, Mapping) else {},
        "raw": raw,
    }


class NotionOperationClient:
    """Read-only Notion CLI client."""

    def __init__(self, config: Any = None) -> None:
        self._config = config

    async def search(self, search_filter: SearchFilter) -> SearchResult:
        payload: dict[str, Any] = {
            "page_size": search_filter.page_size,
        }
        if search_filter.object_type:
            object_type = search_filter.object_type.strip().lower()
            object_value = _SEARCH_FILTER_OBJECT_MAP.get(object_type, object_type)
            payload["filter"] = {
                "property": "object",
                "value": object_value,
            }
        if search_filter.query:
            payload["query"] = search_filter.query
        if search_filter.start_cursor:
            payload["start_cursor"] = search_filter.start_cursor
        response = await self._run_endpoint("v1/search", payload)
        return SearchResult(
            results=list(response.get("results") or []),
            has_more=bool(response.get("has_more")),
            next_cursor=response.get("next_cursor"),
        )

    async def discover_databases(self, query: Optional[str] = None, page_size: int = 100) -> list[dict[str, Any]]:
        result = await self.search(
            SearchFilter(object_type="database", query=query, page_size=page_size)
        )
        return [
            normalize_database_item(item)
            for item in result.results
            if not _is_people_system_database(item)
        ]

    async def discover_pages(self, query: Optional[str] = None, page_size: int = 100) -> list[dict[str, Any]]:
        result = await self.search(
            SearchFilter(object_type="page", query=query, page_size=page_size)
        )
        return [normalize_page_item(item) for item in result.results]

    async def query_database(self, query: DatabaseQuery) -> SearchResult:
        payload: dict[str, Any] = {
            "page_size": query.page_size,
        }
        if query.filter is not None:
            payload["filter"] = query.filter
        if query.sorts is not None:
            payload["sorts"] = query.sorts
        if query.start_cursor:
            payload["start_cursor"] = query.start_cursor
        response = await self._run_endpoint(
            f"v1/databases/{query.database_id}/query",
            payload,
        )
        return SearchResult(
            results=list(response.get("results") or []),
            has_more=bool(response.get("has_more")),
            next_cursor=response.get("next_cursor"),
        )

    async def get_page(self, page_id: str) -> OperationResult:
        page = await self._run_endpoint(f"v1/pages/{page_id}")
        blocks = await self._run_endpoint(f"v1/blocks/{page_id}/children")
        return OperationResult(
            success=True,
            data={
                "page": page,
                "blocks": list(blocks.get("results") or blocks.get("children") or []),
            },
        )

    async def get_blocks(self, block_id: str) -> OperationResult:
        blocks = await self._run_endpoint(f"v1/blocks/{block_id}/children")
        return OperationResult(success=True, data={"blocks": list(blocks.get("results") or [])})

    async def _run_endpoint(self, endpoint: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        env = build_notion_env(self._config)
        args = ["ntn", "api", endpoint]
        if payload is not None:
            args.extend(["--data", json.dumps(payload, ensure_ascii=False)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:  # pragma: no cover - depends on host env
            raise NotionCLIUnavailableError("`ntn` CLI is not installed or not on PATH.") from exc

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_seconds())
        except TimeoutError as exc:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            raise NotionOperationError(f"ntn api {endpoint} timed out.") from exc

        stdout_text = stdout.decode("utf-8", "replace").strip()
        stderr_text = stderr.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise NotionOperationError(stderr_text or stdout_text or f"ntn api {endpoint} failed.")
        if not stdout_text:
            return {}
        try:
            parsed = json.loads(stdout_text)
            return parsed if isinstance(parsed, dict) else {"results": parsed}
        except json.JSONDecodeError as exc:
            raise NotionOperationError(
                f"ntn api {endpoint} returned invalid JSON: {stdout_text[:200]}"
            ) from exc

    def _timeout_seconds(self) -> float:
        config = _mapping(self._config)
        timeout = config.get("operation_timeout_seconds")
        if timeout is None:
            nested = config.get("config")
            if isinstance(nested, Mapping):
                timeout = nested.get("operation_timeout_seconds")
        try:
            return max(1.0, float(timeout)) if timeout is not None else 30.0
        except (TypeError, ValueError):
            return 30.0


async def discover_databases(config: Any = None, query: Optional[str] = None, page_size: int = 100) -> list[dict[str, Any]]:
    """Discover accessible databases with normalized records."""

    return await NotionOperationClient(config).discover_databases(query=query, page_size=page_size)


async def discover_pages(config: Any = None, query: Optional[str] = None, page_size: int = 100) -> list[dict[str, Any]]:
    """Discover accessible standalone pages with normalized records."""

    return await NotionOperationClient(config).discover_pages(query=query, page_size=page_size)
