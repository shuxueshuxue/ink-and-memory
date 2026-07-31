# [Input] Consume Claude Code hook stdin, project PAWKEYLAND_MEM0_* env, and JSONL transcripts.
# [Output] Provide SessionStart additionalContext injection and Stop-time Mem0 session summaries.
# [Pos] Claude Code lifecycle hook node under .claude/hooks
# [Sync] 2026-05-10: keep hook memory lookup/write on the Pawkeyland app-resolved Mem0 user index.
# [Sync] 2026-05-10: use the app memory recall policy to expand short meeting-memory queries.
# [Sync] 2026-05-10: restore origin/claude-runner Mem0 session hook flow with Volcengine PAWKEYLAND_MEM0_API_HOST config.
# [Sync] 2026-05-11: append diagnostic lines to $CLAUDE_PROJECT_DIR/logs/mem0_hooks.log for hook debugging (stdout stays JSON-only).
# [Sync] 2026-05-11: diag log emits raw Mem0 recall query (and expanded query) quoted for newline safety.

"""Claude Code session hooks for Mem0 via AsyncMemoryClient.

Entry points:
- mem0-hook-context  -> context_main()   (SessionStart)
- mem0-hook-stop     -> stop_main()      (Stop)
- mem0-install-hooks -> install_main()   (CLI installer)

Required environment variables:
  PAWKEYLAND_MEM0_API_KEY    - Mem0 data-plane API key
  PAWKEYLAND_MEM0_API_HOST   - Volcengine Mem0 host

Runtime environment variables:
  MEM0_USER_ID                 - app memory key resolved from business user_id + persona_id
  PAWKEYLAND_AGENT_USER_MESSAGE - current user message used as the recall query
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

_PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))
_DOTENV_MEM0_CONFIG_KEYS = frozenset(
    {
        "PAWKEYLAND_MEM0_ENABLED",
        "PAWKEYLAND_MEM0_API_KEY",
        "PAWKEYLAND_MEM0_API_HOST",
        "PAWKEYLAND_MEM0_CONNECT_TIMEOUT_MS",
        "PAWKEYLAND_MEM0_READ_TIMEOUT_MS",
        "PAWKEYLAND_MEM0_TOP_K",
    }
)


def _load_project_mem0_config(path: Path) -> None:
    """Load Mem0 service config from .env without loading request identity."""

    if not path.exists():
        return
    for key, value in dotenv_values(path).items():
        if (
            key in _DOTENV_MEM0_CONFIG_KEYS
            and value is not None
            and key not in os.environ
        ):
            os.environ[str(key)] = str(value)


# Load project .env early so standalone hook runs see the same Mem0 data-plane
# config as the app path. Request identity is intentionally excluded; runner.py
# injects MEM0_USER_ID and PAWKEYLAND_AGENT_USER_MESSAGE per turn.
_load_project_mem0_config(_PROJECT_DIR / ".env")

# Hooks write JSON responses to stdout. Logging must stay on stderr so it never
# corrupts Claude Code's hook response channel.
logging.basicConfig(stream=sys.stderr, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def _hook_diag_log(message: str) -> None:
    """Append a timestamped line under CLAUDE_PROJECT_DIR/logs; never raises; never touches stdout."""

    try:
        log_dir = _PROJECT_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        path = log_dir / "mem0_hooks.log"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"[{ts}] {message}\n")
    except OSError:
        pass


def _hook_diag_log_exc(context: str) -> None:
    """Write a full traceback to the hook diag log (call from active except handler)."""

    _hook_diag_log(f"{context}: {traceback.format_exc().rstrip()}")

_client = None

_MAX_MEMORIES = 20
_MIN_USER_LEN = 20
_MIN_ASSISTANT_LEN = 50
_MAX_CONTENT_LEN = 4000
_RECENT_WINDOW = 6


def _get_user_id() -> str:
    """Resolve the claude-runner-style Mem0 user ID injected by the runner."""

    return os.environ.get("MEM0_USER_ID", "").strip()


def _get_current_query() -> str:
    """Return the same current-turn query used by the memory MCP tool."""

    return os.environ.get("PAWKEYLAND_AGENT_USER_MESSAGE", "").strip()


def _expand_query(query: str) -> str:
    try:
        from prompts.policy_loader import expand_memory_recall_query

        return expand_memory_recall_query(query)
    except Exception:
        logger.debug("memory query expansion failed", exc_info=True)
        return query


def _get_top_k() -> int:
    raw = os.environ.get("PAWKEYLAND_MEM0_TOP_K", "").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 5
    return max(1, value)


def _get_client():
    """Lazy-initialize and cache a mem0 AsyncMemoryClient.

    The current branch uses Volcengine-hosted Mem0 data-plane config. Keep the
    same client and search/add flow from origin/claude-runner, but source host
    configuration only from PAWKEYLAND_MEM0_API_HOST.
    """

    global _client
    if _client is not None:
        return _client

    from mem0 import AsyncMemoryClient

    api_key = os.environ.get("PAWKEYLAND_MEM0_API_KEY", "").strip()
    host = os.environ.get("PAWKEYLAND_MEM0_API_HOST", "").strip().rstrip("/")
    if not api_key or not host:
        raise ValueError("PAWKEYLAND_MEM0_API_KEY and PAWKEYLAND_MEM0_API_HOST must be set")

    _client = AsyncMemoryClient(api_key=api_key, host=host)
    return _client


def _output(data: dict[str, Any]) -> None:
    """Print JSON to stdout, the Claude Code hook response channel."""

    print(json.dumps(data, ensure_ascii=False))


def _nonfatal() -> dict[str, Any]:
    """Return a fresh non-fatal hook response."""

    return {"continue": True, "suppressOutput": True}


def _extract_results(raw: Any) -> list[dict[str, Any]]:
    """Normalize Mem0 search results to a flat list of dictionaries."""

    if isinstance(raw, dict):
        results = raw.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
        memories = raw.get("memories")
        if isinstance(memories, list):
            return [item for item in memories if isinstance(item, dict)]
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


async def _context_async(hook_input: dict[str, Any]) -> None:
    """SessionStart hook core: fetch app-chat shared memories."""

    mem0_user_id = _get_user_id()
    query = _get_current_query()
    api_key_set = bool(os.environ.get("PAWKEYLAND_MEM0_API_KEY", "").strip())
    host_set = bool(os.environ.get("PAWKEYLAND_MEM0_API_HOST", "").strip())
    _hook_diag_log(
        f"_context_async mem0_user_id_set={bool(mem0_user_id)} query_len={len(query)} "
        f"api_key_set={api_key_set} host_set={host_set} top_k={_get_top_k()}"
    )
    _hook_diag_log(f"_context_async query={query!r}")
    if not mem0_user_id or not query:
        _hook_diag_log("_context_async skip: missing mem0_user_id or empty query")
        _output(_nonfatal())
        return

    client = _get_client()
    seen_ids: set[str] = set()
    all_memories: list[dict[str, Any]] = []

    expanded = _expand_query(query)
    _hook_diag_log(f"_context_async query_expanded len={len(expanded)} value={expanded!r}")
    results = _extract_results(
        await client.search(expanded, user_id=mem0_user_id, top_k=_get_top_k())
    )
    _hook_diag_log(f"_context_async search raw_hit_count={len(results)}")
    for result in results:
        memory_id = str(result.get("id") or result.get("memory_id") or "")
        text = _memory_text(result)
        dedupe_key = memory_id or text
        if dedupe_key and dedupe_key not in seen_ids:
            seen_ids.add(dedupe_key)
            all_memories.append(result)

    all_memories = all_memories[:_MAX_MEMORIES]
    _hook_diag_log(f"_context_async deduped_memory_count={len(all_memories)}")
    if not all_memories:
        _hook_diag_log("_context_async skip: zero memories after dedupe")
        _output(_nonfatal())
        return

    lines = ["# Pawkeyland Shared Memory\n"]
    for index, memory in enumerate(all_memories, 1):
        text = _memory_text(memory)
        if text:
            lines.append(f"{index}. {text}")

    response = _nonfatal()
    response["additionalContext"] = "\n".join(lines)
    _hook_diag_log(
        f"_context_async ok additionalContext_chars={len(response['additionalContext'])} "
        f"memories_injected={len(all_memories)}"
    )
    _output(response)


def context_main() -> None:
    """SessionStart hook entrypoint."""

    try:
        raw = sys.stdin.read()
        _hook_diag_log(f"context_main start project_dir={_PROJECT_DIR} stdin_bytes={len(raw)}")
        hook_input = json.loads(raw)
        keys = list(hook_input.keys()) if isinstance(hook_input, dict) else type(hook_input).__name__
        _hook_diag_log(f"context_main parsed hook_input_keys={keys}")
        asyncio.run(_context_async(hook_input))
    except Exception:
        _hook_diag_log_exc("context_main failed")
        logger.debug("context_main failed", exc_info=True)
        _output(_nonfatal())


def _memory_text(item: dict[str, Any]) -> str:
    for key in ("memory", "text", "content", "summary"):
        text = str(item.get(key) or "").strip()
        if text:
            return text
    return ""


def _extract_content(content: Any) -> str:
    """Extract plain text from a Claude Code transcript content field."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return " ".join(parts)
    return ""


