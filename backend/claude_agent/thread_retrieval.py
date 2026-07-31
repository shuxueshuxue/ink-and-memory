# [Input] Consume chat thread search candidates from database.list_chat_threads_for_search.
# [Output] Provide plugin-style chat history retrievers and retrieval response shaping.
# [Pos] chat-thread-retrieval service node in backend/claude_agent
# [Sync] 2026-06-27: initial plugin boundary for Chat history fuzzy search with
#                    vector_query reserved for future vector-store integration.

"""Configurable retrieval for Claude Agent Chat history.

The Chat page history sidebar searches persisted ``chat_thread`` titles and
``chat_message.parts`` text.  Retrieval defaults to lightweight character fuzzy
matching.  Vector retrieval is intentionally an interface boundary only, aligned
with ``mcp__user__get_sessions_range.vector_query``; no vector database is
called from this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import os
import re
from typing import Any, Protocol


CHAT_HISTORY_RETRIEVAL_MODE_ENV = "INK_AGENT_CHAT_HISTORY_RETRIEVAL_MODE"
CHAT_HISTORY_FUZZY_MIN_SCORE_ENV = "INK_AGENT_CHAT_HISTORY_FUZZY_MIN_SCORE"
CHAT_HISTORY_SEARCH_LIMIT_ENV = "INK_AGENT_CHAT_HISTORY_SEARCH_LIMIT"

DEFAULT_CHAT_HISTORY_RETRIEVAL_MODE = "fuzzy"
DEFAULT_CHAT_HISTORY_FUZZY_MIN_SCORE = 0.35
VALID_CHAT_HISTORY_RETRIEVAL_MODES = frozenset({"fuzzy", "vector", "auto"})
VALID_CHAT_HISTORY_SEARCH_SCOPES = frozenset({"all", "title", "messages"})

_TOKEN_SPLIT_RE = re.compile(r"[\s,，;；|]+")


@dataclass(frozen=True)
class ChatThreadSearchConfig:
    """Normalized search parameters for Chat history retrieval."""

    query: str = ""
    retrieval_mode: str = DEFAULT_CHAT_HISTORY_RETRIEVAL_MODE
    search_scope: str = "all"
    min_score: float = DEFAULT_CHAT_HISTORY_FUZZY_MIN_SCORE
    limit: int | None = None
    vector_query: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatThreadRetrievalOutcome:
    """Structured retrieval result returned to API route callers."""

    ok: bool
    threads: list[dict[str, Any]] = field(default_factory=list)
    retrieval: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    detail: str | None = None


class ChatThreadRetriever(Protocol):
    """Plugin interface for Chat history retrievers."""

    name: str

    def search(
        self,
        candidates: list[dict[str, Any]],
        config: ChatThreadSearchConfig,
    ) -> ChatThreadRetrievalOutcome:
        """Return ranked Chat thread search results."""


class ChatThreadRetrieverRegistry:
    """Registry/factory for Chat history retrieval plugins."""

    def __init__(self) -> None:
        self._retrievers: dict[str, ChatThreadRetriever] = {}

    def register(self, mode: str, retriever: ChatThreadRetriever) -> None:
        normalized = _normalize_text(mode)
        if normalized not in VALID_CHAT_HISTORY_RETRIEVAL_MODES:
            raise ValueError(f"Unsupported chat history retrieval mode: {mode}")
        self._retrievers[normalized] = retriever

    def get(self, mode: str) -> ChatThreadRetriever | None:
        return self._retrievers.get(_normalize_text(mode))


class FuzzyChatThreadRetriever:
    """Character fuzzy matcher over thread title and message text."""

    name = "fuzzy"

    def search(
        self,
        candidates: list[dict[str, Any]],
        config: ChatThreadSearchConfig,
    ) -> ChatThreadRetrievalOutcome:
        query = _normalize_text(config.query)
        ranked: list[tuple[float, int, dict[str, Any]]] = []

        for index, candidate in enumerate(candidates or []):
            score, fields = _score_fuzzy_thread(candidate, query, config.search_scope)
            if query and score < config.min_score:
                continue
            result = _thread_response(candidate, score, fields, query)
            ranked.append((score, index, result))

        if query:
            ranked.sort(key=lambda item: (-item[0], item[1]))

        threads = [item for _score, _index, item in ranked]
        if config.limit is not None:
            threads = threads[: config.limit]

        return ChatThreadRetrievalOutcome(
            ok=True,
            threads=threads,
            retrieval={
                "mode": "fuzzy",
                "query": query,
                "search_scope": config.search_scope,
                "min_score": config.min_score,
                "limit": config.limit,
                "vector": "interface_only",
                "retriever": self.name,
            },
        )


class VectorChatThreadRetriever:
    """Reserved vector retriever plugin boundary.

    This plugin deliberately reports unavailable until a vector store, embedding
    provider, and refresh lifecycle are designed.
    """

    name = "vector"

    def search(
        self,
        candidates: list[dict[str, Any]],
        config: ChatThreadSearchConfig,
    ) -> ChatThreadRetrievalOutcome:
        del candidates
        return ChatThreadRetrievalOutcome(
            ok=False,
            error="vector_retrieval_unavailable",
            detail=(
                "vector_query is reserved for a future chat-history vector-store "
                "integration; no vector store is configured."
            ),
            retrieval={
                "mode": "vector",
                "query": config.query,
                "search_scope": config.search_scope,
                "vector": "interface_only",
                "retriever": self.name,
            },
            warnings=["vector_retrieval_unavailable"],
        )


def build_chat_thread_search_config(
    *,
    query: Any = "",
    retrieval_mode: Any = None,
    search_scope: Any = "all",
    min_score: Any = None,
    limit: Any = None,
    vector_query: dict[str, Any] | None = None,
) -> ChatThreadSearchConfig | None:
    """Normalize raw route parameters into a retrieval config.

    Returns ``None`` when the requested retrieval mode or search scope is
    invalid.  Routes can translate that into a 400 response.
    """

    mode = _normalize_text(
        retrieval_mode
        if retrieval_mode is not None
        else os.getenv(CHAT_HISTORY_RETRIEVAL_MODE_ENV, DEFAULT_CHAT_HISTORY_RETRIEVAL_MODE)
    )
    scope = _normalize_text(search_scope or "all")
    if mode not in VALID_CHAT_HISTORY_RETRIEVAL_MODES:
        return None
    if scope not in VALID_CHAT_HISTORY_SEARCH_SCOPES:
        return None

    return ChatThreadSearchConfig(
        query=_normalize_text(query),
        retrieval_mode=mode,
        search_scope=scope,
        min_score=_coerce_score(min_score),
        limit=_coerce_limit(limit),
        vector_query=vector_query if isinstance(vector_query, dict) else None,
    )


def search_chat_threads(
    candidates: list[dict[str, Any]],
    config: ChatThreadSearchConfig,
    registry: ChatThreadRetrieverRegistry | None = None,
) -> ChatThreadRetrievalOutcome:
    """Run the configured retrieval plugin over Chat thread candidates."""

    if registry is None:
        registry = DEFAULT_CHAT_THREAD_RETRIEVER_REGISTRY

    mode = config.retrieval_mode
    warnings: list[str] = []
    if mode == "auto" and config.vector_query:
        warnings.append("vector_retrieval_unconfigured_falling_back_to_fuzzy")
        mode = "fuzzy"

    retriever = registry.get(mode)
    if retriever is None:
        return ChatThreadRetrievalOutcome(
            ok=False,
            error="invalid_retrieval_mode",
            detail="retrieval_mode must be one of: fuzzy, vector, auto.",
            warnings=warnings,
        )

    outcome = retriever.search(candidates, config)
    if warnings:
        outcome = ChatThreadRetrievalOutcome(
            ok=outcome.ok,
            threads=outcome.threads,
            retrieval={**outcome.retrieval, "mode": mode},
            warnings=[*warnings, *outcome.warnings],
            error=outcome.error,
            detail=outcome.detail,
        )
    return outcome


def is_chat_history_search_requested(
    query: Any = "",
    *,
    retrieval_mode: Any = None,
    vector_query: dict[str, Any] | None = None,
) -> bool:
    """Return whether list-threads should use the retrieval path."""

    return bool(_normalize_text(query) or retrieval_mode or vector_query)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _query_terms(query: str) -> list[str]:
    return [part for part in _TOKEN_SPLIT_RE.split(query) if part]


def _coerce_score(raw: Any) -> float:
    if raw is None:
        raw = os.getenv(
            CHAT_HISTORY_FUZZY_MIN_SCORE_ENV,
            str(DEFAULT_CHAT_HISTORY_FUZZY_MIN_SCORE),
        )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_CHAT_HISTORY_FUZZY_MIN_SCORE
    return min(1.0, max(0.0, value))


def _coerce_limit(raw: Any) -> int | None:
    if raw is None:
        raw = os.getenv(CHAT_HISTORY_SEARCH_LIMIT_ENV, "").strip()
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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


def _score_fuzzy_thread(
    candidate: dict[str, Any],
    query: str,
    search_scope: str,
) -> tuple[float, list[str]]:
    if not query:
        return 0.0, []

    fields_by_scope = {
        "title": {"title": candidate.get("title") or ""},
        "messages": {"messages": candidate.get("messages_text") or ""},
        "all": {
            "title": candidate.get("title") or "",
            "messages": candidate.get("messages_text") or "",
        },
    }
    field_scores = {
        field: _best_char_fuzzy_score(query, value)
        for field, value in fields_by_scope.get(search_scope, fields_by_scope["all"]).items()
    }
    best_score = max(field_scores.values(), default=0.0)
    fields = [
        field
        for field, score in field_scores.items()
        if score == best_score and score > 0
    ]
    return best_score, fields


def _thread_response(
    candidate: dict[str, Any],
    score: float,
    fields: list[str],
    query: str,
) -> dict[str, Any]:
    response = {
        "id": candidate.get("id"),
        "title": candidate.get("title"),
        "created_at": candidate.get("created_at"),
        "updated_at": candidate.get("updated_at"),
    }
    if fields:
        response["match"] = {
            "strategy": "fuzzy",
            "retriever": "fuzzy",
            "score": round(score, 3),
            "fields": fields,
            "excerpt": _match_excerpt(candidate, fields, query),
        }
    return response


def _match_excerpt(candidate: dict[str, Any], fields: list[str], query: str) -> str:
    if "messages" not in fields:
        return ""

    text = str(candidate.get("messages_text") or "").strip()
    if not text:
        return ""
    normalized_text = _normalize_text(text)
    normalized_query = _normalize_text(query)
    index = normalized_text.find(normalized_query) if normalized_query else -1
    if index < 0:
        terms = _query_terms(normalized_query)
        index = next((normalized_text.find(term) for term in terms if normalized_text.find(term) >= 0), -1)
    if index < 0:
        return text[:120].strip()

    start = max(0, index - 40)
    end = min(len(text), index + len(query) + 80)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


DEFAULT_CHAT_THREAD_RETRIEVER_REGISTRY = ChatThreadRetrieverRegistry()
DEFAULT_CHAT_THREAD_RETRIEVER_REGISTRY.register("fuzzy", FuzzyChatThreadRetriever())
DEFAULT_CHAT_THREAD_RETRIEVER_REGISTRY.register("auto", FuzzyChatThreadRetriever())
DEFAULT_CHAT_THREAD_RETRIEVER_REGISTRY.register("vector", VectorChatThreadRetriever())
