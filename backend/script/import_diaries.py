#!/usr/bin/env python3
# [Input] Consume Markdown diary/note files plus user/date import options.
# [Output] Upsert diary content as Ink & Memory editor sessions.
# [Pos] backend/script import utility node.
# [Sync] 2026-05-31: created dated diary importer for user_sessions.
# [Sync] 2026-05-31: default import matching now uses file creation time before filename dates.
# [Sync] 2026-05-31: imported text now prefixes the source filename as the first line.
# [Sync] 2026-05-31: same-name folder docs like 临时记事本-5-13/临时记事本-5-13.md resolve dates from the folder/file stem.
# [Sync] 2026-05-31: top-level stems like 思考笔记本-5-17.md resolve dates from the filename stem before creation time.
# [Sync] 2026-05-31: imported sessions default selectedState to ok.
# [Sync] 2026-06-01: imported sessions can infer and persist labels before writing user_sessions.
# [Sync] 2026-06-05: add --label-mode agent: create thread via POST /api/claude-agent/threads then call POST /api/claude-agent; token auto-generated from user DB record via auth.create_access_token; --backend-url / INK_MEMORY_BACKEND_URL / --api-token configure the connection.
# [Sync] 2026-07-19: _agent_infer_labels now reads the final assistant text from
#                    the "message-final" SSE frame instead of a follow-up
#                    GET /api/claude-agent/threads/{id}/messages call, which
#                    could race the backend's async assistant-message
#                    persistence (finish is enqueued before persistence
#                    completes) and intermittently return empty labels.
# [Sync] 2026-07-19: load backend/.env (same as server.py) before importing auth
#                    so the auto-generated --label-mode agent JWT is signed with
#                    the running backend's real JWT_SECRET instead of auth.py's
#                    dev-secret fallback; fixes 401 Unauthorized on
#                    POST /api/claude-agent/threads when the script's shell
#                    doesn't already export JWT_SECRET.
# [Sync] 2026-07-19: --label-mode agent now sends toolChoice "none" (label
#                    inference never needs tools) and enforces a wall-clock
#                    AGENT_LABEL_STREAM_TIMEOUT_S deadline around the SSE read
#                    loop; the previous "auto" value let turns wander into
#                    multi-turn tool use, each frame resetting httpx's per-read
#                    timeout, so a single file's call could hang for many
#                    minutes and require a manual Ctrl-C.
# [Sync] 2026-07-19: restored GET /api/claude-agent/threads/{id}/messages
#                    (_agent_fetch_final_assistant_text) as a retried fallback
#                    in _agent_infer_labels when "message-final".text comes
#                    back empty, instead of dropping the endpoint entirely.
"""
Import Markdown diary/note files into user_sessions.

By default, the importer assigns same-name folder docs from their structured
folder/file stem, assigns other `*-M-D.md` files from the filename stem, then
assigns remaining Markdown files from the local file creation timestamp.
Filename dates remain available through --date-source filename for files named like:
- 日记2026-5-26.md
- 日记-2026-5-26.md

It strips YAML front matter, prefixes the source filename as the first text
line, infers primary labels from front matter, hashtags, paths, and content,
writes a single text-cell editor state through database.save_session(), defaults
the imported session mood to OK, and keeps repeated runs idempotent by deriving
a stable session UUID per user/source file/day.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time as _time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load backend/.env the same way server.py does *before* importing auth, so a
# locally auto-generated JWT (see _build_agent_token) is signed with the same
# JWT_SECRET the running backend process verifies against. Without this, auth
# falls back to its dev-secret default whenever the script's shell doesn't
# already export JWT_SECRET, and every --label-mode agent call fails with
# 401 Unauthorized against a real backend.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

import database  # noqa: E402
import auth as _auth  # noqa: E402

try:
    import httpx as _httpx  # noqa: E402
except ImportError:  # pragma: no cover
    _httpx = None  # type: ignore[assignment]

from tqdm import tqdm  # noqa: E402


DIARY_FILE_RE = re.compile(
    r"^日记-?(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\.md$"
)
STEM_MONTH_DAY_RE = re.compile(r"^.+-(?P<month>\d{1,2})-(?P<day>\d{1,2})$")
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_IMPORT_TIME = "09:00"
DEFAULT_DATE_SOURCE = "created-first"
DEFAULT_SELECTED_STATE = "ok"
DEFAULT_LABEL_MODE = "auto"
DEFAULT_MAX_LABELS = 5
DEFAULT_BACKEND_URL = "http://localhost:8000"
# Wall-clock cap for a single --label-mode agent HTTP call (thread create +
# streamed turn). httpx's per-call timeout only bounds the gap between reads,
# so a turn that keeps streaming frames (e.g. tool-input/tool-event chunks
# from unexpected tool use) never trips it and the script appears to hang.
AGENT_LABEL_STREAM_TIMEOUT_S = 120.0
# Fallback retry policy for GET /api/claude-agent/threads/{id}/messages when
# the "message-final" frame's text comes back empty. The backend enqueues the
# SSE "finish" frame before _persist_assistant_turn() finishes writing the
# assistant message (claude_agent/service.py execute_session), so a single
# immediate GET can still race that write; a couple of short retries absorb it.
AGENT_LABEL_MESSAGES_FALLBACK_ATTEMPTS = 3
AGENT_LABEL_MESSAGES_FALLBACK_DELAY_S = 0.3
DATE_SOURCE_CHOICES = (
    "created-first",
    "folder-name",
    "stem-name",
    "created",
    "modified",
    "filename",
)
LABEL_MODE_CHOICES = ("auto", "agent", "none")
HASHTAG_RE = re.compile(r"(?<!\w)#([\w\u4e00-\u9fff-]{1,24})")
INLINE_LABEL_LIST_RE = re.compile(r"^\[(.*)\]$")

AGENT_LABEL_SYSTEM_PROMPT = (
    "你是日记/笔记内容分类助手。\n"
    "任务：根据用户发来的笔记正文，输出最多 {max_labels} 个最相关的主题标签。\n\n"
    "输出格式（严格遵守）：\n"
    "- 只输出标签列表，每行一个标签\n"
    "- 不要编号、符号、括号或任何修饰\n"
    "- 不要输出分析过程、思考过程或解释\n"
    "- 不要输出除标签以外的任何内容\n"
    "- 直接给出最终标签列表，立即结束"
)

AGENT_LABEL_PROMPT = "{text}"



@dataclass(frozen=True)
class AgentLabelContext:
    """Connection context for calling the Claude Agent service to infer labels."""

    backend_url: str
    token: str
    max_labels: int


@dataclass
class _EntryTask:
    """All inputs needed to process a single diary file into a DiaryEntry."""

    day: date
    created_at_db: str
    created_at_state: str
    resolved_source: str
    path: Path
    user_id: int
    source_dir: Path
    label_mode: str
    max_labels: int
    agent_ctx: AgentLabelContext | None
    existing_session_ids: set[str] | None
    replace: bool
    force_labels: bool


def _process_entry_task(task: _EntryTask) -> DiaryEntry | None:
    """Read one Markdown file, infer labels, and return a DiaryEntry (or None if empty)."""
    raw = task.path.read_text(encoding="utf-8")
    body = strip_yaml_front_matter(raw)
    if not body:
        return None
    text = content_with_filename_first_line(task.path, body)
    session_id = make_session_id(task.user_id, task.source_dir, task.path, task.day)

    already_exists = (
        task.existing_session_ids is not None
        and session_id in task.existing_session_ids
    )
    if already_exists and not task.replace and not task.force_labels:
        labels: list[str] = []
    else:
        labels = infer_labels(
            task.path, raw, body, task.label_mode, task.max_labels, task.agent_ctx
        )
    return DiaryEntry(
        path=task.path,
        day=task.day,
        base_title=title_for_path(task.day, task.path),
        text=text,
        text_hash=normalized_text_hash(text),
        session_id=session_id,
        created_at_db=task.created_at_db,
        created_at_state=task.created_at_state,
        date_source=task.resolved_source,
        labels=labels,
    )


def _build_agent_token(user_id: int) -> str:
    """Generate a short-lived JWT for internal script-to-service calls."""
    db = database.get_db()
    try:
        row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise SystemExit(f"Cannot build agent token: user {user_id} not found.")
        email = row["email"]
    finally:
        db.close()
    return _auth.create_access_token(user_id, email)


def _agent_create_thread(backend_url: str, token: str, title: str | None = None) -> str:
    """POST /api/claude-agent/threads and return the new thread_id.

    If *title* is given, set it immediately via the local database so the
    thread appears with a meaningful name in chat history.
    """
    if _httpx is None:
        raise SystemExit("httpx is required for --label-mode agent (pip install httpx).")
    url = f"{backend_url.rstrip('/')}/api/claude-agent/threads"
    with _httpx.Client(timeout=30) as client:
        resp = client.post(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        thread_id = resp.json()["thread_id"]
    if title:
        database.update_chat_thread_title(thread_id, title)
    return thread_id


def _agent_fetch_final_assistant_text(backend_url: str, token: str, thread_id: str) -> str:
    """GET /api/claude-agent/threads/{id}/messages and return the last
    assistant message's concatenated text parts.

    This is the pre-2026-07-19 primary lookup for the final label text; it is
    kept (not removed) as a fallback for ``_agent_infer_labels`` when the
    "message-final" SSE frame's ``text`` comes back empty, so this endpoint
    stays in active use by the script rather than being dropped entirely.
    """
    base = backend_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    with _httpx.Client(timeout=30) as client:
        resp = client.get(f"{base}/api/claude-agent/threads/{thread_id}/messages", headers=headers)
        resp.raise_for_status()
        messages = resp.json().get("messages", [])
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        parts = message.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        if text:
            return text
    return ""


def _agent_infer_labels(
    text: str,
    backend_url: str,
    token: str,
    max_labels: int,
    thread_title: str | None = None,
) -> list[str]:
    """Send diary text to the Claude Agent service and parse returned label lines.

    Creates a new thread, then streams POST /api/claude-agent and reads the
    final assistant text primarily from the ``message-final`` frame's ``text``
    field. That field is assembled server-side from ``text-delta`` events only
    (thinking/reasoning content is streamed as separate ``tool-event`` frames
    and never mixed in), so it can be used as-is without an extra round trip
    in the common case.

    If ``message-final.text`` comes back empty, falls back to
    ``_agent_fetch_final_assistant_text`` (GET
    /api/claude-agent/threads/{id}/messages), retried a few times
    (``AGENT_LABEL_MESSAGES_FALLBACK_ATTEMPTS`` / ``_DELAY_S``) because the
    backend enqueues the SSE ``finish`` frame before
    ``_persist_assistant_turn()`` finishes writing the assistant message (see
    ``claude_agent/service.py`` ``execute_session``), so an immediate GET can
    still race that write. This keeps the endpoint in active use rather than
    dropping it outright.

    Sends ``toolChoice: "none"`` — label inference is pure text classification
    and never needs tools; the backend fully disables tool exposure in this
    mode (``agent_runner.py``: ``effective_allowed_tools = [] if tool_choice ==
    "none" else allowed_tools``). With the previous ``"auto"`` value, the model
    could wander into multi-turn tool use (filesystem/bash exploration) on an
    unrelated ``cwd``, and each such tool-event frame resets httpx's per-read
    timeout, so a single file's call could run for many minutes instead of
    erroring out. A wall-clock deadline (``AGENT_LABEL_STREAM_TIMEOUT_S``) is
    enforced on top of that as a second line of defense.
    """
    if _httpx is None:
        raise SystemExit("httpx is required for --label-mode agent (pip install httpx).")

    base = backend_url.rstrip("/")
    thread_id = _agent_create_thread(backend_url, token, title=thread_title)
    system_prompt = AGENT_LABEL_SYSTEM_PROMPT.format(max_labels=max_labels)
    message = AGENT_LABEL_PROMPT.format(text=text)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    msg_id = uuid.uuid4().hex[:12]
    payload = {
        "id": thread_id,
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": message}],
            "id": msg_id,
        },
        "toolChoice": "none",
        "attachments": [],
        "system_prompt": system_prompt,
    }

    assistant_text = ""
    deadline = _time.monotonic() + AGENT_LABEL_STREAM_TIMEOUT_S
    with _httpx.Client(timeout=AGENT_LABEL_STREAM_TIMEOUT_S) as client:
        with client.stream("POST", f"{base}/api/claude-agent", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if _time.monotonic() > deadline:
                    raise TimeoutError(
                        f"No finish/error frame from thread {thread_id} within "
                        f"{AGENT_LABEL_STREAM_TIMEOUT_S:.0f}s"
                    )
                if not raw_line.startswith("data: "):
                    continue
                try:
                    frame = json.loads(raw_line[len("data: "):])
                except json.JSONDecodeError:
                    continue
                frame_type = frame.get("type")
                if frame_type == "message-final":
                    assistant_text = frame.get("text", "")
                elif frame_type in ("finish", "error"):
                    break

    if not assistant_text.strip():
        for attempt in range(AGENT_LABEL_MESSAGES_FALLBACK_ATTEMPTS):
            if attempt:
                _time.sleep(AGENT_LABEL_MESSAGES_FALLBACK_DELAY_S)
            assistant_text = _agent_fetch_final_assistant_text(base, token, thread_id)
            if assistant_text.strip():
                break

    labels: list[str] = []
    for raw in assistant_text.strip().split("\n"):
        label = raw.strip()
        if label:
            add_label(labels, label, max_labels)
    return labels


@dataclass
class DiaryEntry:
    path: Path
    day: date
    base_title: str
    text: str
    text_hash: str
    session_id: str
    created_at_db: str
    created_at_state: str
    date_source: str
    labels: list[str]
    title: str = ""
    action: str = "insert"
    skip_reason: str = ""


@dataclass(frozen=True)
class ExistingSession:
    session_id: str
    local_day: date | None
    name: str
    text_hash: str
    first_line: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import dated diary Markdown files into user_sessions."
    )
    parser.add_argument(
        "--source-dir",
        default=os.environ.get("INK_MEMORY_DIARY_SOURCE_DIR"),
        help="Directory containing diary Markdown files; can also use INK_MEMORY_DIARY_SOURCE_DIR.",
    )
    parser.add_argument("--email", help="User email (alternative to --user-id).")
    parser.add_argument("--user-id", type=int, help="User ID (alternative to --email).")
    parser.add_argument("--start-date", help="Inclusive local date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Inclusive local date, YYYY-MM-DD.")
    parser.add_argument(
        "--timezone",
        help="IANA timezone. Defaults to user preference, INK_MEMORY_IMPORT_TIMEZONE, or Asia/Shanghai.",
    )
    parser.add_argument(
        "--time",
        default=DEFAULT_IMPORT_TIME,
        help=(
            "Local time assigned when --date-source uses filename dates, HH:MM "
            f"(default {DEFAULT_IMPORT_TIME})."
        ),
    )
    parser.add_argument(
        "--date-source",
        choices=DATE_SOURCE_CHOICES,
        default=os.environ.get("INK_MEMORY_DIARY_DATE_SOURCE", DEFAULT_DATE_SOURCE),
        help=(
            "How to assign each Markdown file to a date. Default created-first uses "
            "same-name folder stems first, then filename stems like 思考笔记本-5-17, "
            "then file creation time, and finally filename dates when creation time "
            "is unavailable."
        ),
    )
    parser.add_argument(
        "--default-year",
        type=int,
        default=None,
        help="Year used for month-day folder names like 临时记事本-5-13.",
    )
    parser.add_argument(
        "--diary-filenames-only",
        action="store_true",
        help="Only import files whose basename matches 日记YYYY-M-D.md or 日记-YYYY-M-D.md.",
    )
    parser.add_argument(
        "--same-name-folder-docs-only",
        action="store_true",
        help="Only import docs whose parent folder stem equals the Markdown file stem.",
    )
    parser.add_argument(
        "--selected-state",
        default=os.environ.get("INK_MEMORY_IMPORT_SELECTED_STATE", DEFAULT_SELECTED_STATE),
        help=(
            "Editor selectedState for imported sessions. Use an empty string to omit it "
            f"(default {DEFAULT_SELECTED_STATE}, displayed as OK by the default state config)."
        ),
    )
    parser.add_argument(
        "--label-mode",
        choices=LABEL_MODE_CHOICES,
        default=os.environ.get("INK_MEMORY_IMPORT_LABEL_MODE", DEFAULT_LABEL_MODE),
        help=(
            "How to populate user_sessions.labels. "
            "auto infers front matter, hashtags, path subjects, and content keywords; "
            "agent calls the Claude Agent service (POST /api/claude-agent) for dynamic "
            "label inference — requires --backend-url and a running backend; "
            "none writes an empty label list."
        ),
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("INK_MEMORY_BACKEND_URL", DEFAULT_BACKEND_URL),
        help=(
            "Base URL of the running Ink & Memory backend, used with --label-mode agent "
            f"(default {DEFAULT_BACKEND_URL}, env INK_MEMORY_BACKEND_URL)."
        ),
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("INK_MEMORY_IMPORT_API_TOKEN"),
        help=(
            "Bearer JWT to authenticate against the backend. "
            "If omitted, a token is auto-generated from the resolved user record "
            "(env INK_MEMORY_IMPORT_API_TOKEN)."
        ),
    )
    parser.add_argument(
        "--max-labels",
        type=int,
        default=int(os.environ.get("INK_MEMORY_IMPORT_MAX_LABELS", DEFAULT_MAX_LABELS)),
        help=f"Maximum labels per imported session (default {DEFAULT_MAX_LABELS}).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Update an existing deterministic import session instead of skipping it.",
    )
    parser.add_argument(
        "--force-labels",
        action="store_true",
        default=os.environ.get("INK_MEMORY_IMPORT_FORCE_LABELS", "").lower() in ("1", "true"),
        help=(
            "Always run label inference even when the session already exists in the database. "
            "By default, existing sessions (without --replace) skip label inference to avoid "
            "redundant agent calls (env INK_MEMORY_IMPORT_FORCE_LABELS)."
        ),
    )
    parser.add_argument(
        "--workers",
        "-j",
        type=int,
        default=int(os.environ.get("INK_MEMORY_IMPORT_WORKERS", 1)),
        help=(
            "Number of parallel worker threads for file processing and label inference. "
            "Values > 1 are most effective with --label-mode agent where each file makes "
            "an HTTP call (default 1, env INK_MEMORY_IMPORT_WORKERS)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the import plan without writing to the database.",
    )
    return parser.parse_args()


def parse_day(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"{label} must be YYYY-MM-DD: {value}") from exc


def parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise SystemExit(f"--time must be HH:MM: {value}") from exc


def resolve_default_year(
    explicit_year: int | None,
    start_day: date | None,
    end_day: date | None,
    tz: ZoneInfo,
) -> int:
    if explicit_year is None and os.environ.get("INK_MEMORY_IMPORT_DEFAULT_YEAR"):
        try:
            explicit_year = int(os.environ["INK_MEMORY_IMPORT_DEFAULT_YEAR"])
        except ValueError as exc:
            raise SystemExit("INK_MEMORY_IMPORT_DEFAULT_YEAR must be an integer.") from exc

    if explicit_year is not None:
        if explicit_year < 1:
            raise SystemExit("--default-year must be a positive year.")
        return explicit_year
    if start_day and end_day and start_day.year == end_day.year:
        return start_day.year
    if start_day:
        return start_day.year
    if end_day:
        return end_day.year
    return datetime.now(tz).year


def resolve_source_dir(value: str | None) -> Path:
    if not value:
        raise SystemExit("--source-dir or INK_MEMORY_DIARY_SOURCE_DIR is required.")
    source_dir = Path(value).expanduser().resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory not found: {source_dir}")
    return source_dir


def list_users() -> list[dict]:
    db = database.get_db()
    try:
        rows = db.execute("SELECT id, email, display_name FROM users ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def resolve_user_id(email: str | None, user_id: int | None) -> int:
    if user_id:
        user = database.get_user_by_id(user_id)
        if not user:
            raise SystemExit(f"User ID {user_id} not found.")
        return user["id"]

    if email:
        user = database.get_user_by_email(email)
        if not user:
            raise SystemExit(f"User with email {email} not found.")
        return user["id"]

    users = list_users()
    if len(users) == 1:
        return users[0]["id"]

    raise SystemExit("Either --email or --user-id is required when multiple users exist.")


def resolve_timezone(tz_arg: str | None, user_id: int) -> ZoneInfo:
    tz_name = tz_arg

    if not tz_name:
        db = database.get_db()
        try:
            row = db.execute(
                "SELECT timezone FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            tz_name = row["timezone"] if row and row["timezone"] else None
        finally:
            db.close()

    if not tz_name:
        tz_name = os.environ.get("INK_MEMORY_IMPORT_TIMEZONE") or DEFAULT_TIMEZONE

    try:
        return ZoneInfo(tz_name)
    except Exception as exc:
        raise SystemExit(f"Invalid timezone: {tz_name}") from exc


def filename_date_from_path(path: Path) -> date | None:
    match = DIARY_FILE_RE.match(path.name)
    if not match:
        return None

    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise SystemExit(f"Invalid diary date in filename: {path}") from exc


def month_day_stem_date(stem: str, default_year: int) -> date | None:
    match = STEM_MONTH_DAY_RE.match(stem)
    if not match:
        return None

    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        return date(default_year, month, day)
    except ValueError as exc:
        raise SystemExit(f"Invalid month-day date in stem: {stem}") from exc


def same_name_folder_date_from_path(path: Path, default_year: int) -> date | None:
    if path.suffix.lower() != ".md":
        return None
    if path.parent.name != path.stem:
        return None

    day = filename_date_from_path(path)
    if day:
        return day
    return month_day_stem_date(path.stem, default_year)


def stem_date_from_path(path: Path, default_year: int) -> date | None:
    if path.suffix.lower() != ".md":
        return None

    day = filename_date_from_path(path)
    if day:
        return day
    return month_day_stem_date(path.stem, default_year)


def strip_yaml_front_matter(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        return text.strip()

    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return text.strip()


def normalize_label(value: str) -> str:
    label = value.strip().strip("#").strip()
    label = re.sub(r"\s+", " ", label)
    label = label.strip(" ,，、;；[]")
    return label[:40]


def add_label(labels: list[str], label: str, max_labels: int) -> None:
    normalized = normalize_label(label)
    if not normalized:
        return
    if normalized.lower() in {existing.lower() for existing in labels}:
        return
    if len(labels) < max_labels:
        labels.append(normalized)


def split_inline_labels(value: str) -> list[str]:
    stripped = value.strip()
    bracketed = INLINE_LABEL_LIST_RE.match(stripped)
    if bracketed:
        stripped = bracketed.group(1)
    return [
        item.strip().strip("'\"")
        for item in re.split(r"[,，、]", stripped)
        if item.strip().strip("'\"")
    ]


def explicit_labels_from_front_matter(raw: str) -> list[str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        return []

    lines = text.split("\n")
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return []

    labels: list[str] = []
    index = 1
    while index < end_index:
        line = lines[index]
        key_match = re.match(r"^\s*(tags|labels)\s*:\s*(.*)$", line, re.IGNORECASE)
        if not key_match:
            index += 1
            continue

        value = key_match.group(2).strip()
        if value:
            labels.extend(split_inline_labels(value))
            index += 1
            continue

        index += 1
        while index < end_index:
            item_match = re.match(r"^\s*-\s+(.+)$", lines[index])
            if not item_match:
                break
            labels.append(item_match.group(1).strip().strip("'\""))
            index += 1
    return labels


def explicit_labels_from_hashtags(body: str) -> list[str]:
    labels: list[str] = []
    for match in HASHTAG_RE.finditer(body):
        label = normalize_label(match.group(1))
        if re.fullmatch(r"\d+", label):
            continue
        if re.fullmatch(r"[A-Za-z]\d+", label):
            continue
        labels.append(label)
    return labels


def path_subject_labels(path: Path) -> list[str]:
    stem = path.stem
    labels: list[str] = []

    if DIARY_FILE_RE.match(path.name):
        labels.append("日记")
    if "临时记事本" in path.as_posix():
        labels.append("临时记事本")
    if "思考笔记本" in stem:
        labels.append("思考笔记")
    if stem.startswith("PDST-CHAT"):
        labels.append("PDST-CHAT")
    if stem == "ISSUE-LIFECYCLE-ANALYSIS":
        labels.append("Issue Lifecycle")
    if stem == "智能体协作工程管理":
        labels.extend(["智能体协作", "工程管理"])

    if stem.startswith("PDST-CHAT") or stem in {
        "ISSUE-LIFECYCLE-ANALYSIS",
        "智能体协作工程管理",
    }:
        cleaned = ""
    else:
        cleaned = re.sub(r"^日记-?\d{4}-\d{1,2}-\d{1,2}$", "", stem)
        cleaned = re.sub(r"^.+-\d{1,2}-\d{1,2}$", "", cleaned)
        cleaned = re.sub(r"\s*\(\d+\)$", "", cleaned)
    cleaned = cleaned.strip(" -_")
    if cleaned and cleaned not in {"临时记事本", "思考笔记本"} and len(cleaned) <= 12:
        labels.append(cleaned)
    return labels


def infer_labels(
    path: Path,
    raw: str,
    body: str,
    mode: str,
    max_labels: int,
    agent_ctx: AgentLabelContext | None = None,
) -> list[str]:
    if max_labels < 1:
        raise SystemExit("--max-labels must be a positive integer.")
    if mode == "none":
        return []

    if mode == "agent":
        if agent_ctx is None:
            raise SystemExit(
                "--label-mode agent requires --backend-url (or INK_MEMORY_BACKEND_URL) "
                "and a running backend."
            )
        try:
            labels = _agent_infer_labels(
                body,
                agent_ctx.backend_url,
                agent_ctx.token,
                agent_ctx.max_labels,
                thread_title=f"label-inference: {path.name}",
            )
        except Exception as exc:
            print(
                f"WARNING: agent label inference failed for {path.name}: {exc}",
                file=sys.stderr,
            )
            labels = []
        return labels[:max_labels]

    # auto mode: front matter + hashtags + path subjects
    labels: list[str] = []
    for label in explicit_labels_from_front_matter(raw):
        add_label(labels, label, max_labels)
    for label in explicit_labels_from_hashtags(body):
        add_label(labels, label, max_labels)
    for label in path_subject_labels(path):
        add_label(labels, label, max_labels)
    return labels


def normalized_text_hash(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def content_with_filename_first_line(path: Path, body: str) -> str:
    filename = path.name.strip()
    stripped_body = body.strip()
    first_line = stripped_body.splitlines()[0].strip() if stripped_body else ""
    if first_line == filename:
        return stripped_body
    return f"{filename}\n\n{stripped_body}" if stripped_body else filename


def file_datetime_from_timestamp(timestamp: float, tz: ZoneInfo) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(tz)


def file_creation_datetime(path: Path, tz: ZoneInfo) -> datetime | None:
    creation_timestamp = getattr(path.stat(), "st_birthtime", None)
    if creation_timestamp is None:
        return None
    return file_datetime_from_timestamp(creation_timestamp, tz)


def file_modified_datetime(path: Path, tz: ZoneInfo) -> datetime:
    return file_datetime_from_timestamp(path.stat().st_mtime, tz)


def timestamp_strings_from_local(local_dt: datetime) -> tuple[str, str]:
    utc_dt = local_dt.astimezone(timezone.utc)
    return (
        utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        utc_dt.isoformat().replace("+00:00", "Z"),
    )


def filename_day_timestamp(
    path: Path,
    import_time: time,
    tz: ZoneInfo,
    offset_minutes: int,
) -> tuple[date, str, str, str] | None:
    day = filename_date_from_path(path)
    if not day:
        return None
    created_at_db, created_at_state = local_timestamp(day, import_time, tz, offset_minutes)
    return day, created_at_db, created_at_state, "filename"


def structured_day_timestamp(
    path: Path,
    day: date,
    import_time: time,
    tz: ZoneInfo,
    offset_minutes: int,
    source_name: str,
) -> tuple[date, str, str, str]:
    modified_dt = file_modified_datetime(path, tz)
    if modified_dt.date() == day:
        created_at_db, created_at_state = timestamp_strings_from_local(modified_dt)
        return day, created_at_db, created_at_state, source_name

    created_dt = file_creation_datetime(path, tz)
    if created_dt and created_dt.date() == day:
        created_at_db, created_at_state = timestamp_strings_from_local(created_dt)
        return day, created_at_db, created_at_state, source_name

    created_at_db, created_at_state = local_timestamp(day, import_time, tz, offset_minutes)
    return day, created_at_db, created_at_state, source_name


def resolve_file_day(
    path: Path,
    date_source: str,
    import_time: time,
    tz: ZoneInfo,
    offset_minutes: int,
    default_year: int,
) -> tuple[date, str, str, str] | None:
    folder_day = same_name_folder_date_from_path(path, default_year)
    if folder_day and date_source in ("created-first", "folder-name"):
        return structured_day_timestamp(
            path, folder_day, import_time, tz, offset_minutes, "folder-name"
        )

    if date_source == "folder-name":
        return None

    stem_day = stem_date_from_path(path, default_year)
    if stem_day and date_source in ("created-first", "stem-name"):
        return structured_day_timestamp(
            path, stem_day, import_time, tz, offset_minutes, "stem-name"
        )

    if date_source == "stem-name":
        return None

    if date_source == "filename":
        return filename_day_timestamp(path, import_time, tz, offset_minutes)

    if date_source == "modified":
        local_dt = file_modified_datetime(path, tz)
        created_at_db, created_at_state = timestamp_strings_from_local(local_dt)
        return local_dt.date(), created_at_db, created_at_state, "modified"

    created_dt = file_creation_datetime(path, tz)
    if created_dt:
        created_at_db, created_at_state = timestamp_strings_from_local(created_dt)
        return created_dt.date(), created_at_db, created_at_state, "created"

    if date_source == "created":
        raise SystemExit(f"Creation time is unavailable for: {path}")

    return filename_day_timestamp(path, import_time, tz, offset_minutes)


def title_for_path(day: date, path: Path) -> str:
    if DIARY_FILE_RE.match(path.name):
        return f"日记 {day.isoformat()}"
    return f"{day.isoformat()} {path.stem}"


def make_session_id(user_id: int, source_dir: Path, path: Path, day: date) -> str:
    relative = path.resolve().relative_to(source_dir).as_posix()
    stable_key = f"ink-and-memory:diary-import:user:{user_id}:{day.isoformat()}:{relative}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))


def local_timestamp(
    day: date,
    import_time: time,
    tz: ZoneInfo,
    offset_minutes: int,
) -> tuple[str, str]:
    local_dt = datetime.combine(day, import_time, tzinfo=tz) + timedelta(
        minutes=offset_minutes
    )
    utc_dt = local_dt.astimezone(timezone.utc)
    return (
        utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        utc_dt.isoformat().replace("+00:00", "Z"),
    )


def collect_diary_entries(
    source_dir: Path,
    user_id: int,
    start_day: date | None,
    end_day: date | None,
    tz: ZoneInfo,
    import_time: time,
    date_source: str,
    default_year: int,
    diary_filenames_only: bool,
    same_name_folder_docs_only: bool,
    label_mode: str,
    max_labels: int,
    agent_ctx: AgentLabelContext | None = None,
    existing_session_ids: set[str] | None = None,
    replace: bool = False,
    force_labels: bool = False,
    workers: int = 1,
) -> list[DiaryEntry]:
    dated_paths: list[tuple[date, str, str, str, Path]] = []
    per_day_counts: dict[date, int] = {}
    for path in source_dir.rglob("*.md"):
        if diary_filenames_only and not filename_date_from_path(path):
            continue
        if same_name_folder_docs_only and not same_name_folder_date_from_path(path, default_year):
            continue

        seed_day = (
            same_name_folder_date_from_path(path, default_year)
            or stem_date_from_path(path, default_year)
            or filename_date_from_path(path)
            or file_modified_datetime(path, tz).date()
        )
        offset = per_day_counts.get(seed_day, 0)
        resolved = resolve_file_day(
            path, date_source, import_time, tz, offset, default_year
        )
        if not resolved:
            continue
        day, created_at_db, created_at_state, resolved_source = resolved

        if start_day and day < start_day:
            continue
        if end_day and day > end_day:
            continue
        per_day_counts[day] = per_day_counts.get(day, 0) + 1
        dated_paths.append((day, created_at_db, created_at_state, resolved_source, path))

    sorted_paths = sorted(
        dated_paths, key=lambda item: (item[0], item[1], item[4].as_posix())
    )
    work_items = [
        _EntryTask(
            day=day,
            created_at_db=created_at_db,
            created_at_state=created_at_state,
            resolved_source=resolved_source,
            path=path,
            user_id=user_id,
            source_dir=source_dir,
            label_mode=label_mode,
            max_labels=max_labels,
            agent_ctx=agent_ctx,
            existing_session_ids=existing_session_ids,
            replace=replace,
            force_labels=force_labels,
        )
        for day, created_at_db, created_at_state, resolved_source, path in sorted_paths
    ]

    bar_desc = "Labeling (agent)" if label_mode == "agent" else "Processing"
    effective_workers = max(1, workers)

    if effective_workers == 1:
        results: list[DiaryEntry | None] = []
        with tqdm(
            work_items,
            desc=bar_desc,
            unit="file",
            file=sys.stderr,
            dynamic_ncols=True,
        ) as bar:
            for task in bar:
                bar.set_postfix_str(task.path.name, refresh=False)
                results.append(_process_entry_task(task))
    else:
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            results = list(
                tqdm(
                    executor.map(_process_entry_task, work_items),
                    total=len(work_items),
                    desc=f"{bar_desc} (×{effective_workers})",
                    unit="file",
                    file=sys.stderr,
                    dynamic_ncols=True,
                )
            )

    return [r for r in results if r is not None]


def parse_db_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    cleaned = raw.replace("Z", "+00:00")
    if "T" not in cleaned and " " in cleaned:
        cleaned = cleaned.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def text_from_editor_state(editor_state_json: str) -> str:
    try:
        state = json.loads(editor_state_json)
    except json.JSONDecodeError:
        return ""
    return "\n\n".join(
        cell.get("content", "")
        for cell in state.get("cells", [])
        if cell.get("type") == "text" and cell.get("content", "").strip()
    ).strip()


def first_line_from_text(text: str) -> str:
    return text.splitlines()[0].strip() if text else ""


def fetch_existing_sessions(user_id: int, tz: ZoneInfo) -> list[ExistingSession]:
    db = database.get_db()
    try:
        rows = db.execute(
            """
            SELECT id, name, editor_state_json, created_at, updated_at
            FROM user_sessions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    sessions: list[ExistingSession] = []
    for row in rows:
        timestamp = parse_db_timestamp(row["created_at"] or row["updated_at"])
        local_day = timestamp.astimezone(tz).date() if timestamp else None
        text = text_from_editor_state(row["editor_state_json"])
        sessions.append(
            ExistingSession(
                session_id=row["id"],
                local_day=local_day,
                name=row["name"] or "",
                text_hash=normalized_text_hash(text) if text else "",
                first_line=first_line_from_text(text),
            )
        )
    return sessions