def _read_recent_messages(transcript_path: str) -> list[tuple[str, str]]:
    """Read recent user/assistant transcript messages in chronological order."""

    messages: deque[tuple[str, str]] = deque(maxlen=_RECENT_WINDOW)
    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = entry.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = _extract_content(entry.get("content", ""))[:_MAX_CONTENT_LEN]
            if content:
                messages.append((role, content))
    return list(messages)


async def _stop_async(hook_input: dict[str, Any]) -> None:
    """Stop hook core: save a compact app-chat session summary to Mem0."""

    if hook_input.get("stop_hook_active"):
        _hook_diag_log("_stop_async skip: stop_hook_active")
        _output(_nonfatal())
        return

    mem0_user_id = _get_user_id()
    if not mem0_user_id:
        _hook_diag_log("_stop_async skip: missing mem0_user_id")
        _output(_nonfatal())
        return

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    transcript_exists = bool(transcript_path and Path(transcript_path).is_file())
    _hook_diag_log(
        f"_stop_async session_id_len={len(str(session_id))} "
        f"transcript_path_len={len(str(transcript_path))} transcript_exists={transcript_exists}"
    )

    if not transcript_path or not Path(transcript_path).is_file():
        _hook_diag_log("_stop_async skip: transcript path missing or not a file")
        _output(_nonfatal())
        return

    recent = _read_recent_messages(transcript_path)
    user_total = sum(len(content) for role, content in recent if role == "user")
    assistant_total = sum(len(content) for role, content in recent if role == "assistant")
    _hook_diag_log(
        f"_stop_async recent_window_messages={len(recent)} user_chars={user_total} "
        f"assistant_chars={assistant_total}"
    )
    if user_total < _MIN_USER_LEN and assistant_total < _MIN_ASSISTANT_LEN:
        _hook_diag_log(
            f"_stop_async skip: transcript too short "
            f"(min_user={_MIN_USER_LEN} min_assistant={_MIN_ASSISTANT_LEN})"
        )
        _output(_nonfatal())
        return

    exchanges = []
    for role, content in recent:
        label = "User" if role == "user" else "Assistant"
        exchanges.append(f"[{label}]: {content}")

    summary = (
        "Pawkeyland chat memory summary:\n\n"
        + "\n\n".join(exchanges)
        + "\n\n"
        "Extract stable user-pet shared stories, preferences, relationship facts, "
        "and important context that should help future Pawkeyland chat turns."
    )

    _hook_diag_log(f"_stop_async mem0 add summary_chars={len(summary)} infer=True")
    await _get_client().add(
        messages=[{"role": "user", "content": summary}],
        user_id=mem0_user_id,
        infer=True,
        metadata={
            "source": "pawkeyland-claude-code-stop-hook",
            "session_id": session_id,
        },
    )

    _hook_diag_log("_stop_async mem0 add completed")
    _output(_nonfatal())


