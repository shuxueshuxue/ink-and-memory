# [Input] database.py, reflections_config.py, user sessions, and Reflections prompt config.
# [Output] Persistence-first Reflections-agent task engine, EventBus, Observer, and
#          deterministic section runner for backend async Reflections tasks.
# [Pos] reflections-agent runtime node in backend
# [Sync] 2026-06-25: implement first-release Reflections-agent flow: task/result
#                    persistence, four-phase task engine, in-memory EventBus, and
#                    TaskPersistenceObserver.
#        2026-06-27: keep UTC timestamp generation compatible with the Python 3.10
#                    backend container by using timezone.utc.
"""Backend Reflections-agent runtime.

This module intentionally implements the first-release design only:
- DB-backed ``reflection_task`` / ``reflection_result`` are the truth source.
- A lightweight Task Engine owns the four lifecycle phases.
- In-memory EventBus provides same-process realtime status fan-out.
- Observer is minimal; audio/video consumers are not implemented here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Protocol

import database
from llm_json_parser import try_parse_json_array, try_parse_json_object
from reflections_config import get_section_config, list_sections

logger = logging.getLogger(__name__)

VALID_TASK_STATUSES = {
    "CREATED",
    "ASSEMBLING",
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "PARTIAL_FAILED",
    "FAILED",
}

TERMINAL_TASK_STATUSES = {"COMPLETED", "PARTIAL_FAILED", "FAILED"}


def _utcnow_iso() -> str:
    """Return a compact UTC ISO timestamp with a trailing Z."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class ReflectionTaskEvent:
    """Task-scoped event envelope used by SSE and Observers."""

    id: str
    task_id: str
    type: str
    sequence: int
    created_at: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "type": self.type,
            "sequence": self.sequence,
            "created_at": self.created_at,
            "payload": self.payload,
        }

    def to_sse_frame(self) -> str:
        return (
            f"event: {self.type}\n"
            f"id: {self.id}\n"
            f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"
        )


class ReflectionTaskObserver(Protocol):
    """Observer contract for Reflections task events."""

    async def on_event(self, event: ReflectionTaskEvent) -> None: ...


class TaskPersistenceObserver:
    """Persist task events for audit and replay support."""

    async def on_event(self, event: ReflectionTaskEvent) -> None:
        database.append_reflection_task_event(
            event.task_id,
            event.type,
            event.payload,
            event_id=event.id,
            sequence=event.sequence,
            created_at=event.created_at,
        )


class ReflectionEventBus:
    """Task-scoped in-memory EventBus with replay and fan-out semantics."""

    def __init__(self, task_id: str, observers: list[ReflectionTaskObserver] | None = None) -> None:
        self.task_id = task_id
        self._events: list[ReflectionTaskEvent] = []
        self._subscribers: list[asyncio.Queue[ReflectionTaskEvent | None]] = []
        self._done = False
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._observers = list(observers or [])

    @property
    def is_done(self) -> bool:
        return self._done

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> ReflectionTaskEvent:
        async with self._lock:
            self._sequence += 1
            event = ReflectionTaskEvent(
                id=f"evt_{self._sequence:06d}",
                task_id=self.task_id,
                type=event_type,
                sequence=self._sequence,
                created_at=_utcnow_iso(),
                payload=payload or {},
            )
            self._events.append(event)
            if event_type in {
                "reflection.task.completed",
                "reflection.task.partial_failed",
                "reflection.task.failed",
            }:
                self._done = True
            for queue in list(self._subscribers):
                await queue.put(event)
            if self._done:
                for queue in list(self._subscribers):
                    await queue.put(None)
                self._subscribers.clear()

        for observer in self._observers:
            try:
                await observer.on_event(event)
            except Exception:
                logger.exception("Reflection observer failed for event %s", event.type)
        return event

    async def subscribe(self, after_event_id: str | None = None) -> asyncio.Queue[ReflectionTaskEvent | None]:
        queue: asyncio.Queue[ReflectionTaskEvent | None] = asyncio.Queue()
        async with self._lock:
            replay = self._events
            if after_event_id:
                for index, event in enumerate(self._events):
                    if event.id == after_event_id:
                        replay = self._events[index + 1 :]
                        break
            for event in replay:
                await queue.put(event)
            if self._done:
                await queue.put(None)
            else:
                self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, token: object) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(token)  # type: ignore[arg-type]
            except ValueError:
                pass

    async def read(self, token: object) -> AsyncIterator[ReflectionTaskEvent]:
        queue: asyncio.Queue[ReflectionTaskEvent | None] = token  # type: ignore[assignment]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                continue
            if event is None:
                break
            yield event