def unique_title(base_title: str, used_titles: set[str]) -> str:
    if base_title not in used_titles:
        return base_title

    counter = 2
    while True:
        candidate = f"{base_title} ({counter})"
        if candidate not in used_titles:
            return candidate
        counter += 1


def plan_entries(
    entries: list[DiaryEntry],
    existing_sessions: list[ExistingSession],
    replace: bool,
) -> list[DiaryEntry]:
    existing_ids = {session.session_id for session in existing_sessions}
    existing_by_content_filename: dict[tuple[str, str], ExistingSession] = {}
    for session in existing_sessions:
        if session.text_hash and session.first_line:
            existing_by_content_filename.setdefault(
                (session.text_hash, session.first_line),
                session,
            )

    for entry in entries:
        if entry.session_id in existing_ids:
            continue
        matching_existing = existing_by_content_filename.get(
            (entry.text_hash, entry.path.name)
        )
        if matching_existing:
            entry.session_id = matching_existing.session_id

    existing_by_day: dict[date, list[ExistingSession]] = {}
    for session in existing_sessions:
        if session.local_day:
            existing_by_day.setdefault(session.local_day, []).append(session)

    used_titles_by_day: dict[date, set[str]] = {}
    for session in existing_sessions:
        if session.local_day and session.name:
            used_titles_by_day.setdefault(session.local_day, set()).add(session.name)

    planned_ids = {entry.session_id for entry in entries}
    for session in existing_sessions:
        if session.session_id in planned_ids and session.local_day and session.name:
            used_titles_by_day[session.local_day].discard(session.name)

    for entry in entries:
        used_titles = used_titles_by_day.setdefault(entry.day, set())

        same_day_sessions = existing_by_day.get(entry.day, [])
        duplicate_content = next(
            (
                session
                for session in same_day_sessions
                if session.session_id != entry.session_id
                and session.text_hash
                and session.text_hash == entry.text_hash
            ),
            None,
        )
        if duplicate_content:
            entry.action = "skip"
            entry.skip_reason = (
                f"same text already exists on {entry.day.isoformat()} "
                f"as {duplicate_content.session_id}"
            )
            entry.title = entry.base_title
            continue

        entry.title = unique_title(entry.base_title, used_titles)
        used_titles.add(entry.title)

        if entry.session_id in existing_ids:
            if replace:
                entry.action = "replace"
            else:
                entry.action = "skip"
                entry.skip_reason = "deterministic import session already exists"

    return entries