def stop_main() -> None:
    """Stop hook entrypoint."""

    try:
        raw = sys.stdin.read()
        _hook_diag_log(f"stop_main start project_dir={_PROJECT_DIR} stdin_bytes={len(raw)}")
        hook_input = json.loads(raw)
        keys = list(hook_input.keys()) if isinstance(hook_input, dict) else type(hook_input).__name__
        _hook_diag_log(f"stop_main parsed hook_input_keys={keys}")
        asyncio.run(_stop_async(hook_input))
    except Exception:
        _hook_diag_log_exc("stop_main failed")
        logger.debug("stop_main failed", exc_info=True)
        _output(_nonfatal())


_HOOK_CONTEXT_CMD = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/mem0-context.sh'
_HOOK_STOP_CMD = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/mem0-stop.sh'


def _has_hook(hooks_list: list[Any], command: str) -> bool:
    for group in hooks_list:
        if not isinstance(group, dict):
            continue
        for handler in group.get("hooks") or []:
            if isinstance(handler, dict) and handler.get("command") == command:
                return True
        if group.get("command") == command:
            return True
    return False


_HANDLER_KEYS = {"command", "timeout"}
_GROUP_KEYS = {"matcher"}


def _migrate_legacy_hooks(hooks_list: list[Any]) -> list[dict[str, Any]]:
    """Convert legacy flat-format hooks to Claude Code's nested hook format."""

    migrated: list[dict[str, Any]] = []
    for group in hooks_list:
        if not isinstance(group, dict):
            continue
        if "hooks" in group:
            migrated.append(group)
        elif "command" in group:
            handler: dict[str, Any] = {"type": "command"}
            new_group: dict[str, Any] = {}
            for key, value in group.items():
                if key in _HANDLER_KEYS:
                    handler[key] = value
                elif key in _GROUP_KEYS:
                    new_group[key] = value
                else:
                    new_group[key] = value
            new_group["hooks"] = [handler]
            migrated.append(new_group)
        else:
            migrated.append(group)
    return migrated