_BUSES: dict[str, ReflectionEventBus] = {}
_BUSES_LOCK = asyncio.Lock()
_RUNNING_TASKS: dict[str, asyncio.Task[None]] = {}
_TASK_LOCKS: dict[str, asyncio.Lock] = {}


def _workspace_root() -> Path:
    agent_cwd = os.environ.get("AGENT_CWD", "").strip()
    if agent_cwd:
        return Path(agent_cwd)
    return Path(tempfile.gettempdir()) / "ink-agent-workspaces"


async def get_or_create_reflection_event_bus(task_id: str) -> ReflectionEventBus:
    async with _BUSES_LOCK:
        bus = _BUSES.get(task_id)
        if bus is None:
            bus = ReflectionEventBus(task_id, observers=[TaskPersistenceObserver()])
            _BUSES[task_id] = bus
        return bus


async def get_reflection_event_bus(task_id: str) -> ReflectionEventBus | None:
    async with _BUSES_LOCK:
        return _BUSES.get(task_id)


def _effective_prompt_files(user_id: int, section: str) -> dict[str, str]:
    static_cfg = get_section_config(section)
    static_files: dict[str, str] = static_cfg.get("prompt_files", {})
    user_files = database.get_reflections_section_config(user_id, section)
    if not user_files:
        return dict(static_files)
    merged = dict(static_files)
    for filename, content in user_files.items():
        if isinstance(content, str) and content.strip():
            merged[filename] = content.strip()
    return merged


def _normalize_task_language(language: Any) -> tuple[str, str]:
    code = str(language or "en").strip().lower()
    if code.startswith("zh"):
        return "zh", "Simplified Chinese"
    return "en", "English"


def _language_instruction(language: Any) -> str:
    code, label = _normalize_task_language(language)
    if code == "zh":
        return (
            "\n\n## Runtime Language Requirement\n"
            "The current frontend UI language is Simplified Chinese (`zh`).\n"
            "Write every user-facing `title`, `description`, and `evidence` value in Simplified Chinese.\n"
            "Keep JSON keys and enum values such as `confidence` in English."
        )
    return (
        "\n\n## Runtime Language Requirement\n"
        f"The current frontend UI language is {label} (`en`).\n"
        "Write every user-facing `title`, `description`, and `evidence` value in English.\n"
        "Keep JSON keys and enum values such as `confidence` in English."
    )


def _session_metadata(session: dict[str, Any]) -> dict[str, Any]:
    labels = session.get("labels") if isinstance(session.get("labels"), list) else []
    return {
        "sessionId": str(session.get("id") or ""),
        "date": str(session.get("created_at") or session.get("updated_at") or "")[:10],
        "title": str(session.get("name") or "Untitled")[:120],
        "labels": [str(label) for label in labels if str(label).strip()],
    }


def _build_sessions_context(sessions: list[dict[str, Any]]) -> str:
    metadata = [item for item in (_session_metadata(session) for session in sessions) if item["sessionId"]]
    lines = [
        "Full note bodies are intentionally omitted to keep this request small.",
        "Use only these real session IDs in related_session_ids.",
        "Before writing final insights, fetch needed note content by session ID with mcp__user__get_sessions_range using the listed date and labels, then match the returned sessionId.",
    ]
    lines.extend(json.dumps(item, ensure_ascii=False) for item in metadata)
    return "<sessions_context>\n" + "\n".join(lines) + "\n</sessions_context>"