def build_editor_state(entry: DiaryEntry, selected_state: str | None) -> dict:
    text_cell_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{entry.session_id}:text").hex[:12]
    return {
        "cells": [{"id": text_cell_id, "type": "text", "content": entry.text}],
        "commentors": [],
        "tasks": [],
        "weightPath": [],
        "overlappedPhrases": [],
        "notFoundPhrases": [],
        "id": entry.session_id,
        "selectedState": selected_state,
        "createdAt": entry.created_at_state,
    }


def preserve_import_timestamps(user_id: int, entry: DiaryEntry) -> None:
    db = database.get_db()
    try:
        db.execute(
            """
            UPDATE user_sessions
            SET created_at = ?,
                updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (entry.created_at_db, entry.created_at_db, user_id, entry.session_id),
        )
        db.commit()
    finally:
        db.close()


def import_entries(
    user_id: int,
    entries: list[DiaryEntry],
    dry_run: bool,
    selected_state: str | None,
) -> None:
    with tqdm(
        entries,
        desc="Importing",
        unit="entry",
        file=sys.stderr,
        dynamic_ncols=True,
    ) as bar:
        for entry in bar:
            bar.set_postfix_str(entry.base_title[:50], refresh=False)
            relative = entry.path.as_posix()
            labels_text = ", ".join(entry.labels) if entry.labels else "-"
            if entry.action == "skip":
                tqdm.write(
                    f"SKIP    {entry.day.isoformat()}  [{entry.date_source}]  {entry.base_title}  "
                    f"{relative}  labels=[{labels_text}]  ({entry.skip_reason})"
                )
                continue

            verb = "REPLACE" if entry.action == "replace" else "INSERT "
            tqdm.write(
                f"{verb} {entry.day.isoformat()}  [{entry.date_source}]  {entry.title}  "
                f"{relative}  labels=[{labels_text}]"
            )
            if dry_run:
                continue

            database.save_session(
                user_id,
                entry.session_id,
                build_editor_state(entry, selected_state),
                name=entry.title,
                created_at=entry.created_at_db,
                labels=entry.labels,
            )
            preserve_import_timestamps(user_id, entry)


def print_summary(entries: list[DiaryEntry], dry_run: bool) -> None:
    inserts = sum(1 for entry in entries if entry.action == "insert")
    replaces = sum(1 for entry in entries if entry.action == "replace")
    skips = sum(1 for entry in entries if entry.action == "skip")
    mode = "dry run" if dry_run else "write"
    print(
        f"Summary ({mode}): {inserts} insert(s), {replaces} replace(s), {skips} skip(s)."
    )


def main() -> None:
    args = parse_args()
    source_dir = resolve_source_dir(args.source_dir)
    user_id = resolve_user_id(args.email, args.user_id)
    tz = resolve_timezone(args.timezone, user_id)
    import_time = parse_time(args.time)
    start_day = parse_day(args.start_date, "--start-date") if args.start_date else None
    end_day = parse_day(args.end_date, "--end-date") if args.end_date else None
    if start_day and end_day and start_day > end_day:
        raise SystemExit("--start-date must be on or before --end-date.")
    default_year = resolve_default_year(args.default_year, start_day, end_day, tz)

    agent_ctx: AgentLabelContext | None = None
    if args.label_mode == "agent":
        backend_url = args.backend_url or DEFAULT_BACKEND_URL
        token = args.api_token or _build_agent_token(user_id)
        agent_ctx = AgentLabelContext(
            backend_url=backend_url, token=token, max_labels=args.max_labels
        )

    existing = fetch_existing_sessions(user_id, tz)
    existing_session_ids = {s.session_id for s in existing}

    entries = collect_diary_entries(
        source_dir=source_dir,
        user_id=user_id,
        start_day=start_day,
        end_day=end_day,
        tz=tz,
        import_time=import_time,
        date_source=args.date_source,
        default_year=default_year,
        diary_filenames_only=args.diary_filenames_only,
        same_name_folder_docs_only=args.same_name_folder_docs_only,
        label_mode=args.label_mode,
        max_labels=args.max_labels,
        agent_ctx=agent_ctx,
        existing_session_ids=existing_session_ids,
        replace=args.replace,
        force_labels=args.force_labels,
        workers=args.workers,
    )
    planned = plan_entries(entries, existing, replace=args.replace)
    selected_state = args.selected_state.strip() or None

    print(f"User: {user_id}")
    print(f"Source: {source_dir}")
    print(f"Timezone: {tz.key}")
    print(f"Date source: {args.date_source}")
    print(f"Default year: {default_year}")
    print(f"Selected state: {selected_state or '(none)'}")
    print(f"Label mode: {args.label_mode}")
    if agent_ctx:
        print(f"Agent backend: {agent_ctx.backend_url}")
    print(f"Workers: {args.workers}")
    print(f"Force labels: {args.force_labels}")
    print(f"Max labels: {args.max_labels}")
    if args.same_name_folder_docs_only:
        file_scope = "same-name folder docs only"
    elif args.diary_filenames_only:
        file_scope = "diary filenames only"
    else:
        file_scope = "all Markdown files"
    print(f"File scope: {file_scope}")
    if start_day or end_day:
        print(
            "Date range: "
            f"{start_day.isoformat() if start_day else '-∞'}.."
            f"{end_day.isoformat() if end_day else '+∞'}"
        )
    print(f"Matched Markdown file(s): {len(entries)}")

    import_entries(user_id, planned, dry_run=args.dry_run, selected_state=selected_state)
    print_summary(planned, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
