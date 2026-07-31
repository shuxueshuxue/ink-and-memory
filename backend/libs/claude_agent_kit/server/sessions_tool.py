# [Input] Reads INK_AGENT_USER_ID from env (injected via mcp_env in AgentRunOptions).
#         Calls database.list_sessions_in_range directly (trusted subprocess context)
#         and applies configured lightweight retrieval strategy parameters.
# [Output] Provide GET_SESSIONS_RANGE_TOOL_SPEC, handle_get_sessions_range for the
#          user MCP server (mcp__user__get_sessions_range).
# [Pos] tool-definition node in libs/claude_agent_kit/server
# [Sync] 2026-05-31: initial implementation — Agent cross-session retrieval tool.
# [Sync] 2026-06-16: add configurable fuzzy retrieval parameters, label matching,
#                    and a vector-query interface boundary without vector DB wiring.

"""MCP tool handler for ``get_sessions_range``.

Allows the Claude Agent to query journal sessions beyond the 3-day window
that is statically injected into the system prompt.  Retrieval defaults to
character-level fuzzy matching when ``query`` is supplied; date-only calls keep
the original range-listing behavior.

The tool runs inside the ``user`` MCP stdio subprocess.  The current user's
``user_id`` is read from the ``INK_AGENT_USER_ID`` environment variable, which
is injected into the MCP subprocess environment by the agent runner.

Session context flows via env var:

    ClaudeAgentService.assemble_context
      → run_options.mcp_env["INK_AGENT_USER_ID"] = str(request.user_id)

    agent_runner._user_mcp_stdio_config(extra_env=mcp_env)
      → McpStdioServerConfig.env["INK_AGENT_USER_ID"] = ...

    sessions_tool.handle_get_sessions_range()
      → os.getenv("INK_AGENT_USER_ID")
      → database.list_sessions_in_range(user_id, start_date, end_date, include_text=...)
"""
from __future__ import annotations

from difflib import SequenceMatcher
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionsToolSpec:
    """Server-owned field bundle for the get_sessions_range tool."""

    description: str
    input_schema: dict[str, Any]


GET_SESSIONS_RANGE_TOOL_NAME = "get_sessions_range"

GET_SESSIONS_RANGE_TOOL_SPEC = SessionsToolSpec(
    description=(
        "按日期范围检索用户的历史日记 session，用于发现三天前的内容。\n"
        "默认使用字符模糊匹配 query 检索 title、labels、excerpt 和正文文本；也可用 labels 过滤。\n"
        "向量检索仅保留 vector_query 接口边界，当前未接入向量库。\n"
        "返回匹配 session 的 id、title、labels、excerpt 和 match 信息，供 Agent 定位相关笔记。\n"
        "仅在用户提到可能早于近期条目的主题或事件时调用此工具。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "查询起始日期（含），格式 YYYY-MM-DD",
            },
            "end_date": {
                "type": "string",
                "description": "查询截止日期（含），格式 YYYY-MM-DD",
            },
            "query": {
                "type": "string",
                "description": "可选自然语言或关键词查询；默认用字符模糊匹配检索标题、标签、摘要和正文。",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选标签过滤。与 query 同时提供时，先按标签过滤，再按 query 排序。",
            },
            "label_match": {
                "type": "string",
                "enum": ["any", "all"],
                "description": "labels 过滤模式；any 表示命中任一标签，all 表示必须全部命中。默认 any。",
            },
            "retrieval_mode": {
                "type": "string",
                "enum": ["fuzzy", "vector", "auto"],
                "description": "检索策略。默认 fuzzy；vector 当前仅声明接口，未配置向量库时返回不可用；auto 在向量不可用时降级 fuzzy。",
            },
            "vector_query": {
                "type": "object",
                "description": "预留向量检索接口，不接入具体向量库。",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "未来用于生成 embedding 的语义查询文本。",
                    },
                    "embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "未来外部调用方可直接传入的查询向量。",
                    },
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "未来向量检索返回候选数量。",
                    },
                },
                "additionalProperties": True,
            },
            "min_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": (
                    "可选模糊匹配最低分，默认读取 INK_AGENT_SESSION_FUZZY_MIN_SCORE，否则 0.2。"
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "可选最大返回条数；未提供时保持日期范围内全部匹配结果。",
            },
        },
        "required": ["start_date", "end_date"],
    },
)