def _prepare_workspace(task_id: str, user_id: int, sections: list[str], sessions: list[dict[str, Any]], language: str = "en") -> str:
    root = _workspace_root().resolve()
    task_dir = (root / task_id).resolve()
    if not str(task_dir).startswith(str(root)):
        raise ValueError("task workspace resolves outside workspace root")

    memory_dir = task_dir / "memory"
    procedural_dir = memory_dir / "procedural"
    procedural_dir.mkdir(parents=True, exist_ok=True)

    sessions_context = _build_sessions_context(sessions)
    (memory_dir / "sessions_context.md").write_text(sessions_context + "\n", encoding="utf-8")
    (memory_dir / "sessions_context.json").write_text(
        json.dumps([_session_metadata(session) for session in sessions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    language_code, language_label = _normalize_task_language(language)
    (memory_dir / "language_context.md").write_text(
        f"# Runtime Language Context\n\nFrontend UI language: {language_label} (`{language_code}`).\n"
        "All user-facing Reflections output should follow this language unless a section prompt says otherwise.\n",
        encoding="utf-8",
    )

    for section in sections:
        section_dir = memory_dir / section
        section_dir.mkdir(exist_ok=True)
        for filename, content in _effective_prompt_files(user_id, section).items():
            if isinstance(content, str) and content.strip():
                prompt_content = content.strip()
                if filename == "MEMORY_ANSWER_PROMPT.md":
                    prompt_content += _language_instruction(language_code)
                (section_dir / filename).write_text(prompt_content + "\n", encoding="utf-8")

    (procedural_dir / "analysis_state.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "sections": sections,
                "completed_sections": [],
                "failed_sections": [],
                "results_count": 0,
                "language": language_code,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(memory_dir)


def _update_analysis_state(workspace_path: str, **updates: Any) -> None:
    state_path = Path(workspace_path) / "procedural" / "analysis_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except Exception:
        state = {}
    state.update(updates)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class ClaudeAgentReflectionsRunner:
    """Run each Reflections section through the Claude Agent workflow from the PRD."""

    async def run_section(
        self,
        section: str,
        sessions: list[dict[str, Any]],
        language: str = "en",
        *,
        user_id: int,
    ) -> list[dict[str, Any]]:
        thread_id = database.create_chat_thread(user_id)
        memory_path = self._init_memory_workspace(thread_id, user_id, section, language)
        request = _build_claude_agent_run_request(
            user_id=str(user_id),
            thread_id=thread_id,
            resume=False,
            tool_choice="auto",
            max_turns=1000,
            message_id=f"reflections-{section}-{thread_id}",
            message_parts=[{"type": "text", "text": self._build_user_message(sessions)}],
            system_prompt=self._build_system_prompt(section, memory_path),
        )

        async for _frame in _run_claude_agent_stream(request):
            # Step 4 in the PRD requires draining the SSE stream before reading
            # the persisted thread transcript.  Frames are intentionally not
            # interpreted here; the transcript is the source of truth.
            pass

        return self._parse_thread_results(thread_id)

    def _init_memory_workspace(self, thread_id: str, user_id: int, section: str, language: str) -> str | None:
        try:
            memory_dir = self._write_section_memory_workspace(
                thread_id,
                _effective_prompt_files(user_id, section),
                language,
            )
            return str(memory_dir)
        except Exception:
            logger.exception(
                "Reflections memory-init failed for section=%s thread_id=%s; continuing without memory",
                section,
                thread_id,
            )
            return None

    @staticmethod
    def _write_section_memory_workspace(
        thread_id: str,
        prompt_files: dict[str, str],
        language: str,
    ) -> Path:
        workspace_root = _workspace_root().resolve()
        workspace_path = (workspace_root / thread_id).resolve()
        if not str(workspace_path).startswith(str(workspace_root)):
            raise ValueError(f"thread_id resolves outside workspace root: {thread_id!r}")

        memory_dir = workspace_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        language_code = _normalize_task_language(language)[0]
        for filename, content in prompt_files.items():
            if not isinstance(content, str) or not content.strip():
                continue
            prompt_content = content.strip()
            if filename == "MEMORY_ANSWER_PROMPT.md":
                prompt_content += _language_instruction(language_code)
            (memory_dir / filename).write_text(prompt_content + "\n", encoding="utf-8")

        proc_dir = memory_dir / "procedural"
        proc_dir.mkdir(exist_ok=True)
        (proc_dir / "analysis_state.json").write_text(
            json.dumps({"completed": False, "results_count": 0}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return memory_dir

    @staticmethod
    def _build_system_prompt(section: str, memory_path: str | None) -> str:
        section_cfg = get_section_config(section)
        display = section_cfg.get("display_name") or section
        memory_line = (
            f"The procedural memory workspace has been initialised at: {memory_path}"
            if memory_path
            else "No memory workspace was initialised; use the embedded Reflections instructions and session context."
        )
        return (
            f'You are performing a "{display}" analysis for the Ink & Memory Reflections page.\n'
            f"Section key: {section}.\n"
            f"{memory_line}\n"
            "Follow memory/WORKFLOW.md for the analysis procedure when the memory workspace is available.\n"
            "Output ONLY a JSON array as your final response."
        )

    @staticmethod
    def _build_user_message(sessions: list[dict[str, Any]]) -> str:
        return (
            f"{_build_sessions_context(sessions)}\n\n"
            "Your memory workspace contains procedural analysis guidance.\n"
            "Start by reading memory/WORKFLOW.md to understand the analysis procedure.\n"
            "The sessions_context lists only allowed session IDs and labels, not full note bodies. "
            "Fetch the note content you need by session ID before final analysis.\n"
            "Then output ONLY a JSON array — no other text."
        )

    @staticmethod
    def _parse_thread_results(thread_id: str) -> list[dict[str, Any]]:
        messages = database.list_chat_messages(thread_id)
        texts: list[str] = []
        for message in messages:
            if message.get("role") not in {"assistant", "system"}:
                continue
            for part in message.get("parts") or []:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                    texts.append(str(part["text"]))
        for text in reversed(texts):
            parsed = _parse_json_array_from_text(text)
            if parsed is not None:
                return parsed
        return []


def _build_claude_agent_run_request(**kwargs: Any) -> Any:
    try:
        from claude_agent import ClaudeAgentRunRequest

        return ClaudeAgentRunRequest(**kwargs)
    except ModuleNotFoundError:
        return SimpleNamespace(**kwargs)


async def _run_claude_agent_stream(request: Any) -> AsyncIterator[str]:
    from agent_factory import claude_agent_thread_factory

    async for frame in claude_agent_thread_factory.run_streaming(request):
        yield frame


def _parse_json_array_from_text(text: str) -> list[dict[str, Any]] | None:
    _cleaned, value = try_parse_json_array(text)
    if value:
        parsed = [item for item in value if isinstance(item, dict)]
        return parsed or None
    _cleaned, obj = try_parse_json_object(text)
    return [obj] if obj else None


class ReflectionsTaskEngine:
    """Four-phase backend Task Engine for Reflections analysis."""

    def __init__(self, runner: ClaudeAgentReflectionsRunner | None = None) -> None:
        self.runner = runner or ClaudeAgentReflectionsRunner()

    async def run(self, task_id: str) -> None:
        lock = _TASK_LOCKS.setdefault(task_id, asyncio.Lock())
        async with lock:
            bus = await get_or_create_reflection_event_bus(task_id)
            task = database.get_reflection_task(task_id)
            if not task:
                return
            if task.get("status") in TERMINAL_TASK_STATUSES:
                return
            try:
                context = await self._assemble_context(task, bus)
                await self._create_executor(context, bus)
                outcome = await self._execute_task(context, bus)
                await self._finalize_task(context, bus, outcome)
            except Exception as exc:
                logger.exception("Reflections task failed task_id=%s", task_id)
                database.update_reflection_task_status(
                    task_id,
                    "FAILED",
                    error_summary=str(exc),
                    completed_at=_utcnow_iso(),
                )
                await bus.publish(
                    "reflection.task.failed",
                    {"error_code": "TASK_FAILED", "message": str(exc), "retryable": True},
                )
            finally:
                _RUNNING_TASKS.pop(task_id, None)

    async def _assemble_context(self, task: dict[str, Any], bus: ReflectionEventBus) -> dict[str, Any]:
        task_id = task["id"]
        user_id = int(task["user_id"])
        database.update_reflection_task_status(task_id, "ASSEMBLING")
        await bus.publish("reflection.task.created", {"task_id": task_id, "sections": task.get("sections", [])})

        snapshot = task.get("input_snapshot") or {}
        start_date = snapshot.get("start_date")
        end_date = snapshot.get("end_date")
        language = snapshot.get("language") or "en"
        sessions = database.list_sessions_in_range(user_id, start_date, end_date, include_text=True)
        session_ids = snapshot.get("session_ids") or []
        if session_ids:
            allowed = {str(sid) for sid in session_ids}
            sessions = [s for s in sessions if str(s.get("id")) in allowed]

        sections = [s for s in (task.get("sections") or []) if s in set(list_sections())]
        workspace_path = _prepare_workspace(task_id, user_id, sections, sessions, language)
        database.update_reflection_task_status(
            task_id,
            "QUEUED",
            workspace_path=workspace_path,
            input_snapshot={**snapshot, "language": _normalize_task_language(language)[0], "session_count": len(sessions)},
        )
        await bus.publish(
            "reflection.context.ready",
            {"workspace_path": workspace_path, "session_count": len(sessions)},
        )
        return {"task_id": task_id, "user_id": user_id, "sections": sections, "sessions": sessions, "workspace_path": workspace_path, "language": _normalize_task_language(language)[0]}

    async def _create_executor(self, context: dict[str, Any], bus: ReflectionEventBus) -> None:
        database.update_reflection_task_status(
            context["task_id"],
            "RUNNING",
            started_at=_utcnow_iso(),
        )
        await bus.publish("reflection.task.started", {"started_at": _utcnow_iso()})

    async def _execute_task(self, context: dict[str, Any], bus: ReflectionEventBus) -> dict[str, Any]:
        completed: list[str] = []
        failed: list[str] = []
        total_results = 0
        for section in context["sections"]:
            await bus.publish("reflection.section.started", {"section": section})
            try:
                results = await self.runner.run_section(
                    section,
                    context["sessions"],
                    context.get("language", "en"),
                    user_id=context["user_id"],
                )
                validated = self._validate_results(results, section, context["sessions"])
                database.replace_reflection_section_results(
                    context["task_id"], context["user_id"], section, validated
                )
                completed.append(section)
                total_results += len(validated)
                _update_analysis_state(
                    context["workspace_path"],
                    completed_sections=completed,
                    failed_sections=failed,
                    results_count=total_results,
                )
                await bus.publish(
                    "reflection.section.completed",
                    {"section": section, "result_count": len(validated)},
                )
            except Exception as exc:
                failed.append(section)
                _update_analysis_state(
                    context["workspace_path"],
                    completed_sections=completed,
                    failed_sections=failed,
                    last_error=str(exc),
                )
                await bus.publish(
                    "reflection.section.failed",
                    {"section": section, "error_code": "SECTION_FAILED", "message": str(exc), "retryable": True},
                )
        return {"completed_sections": completed, "failed_sections": failed, "total_results": total_results}

    async def _finalize_task(self, context: dict[str, Any], bus: ReflectionEventBus, outcome: dict[str, Any]) -> None:
        completed = outcome["completed_sections"]
        failed = outcome["failed_sections"]
        if completed and failed:
            status = "PARTIAL_FAILED"
            event_type = "reflection.task.partial_failed"
        elif completed:
            status = "COMPLETED"
            event_type = "reflection.task.completed"
        else:
            status = "FAILED"
            event_type = "reflection.task.failed"
        error_summary = None if status == "COMPLETED" else f"Failed sections: {', '.join(failed) or 'all'}"
        database.update_reflection_task_status(
            context["task_id"],
            status,
            error_summary=error_summary,
            completed_at=_utcnow_iso(),
        )
        if completed:
            self._persist_analysis_report(context, completed)
        await bus.publish(
            event_type,
            {
                "completed_sections": completed,
                "failed_sections": failed,
                "result_count": outcome["total_results"],
            },
        )

    @staticmethod
    def _persist_analysis_report(context: dict[str, Any], completed_sections: list[str]) -> None:
        """Mirror completed Reflections task output into the legacy analysis_reports table.

        The frontend historically saved completed Reflections reports through
        POST /api/reports after analysis.  Agent-backed tasks can now finish
        while the page is refreshing or disconnected, so the backend must write
        the same report shape after section results have been persisted.
        """
        task_id = context["task_id"]
        user_id = int(context["user_id"])
        persisted = database.list_reflection_results(task_id, user_id)
        by_section = {
            "echoes": [r for r in persisted if r.get("section") == "echoes"],
            "traits": [r for r in persisted if r.get("section") == "traits"],
            "patterns": [r for r in persisted if r.get("section") == "patterns"],
        }
        if not any(by_section.values()):
            return

        sessions = context.get("sessions") or []
        day_keys = {str(s.get("created_at") or s.get("updated_at") or "")[:10] for s in sessions}
        day_keys.discard("")
        words = sum(len(str(s.get("text") or "").split()) for s in sessions)
        report_data = {
            "echoes": by_section["echoes"],
            "traits": by_section["traits"],
            "patterns": by_section["patterns"],
            "stats": {
                "days": len(day_keys),
                "entries": len(sessions),
                "words": words,
            },
        }
        completed_set = set(completed_sections)
        if completed_set == {"echoes", "traits", "patterns"}:
            report_type = "full_analysis"
        elif len(completed_sections) == 1:
            report_type = f"reflections_{completed_sections[0]}"
        else:
            report_type = "reflections_partial"
        database.save_analysis_report(user_id, report_type, report_data)

    @staticmethod
    def _validate_results(results: list[dict[str, Any]], section: str, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        session_ids = {str(s.get("id")) for s in sessions if s.get("id")}
        validated: list[dict[str, Any]] = []
        for item in results:
            related = [str(sid) for sid in item.get("related_session_ids", []) if str(sid) in session_ids]
            if not related:
                continue
            confidence = item.get("confidence") if item.get("confidence") in {"high", "medium", "low"} else "low"
            validated.append(
                {
                    "section": section,
                    "title": str(item.get("title") or f"{section.title()} Insight")[:200],
                    "description": str(item.get("description") or "")[:4000],
                    "related_session_ids": related,
                    "evidence": str(item.get("evidence") or "")[:2000],
                    "confidence": confidence,
                }
            )
        return validated


async def start_reflections_task(task_id: str) -> None:
    """Start a task in the background if it is not already running."""
    existing = _RUNNING_TASKS.get(task_id)
    if existing and not existing.done():
        return
    await get_or_create_reflection_event_bus(task_id)
    task = asyncio.create_task(ReflectionsTaskEngine().run(task_id))
    _RUNNING_TASKS[task_id] = task


def create_reflections_task(user_id: int, sections: list[str] | None = None, input_snapshot: dict[str, Any] | None = None) -> str:
    valid_sections = set(list_sections())
    normalized = [s for s in (sections or list_sections()) if s in valid_sections]
    if not normalized:
        normalized = list(list_sections())
    return database.create_reflection_task(
        user_id=user_id,
        sections=normalized,
        input_snapshot=input_snapshot or {},
        agent_contract_version="reflections-agent-v1",
    )