def install_main() -> None:
    """CLI: install Mem0 session hooks into .claude/settings.json."""

    import argparse

    parser = argparse.ArgumentParser(
        prog="mem0-install-hooks",
        description="Install Mem0 session hooks for Claude Code",
    )
    parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install to ~/.claude/settings.json instead of project directory",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project directory, defaulting to CWD",
    )
    args = parser.parse_args()

    if args.global_install:
        settings_dir = Path.home() / ".claude"
    else:
        project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
        if not project_dir.is_dir():
            print(f"Error: project directory does not exist: {project_dir}", file=sys.stderr)
            sys.exit(1)
        settings_dir = project_dir / ".claude"

    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Error: {settings_path} contains invalid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        settings = {}

    if not isinstance(settings.get("hooks"), dict):
        settings["hooks"] = {}
    hooks = settings["hooks"]

    for event_key in ("SessionStart", "Stop"):
        if isinstance(hooks.get(event_key), list):
            hooks[event_key] = _migrate_legacy_hooks(hooks[event_key])

    installed: list[str] = []
    skipped: list[str] = []

    if not isinstance(hooks.get("SessionStart"), list):
        hooks["SessionStart"] = []
    if _has_hook(hooks["SessionStart"], _HOOK_CONTEXT_CMD):
        skipped.append(f"SessionStart ({_HOOK_CONTEXT_CMD})")
    else:
        hooks["SessionStart"].append(
            {
                "matcher": "startup|compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": _HOOK_CONTEXT_CMD,
                        "timeout": 15000,
                    }
                ],
            }
        )
        installed.append(f"SessionStart ({_HOOK_CONTEXT_CMD})")

    if not isinstance(hooks.get("Stop"), list):
        hooks["Stop"] = []
    if _has_hook(hooks["Stop"], _HOOK_STOP_CMD):
        skipped.append(f"Stop ({_HOOK_STOP_CMD})")
    else:
        hooks["Stop"].append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _HOOK_STOP_CMD,
                        "timeout": 30000,
                    }
                ],
            }
        )
        installed.append(f"Stop ({_HOOK_STOP_CMD})")

    fd, tmp_path = tempfile.mkstemp(dir=str(settings_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_path, str(settings_path))
    except BaseException:
        os.unlink(tmp_path)
        raise

    for hook in installed:
        print(f"Installed: {hook}")
    for hook in skipped:
        print(f"Already installed: {hook}")
    print(f"Settings: {settings_path}")