_SESSION_RETRIEVAL_MODE_ENV = "INK_AGENT_SESSION_RETRIEVAL_MODE"
_SESSION_FUZZY_MIN_SCORE_ENV = "INK_AGENT_SESSION_FUZZY_MIN_SCORE"
_DEFAULT_RETRIEVAL_MODE = "fuzzy"
_DEFAULT_FUZZY_MIN_SCORE = 0.2
_VALID_RETRIEVAL_MODES = frozenset({"fuzzy", "vector", "auto"})
_VALID_LABEL_MATCH_MODES = frozenset({"any", "all"})
_TOKEN_SPLIT_RE = re.compile(r"[\s,，;；|]+")


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------


def _json_error(error: str, detail: str | None = None, **extra: Any) -> str:
    payload: dict[str, Any] = {"ok": False, "error": error}
    if detail:
        payload["detail"] = detail
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _normalize_labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        _normalize_text(item)
        for item in value
        if isinstance(item, str) and _normalize_text(item)
    ]


def _query_terms(query: str) -> list[str]:
    return [part for part in _TOKEN_SPLIT_RE.split(query) if part]


def _env_retrieval_mode() -> str:
    raw = os.getenv(_SESSION_RETRIEVAL_MODE_ENV, _DEFAULT_RETRIEVAL_MODE)
    mode = _normalize_text(raw)
    return mode if mode in _VALID_RETRIEVAL_MODES else _DEFAULT_RETRIEVAL_MODE


def _fuzzy_min_score(raw: Any) -> float:
    if raw is None:
        raw = os.getenv(_SESSION_FUZZY_MIN_SCORE_ENV, str(_DEFAULT_FUZZY_MIN_SCORE))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_FUZZY_MIN_SCORE
    return min(1.0, max(0.0, value))


def _parse_limit(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resolve_retrieval_mode(args: dict[str, Any]) -> str | None:
    mode = _normalize_text(args.get("retrieval_mode") or _env_retrieval_mode())
    return mode if mode in _VALID_RETRIEVAL_MODES else None


def _resolve_label_match(args: dict[str, Any]) -> str:
    mode = _normalize_text(args.get("label_match") or "any")
    return mode if mode in _VALID_LABEL_MATCH_MODES else "any"


def _best_char_fuzzy_score(query: str, value: Any) -> float:
    target = _normalize_text(value)
    if not query or not target:
        return 0.0
    if query in target:
        return 1.0

    terms = _query_terms(query)
    if terms:
        hits = sum(1 for term in terms if term and term in target)
        if hits:
            return max(0.6, hits / len(terms))

    return SequenceMatcher(None, query, target).ratio()


def _labels_match(row_labels: list[str], requested_labels: list[str], mode: str) -> bool:
    if not requested_labels:
        return True
    if not row_labels:
        return False

    row_set = set(row_labels)
    if mode == "all":
        return all(label in row_set for label in requested_labels)
    return any(label in row_set for label in requested_labels)


def _score_fuzzy_session(
    row: dict[str, Any],
    query: str,
    requested_labels: list[str],
    label_match: str,
) -> tuple[float, list[str]]:
    row_labels = _normalize_labels(row.get("labels") or [])
    if not _labels_match(row_labels, requested_labels, label_match):
        return 0.0, []

    score = 0.6 if requested_labels and query else 1.0 if requested_labels else 0.0
    fields: list[str] = ["labels"] if requested_labels else []

    if not query:
        return score, fields

    candidates = {
        "name": row.get("name") or "",
        "labels": " ".join(str(label) for label in row.get("labels") or []),
        "excerpt": row.get("first_line") or "",
        "text": row.get("text") or "",
    }
    field_scores = {
        field: _best_char_fuzzy_score(query, value)
        for field, value in candidates.items()
    }
    best_score = max(field_scores.values(), default=0.0)
    matched_fields = [
        field
        for field, field_score in field_scores.items()
        if field_score == best_score and field_score > 0
    ]

    if best_score > score:
        score = best_score
    for field in matched_fields:
        if field not in fields:
            fields.append(field)
    return score, fields


def _session_response(
    row: dict[str, Any], score: float, fields: list[str]
) -> dict[str, Any]:
    raw_date = str(row.get("updated_at") or row.get("created_at") or "")[:10]
    session = {
        "sessionId": row.get("id", ""),
        "name": row.get("name") or "Untitled",
        "labels": row.get("labels") or [],
        "date": raw_date,
        "excerpt": row.get("first_line") or "",
    }
    if fields:
        session["match"] = {
            "strategy": "fuzzy",
            "score": round(score, 3),
            "fields": fields,
        }
    return session


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def handle_get_sessions_range(arguments: dict[str, Any] | None) -> str:
    """Query sessions in [start_date, end_date] for the current user.

    ``user_id`` is read from ``INK_AGENT_USER_ID`` env var (trusted subprocess).
    Returns a JSON string with a ``sessions`` list; each item contains:
    ``sessionId``, ``name``, ``labels``, ``date``, ``excerpt``.
    """
    args = arguments or {}
    start_date: str = str(args.get("start_date") or "").strip()
    end_date: str = str(args.get("end_date") or "").strip()
    query = _normalize_text(args.get("query") or args.get("fuzzy_query") or "")
    requested_labels = _normalize_labels(args.get("labels") or [])
    label_match = _resolve_label_match(args)
    retrieval_mode = _resolve_retrieval_mode(args)
    min_score = _fuzzy_min_score(args.get("min_score"))
    limit = _parse_limit(args.get("limit"))

    if not start_date or not end_date:
        return _json_error(
            "start_date_and_end_date_required",
            "Both start_date and end_date must be provided in YYYY-MM-DD format.",
        )

    if retrieval_mode is None:
        return _json_error(
            "invalid_retrieval_mode",
            "retrieval_mode must be one of: fuzzy, vector, auto.",
        )

    warnings: list[str] = []
    if retrieval_mode == "vector":
        return _json_error(
            "vector_retrieval_unavailable",
            "vector_query is reserved for a future vector-store integration; no vector store is configured.",
            retrieval={"mode": "vector", "interface": "reserved"},
        )
    if retrieval_mode == "auto" and args.get("vector_query"):
        warnings.append("vector_retrieval_unconfigured_falling_back_to_fuzzy")
        retrieval_mode = "fuzzy"

    raw_user_id = os.getenv("INK_AGENT_USER_ID", "").strip()
    if not raw_user_id:
        return _json_error(
            "user_context_unavailable",
            "INK_AGENT_USER_ID is not set in the MCP subprocess environment.",
        )

    try:
        user_id = int(raw_user_id)
    except ValueError:
        return _json_error(
            "invalid_user_id",
            f"INK_AGENT_USER_ID is not a valid integer: {raw_user_id!r}",
        )

    try:
        import database  # noqa: PLC0415 — runtime import, backend only

        rows = database.list_sessions_in_range(
            user_id,
            start_date,
            end_date,
            include_text=bool(query),
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "get_sessions_range: DB query failed; user_id=%s start=%s end=%s",
            user_id,
            start_date,
            end_date,
            exc_info=True,
        )
        return _json_error("db_query_failed")

    ranked: list[tuple[float, int, dict[str, Any]]] = []
    has_filter = bool(query or requested_labels)
    for index, row in enumerate(rows or []):
        score, fields = _score_fuzzy_session(row, query, requested_labels, label_match)
        if has_filter and score < min_score:
            continue
        ranked.append((score, index, _session_response(row, score, fields)))

    if has_filter:
        ranked.sort(key=lambda item: (-item[0], item[1]))

    sessions = [item for _score, _index, item in ranked]
    if limit is not None:
        sessions = sessions[:limit]

    payload: dict[str, Any] = {
        "ok": True,
        "retrieval": {
            "mode": retrieval_mode,
            "query": query,
            "labels": requested_labels,
            "label_match": label_match,
            "min_score": min_score,
            "vector": "interface_only",
        },
        "sessions": sessions,
    }
    if warnings:
        payload["warnings"] = warnings
    return json.dumps(payload, ensure_ascii=False)
