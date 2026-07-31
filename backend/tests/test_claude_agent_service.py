# [Input] Consume ClaudeAgentService, ClaudeAgentRunRequest, AgentRunState,
#         service callback factories, and ToolEventPayload.
# [Output] Verify context assembly maps system_config into AgentRunOptions and
#          service-level SSE event mapping remains correct.
# [Pos] test node in backend/tests
# [Sync] 2026-06-14: combine system_config assembly coverage with tool_input_delta
#                    -> tool-input-delta SSE forwarding coverage.
# [Sync] 2026-06-14: cover Edit Session event publication after successful
#                    editor MCP write tool results.
# [Sync] 2026-06-17: cover SSE error formatting that includes exception notes
#                    from runner diagnostics.
# [Sync] 2026-06-21: cover sandbox network policy handoff to workspace init.
# [Sync] 2026-06-22: cover Settings SYSTEM_PROMPT handoff into system_prompt
#                    assembly, config-change cache rebuild, and config-load
#                    failure fallback.
# [Sync] 2026-06-25: cover CancelledError stop path emitting finish and stream sentinel.
# [Sync] 2026-07-04: cover workspace-local Notion snapshot attach and
#                    workspace_context Notion block rendering.
# [Sync] 2026-07-05: cover explicit Notion connector identity / sync cursor
#                    rendering in the workspace context summary.
# [Sync] 2026-07-26: assert sandbox_fs_allowed_write_paths passes from
#                    system_config through assemble_context into
#                    get_or_create_workspace.

"""Tests for ClaudeAgentService context assembly and SSE event mapping."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401 — stub claude_agent_sdk before service import

import claude_agent.service as service_module
import claude_agent.workspace_context as workspace_context_module
from claude_agent.service import ClaudeAgentRunRequest, ClaudeAgentService, _TurnContext
from claude_agent.thread_pool import AgentRunState
from claude_agent.tool_confirmation_store import ToolConfirmationStore
from libs.claude_agent_kit.types import ToolEventPayload


class _FakeContextBuilder:
    def __init__(self) -> None:
        self.system_prompt_calls: list[tuple[str, str | None]] = []
        self.user_message_calls: list[dict[str, Any]] = []

    async def build_system_prompt(
        self,
        user_id: str,
        *,
        configured_system_prompt: str | None = None,
    ) -> str:
        self.system_prompt_calls.append((user_id, configured_system_prompt))
        suffix = f":{configured_system_prompt}" if configured_system_prompt else ""
        return f"system-prompt:{user_id}{suffix}"

    def build_user_message(self, message_parts: list | None, **kwargs: Any) -> list[dict[str, Any]]:
        self.user_message_calls.append(kwargs)
        return [{"type": "text", "text": "assembled"}]


class _FakeBus:
    async def publish(self, frame: str | None) -> None:
        pass


class TestClaudeAgentServiceAssembleContext(unittest.IsolatedAsyncioTestCase):
    async def test_system_config_is_loaded_before_resume_db_lookup(self):
        builder = _FakeContextBuilder()
        service = ClaudeAgentService(context_builder=builder)
        state = AgentRunState(session_id="thread_service_config")
        request = ClaudeAgentRunRequest(
            user_id="7",
            thread_id="thread_service_config",
            message_parts=[{"type": "text", "text": "hello"}],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_path = Path(tmp_dir) / "thread_service_config"
            with (
                unittest.mock.patch.object(
                    service_module._db,
                    "get_system_config",
                    return_value={
                        "system_prompt": "Settings page prompt",
                        "im_full_access_enabled": True,
                        "workspace_enabled": True,
                        "sandbox_network_mode": "allowlist",
                        "sandbox_network_allowed_domains": [
                            "raw.githubusercontent.com",
                            "*.npmjs.org",
                        ],
                        "sandbox_fs_allowed_write_paths": [
                            "/data/out",
                            "/var/cache",
                        ],
                        "env_vars": {
                            "ANTHROPIC_AUTH_TOKEN": "user-token",
                            "EMPTY": None,
                            "  CUSTOM_KEY  ": "custom-value",
                        },
                    },
                ) as get_system_config,
                unittest.mock.patch.object(
                    service_module._db,
                    "get_chat_thread",
                    return_value=None,
                ) as get_chat_thread,
                unittest.mock.patch.object(
                    service_module,
                    "get_or_create_workspace",
                    return_value=workspace_path,
                ) as get_or_create_workspace,
            ):
                execution = await service.assemble_context(
                    request,
                    state=state,
                    bus=_FakeBus(),
                    runner=unittest.mock.Mock(),
                )

        get_system_config.assert_called_once_with(7)
        self.assertEqual(builder.system_prompt_calls, [("7", "Settings page prompt")])
        get_chat_thread.assert_called_once_with("thread_service_config", 7)
        get_or_create_workspace.assert_called_once_with(
            "thread_service_config",
            sandbox_enabled=True,
            sandbox_network_mode="allowlist",
            sandbox_network_allowed_domains=[
                "raw.githubusercontent.com",
                "*.npmjs.org",
            ],
            sandbox_fs_allowed_write_paths=[
                "/data/out",
                "/var/cache",
            ],
        )

        self.assertTrue(execution.run_options.im_full_access_enabled)
        self.assertEqual(execution.run_options.sandbox_network_mode, "allowlist")
        self.assertEqual(
            execution.run_options.system_prompt,
            "system-prompt:7:Settings page prompt",
        )
        self.assertEqual(str(workspace_path), execution.run_options.cwd)
        self.assertEqual(
            execution.run_options.mcp_env,
            {
                "ANTHROPIC_AUTH_TOKEN": "user-token",
                "CUSTOM_KEY": "custom-value",
                "INK_AGENT_USER_ID": "7",
            },
        )
        self.assertEqual(
            execution.run_options.user_sdk_env["ANTHROPIC_AUTH_TOKEN"],
            "user-token",
        )

    async def test_workspace_mode_disabled_skips_workspace_initialization(self):
        builder = _FakeContextBuilder()
        service = ClaudeAgentService(context_builder=builder)
        state = AgentRunState(session_id="thread_workspace_disabled")
        state.with_cwd("/tmp/stale-workspace")
        request = ClaudeAgentRunRequest(
            user_id="7",
            thread_id="thread_workspace_disabled",
            cwd="/tmp/client-workspace",
            message_parts=[{"type": "text", "text": "hello"}],
        )

        with (
            unittest.mock.patch.object(
                service_module._db,
                "get_system_config",
                return_value={"workspace_enabled": False},
            ),
            unittest.mock.patch.object(
                service_module._db,
                "get_chat_thread",
                return_value=None,
            ),
            unittest.mock.patch.object(
                service_module,
                "get_or_create_workspace",
            ) as get_or_create_workspace,
        ):
            execution = await service.assemble_context(
                request,
                state=state,
                bus=_FakeBus(),
                runner=unittest.mock.Mock(),
            )

        get_or_create_workspace.assert_not_called()
        self.assertEqual(state.cwd, "")
        self.assertIsNone(execution.run_options.cwd)
        self.assertEqual(builder.user_message_calls[0]["cwd"], "")

    async def test_settings_system_prompt_change_rebuilds_cached_system_prompt(self):
        builder = _FakeContextBuilder()
        service = ClaudeAgentService(context_builder=builder)
        state = AgentRunState(session_id="thread_service_prompt_change")
        state.with_system_prompt(
            "cached-old-prompt",
            system_config_system_prompt="old settings prompt",
        )
        state.is_context_initialized = True
        request = ClaudeAgentRunRequest(
            user_id="7",
            thread_id="thread_service_prompt_change",
            message_parts=[{"type": "text", "text": "hello"}],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_path = Path(tmp_dir) / "thread_service_prompt_change"
            with (
                unittest.mock.patch.object(
                    service_module._db,
                    "get_system_config",
                    return_value={"system_prompt": "new settings prompt"},
                ),
                unittest.mock.patch.object(
                    service_module._db,
                    "get_chat_thread",
                    return_value=None,
                ),
                unittest.mock.patch.object(
                    service_module,
                    "get_or_create_workspace",
                    return_value=workspace_path,
                ),
            ):
                execution = await service.assemble_context(
                    request,
                    state=state,
                    bus=_FakeBus(),
                    runner=unittest.mock.Mock(),
                )

        self.assertEqual(builder.system_prompt_calls, [("7", "new settings prompt")])
        self.assertEqual(state.system_config_system_prompt, "new settings prompt")
        self.assertEqual(
            execution.run_options.system_prompt,
            "system-prompt:7:new settings prompt",
        )

    async def test_system_config_load_failure_builds_prompt_without_settings_prompt(self):
        builder = _FakeContextBuilder()
        service = ClaudeAgentService(context_builder=builder)
        state = AgentRunState(session_id="thread_service_config_failure")
        request = ClaudeAgentRunRequest(
            user_id="7",
            thread_id="thread_service_config_failure",
            message_parts=[{"type": "text", "text": "hello"}],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_path = Path(tmp_dir) / "thread_service_config_failure"
            with (
                unittest.mock.patch.object(
                    service_module._db,
                    "get_system_config",
                    side_effect=RuntimeError("system_config unavailable"),
                ),
                unittest.mock.patch.object(
                    service_module._db,
                    "get_chat_thread",
                    return_value=None,
                ),
                unittest.mock.patch.object(
                    service_module,
                    "get_or_create_workspace",
                    return_value=workspace_path,
                ),
            ):
                execution = await service.assemble_context(
                    request,
                    state=state,
                    bus=_FakeBus(),
                    runner=unittest.mock.Mock(),
                )

        self.assertEqual(builder.system_prompt_calls, [("7", None)])
        self.assertEqual(execution.run_options.system_prompt, "system-prompt:7")
        self.assertEqual(
            execution.run_options.mcp_env,
            {"INK_AGENT_USER_ID": "7"},
        )


class TestClaudeAgentServiceNotionAttach(unittest.IsolatedAsyncioTestCase):
    async def test_workspace_attach_materializes_notion_snapshot_into_workspace_files(self):
        builder = _FakeContextBuilder()
        service = ClaudeAgentService(context_builder=builder)
        state = AgentRunState(session_id="thread_notion_attach")
        request = ClaudeAgentRunRequest(
            user_id="7",
            thread_id="thread_notion_attach",
            message_parts=[{"type": "text", "text": "hello"}],
        )

        snapshot_metadata = {
            "workspace_id": "thread_notion_attach",
            "resource_connector_id": "connector-attach",
            "snapshot_version": "snap-attach-001",
            "source_revision": "rev-attach-001",
            "sync_cursor": "cursor-attach-001",
            "fetched_at": "2026-07-04T00:00:00Z",
            "state": "snapshot_ready",
        }
        snapshot_payload = {
            "metadata": snapshot_metadata,
            "connector": {
                "id": "connector-attach",
                "platform": "notion",
                "auth_status": "authenticated",
            },
            "index": [{"page_id": "page-attach", "title": "Attach Page"}],
            "databases": [{"database_id": "db-attach", "title": "Attach Database"}],
            "database_pages": {
                "db-attach": [{"page_id": "page-attach", "title": "Attach Page"}],
            },
            "pages": {
                "page-attach": {
                    "page_id": "page-attach",
                    "title": "Attach Page",
                    "url": "https://www.notion.so/page-attach",
                    "last_edited": "2026-07-04T00:00:00Z",
                    "properties": {"Name": {"title": [{"plain_text": "Attach Page"}]}},
                    "blocks": [{"type": "paragraph", "text": "Canonical snapshot"}],
                }
            },
        }

        class _FakeFacade:
            def materialize_workspace(self, workspace_path: Path, connector_id=None, workspace_id=None):
                del connector_id, workspace_id
                notion_dir = workspace_path / ".notion"
                notion_dir.mkdir(parents=True, exist_ok=True)
                (notion_dir / "connector.json").write_text(
                    json.dumps(
                        {
                            "id": "connector-attach",
                            "platform": "notion",
                            "auth_status": "authenticated",
                            "selected_databases": ["db-attach"],
                            "selected_pages": ["page-attach"],
                            "snapshot": snapshot_metadata,
                        },
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                (notion_dir / "snapshot.json").write_text(
                    json.dumps(snapshot_metadata, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                (notion_dir / "index.json").write_text(
                    json.dumps(
                        {"pages": snapshot_payload["index"], "snapshot": snapshot_metadata},
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                (notion_dir / "databases.json").write_text(
                    json.dumps(
                        {"databases": snapshot_payload["databases"], "snapshot": snapshot_metadata},
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_path = Path(tmp_dir) / "thread_notion_attach"
            with (
                unittest.mock.patch.object(
                    service_module._db,
                    "get_system_config",
                    return_value={"workspace_enabled": True},
                ),
                unittest.mock.patch.object(
                    service_module._db,
                    "get_chat_thread",
                    return_value=None,
                ),
                unittest.mock.patch.object(
                    service_module,
                    "get_or_create_workspace",
                    return_value=workspace_path,
                ),
                unittest.mock.patch(
                    "notion.build_notion_facade",
                    return_value=_FakeFacade(),
                ) as build_notion_facade,
            ):
                execution = await service.assemble_context(
                    request,
                    state=state,
                    bus=_FakeBus(),
                    runner=unittest.mock.Mock(),
                )

            build_notion_facade.assert_called_once_with(7)
            self.assertEqual(execution.run_options.cwd, str(workspace_path))
            self.assertEqual(builder.user_message_calls[0]["cwd"], str(workspace_path))
            notion_block = workspace_context_module.build_workspace_context_block(
                str(workspace_path),
                editor_session_id="session-attach",
            )
            self.assertIn("Notion device index (.notion/):", notion_block)
            self.assertIn("Connector ID: connector-attach", notion_block)
            self.assertIn("snapshot snap-attach-001", notion_block)
            self.assertIn("Source Revision: rev-attach-001", notion_block)
            self.assertIn("Sync Cursor: cursor-attach-001", notion_block)
            self.assertIn("Last Synced: 2026-07-04T00:00:00Z", notion_block)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _parse_sse(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame[len("data: "):].strip())


class TestClaudeAgentServiceToolInputDelta(unittest.TestCase):
    def test_tool_input_delta_emits_start_then_delta_without_collecting(self):
        async def scenario():
            queue: asyncio.Queue[str] = asyncio.Queue()
            turn_ctx = _TurnContext(
                queue=queue,
                confirmation_store=ToolConfirmationStore(),
            )
            callback = ClaudeAgentService._make_tool_event_cb(queue, turn_ctx)

            await callback(
                ToolEventPayload(
                    type="tool_input_delta",
                    tool_name="Write",
                    tool_call_id="call-write",
                    output='{"file_path":"files/note.md"',
                )
            )

            first = _parse_sse(queue.get_nowait())
            second = _parse_sse(queue.get_nowait())

            return first, second, turn_ctx

        first, second, turn_ctx = _run(scenario())

        self.assertEqual(first["type"], "tool-input-start")
        self.assertEqual(first["toolCallId"], "call-write")
        self.assertEqual(first["toolName"], "Write")
        self.assertEqual(second["type"], "tool-input-delta")
        self.assertEqual(second["toolCallId"], "call-write")
        self.assertEqual(second["toolName"], "Write")
        self.assertEqual(second["delta"], '{"file_path":"files/note.md"')
        self.assertEqual(turn_ctx.collected_parts, [])


class TestClaudeAgentServiceEditorWriteEvents(unittest.TestCase):
    def test_editor_write_tool_result_publishes_session_event(self):
        async def scenario():
            queue: asyncio.Queue[str] = asyncio.Queue()
            turn_ctx = _TurnContext(
                queue=queue,
                confirmation_store=ToolConfirmationStore(),
            )
            state = AgentRunState(session_id="thread-editor-write")
            state.with_editor_state({"id": "session-editor-write"}, 7)
            callback = ClaudeAgentService._make_tool_event_cb(queue, turn_ctx, state)
            subscription = await service_module.session_event_bus.subscribe("7")

            try:
                with unittest.mock.patch.object(
                    service_module._db,
                    "get_session",
                    return_value={
                        "id": "session-editor-write",
                        "editor_state": {
                            "id": "session-editor-write",
                            "cells": [{"id": "cell-1", "type": "text", "content": "new"}],
                        },
                    },
                ) as get_session:
                    await callback(
                        ToolEventPayload(
                            type="tool_result",
                            tool_name="mcp__editor__write_segment",
                            tool_call_id="tool-call-1",
                            output={"ok": True, "cellId": "cell-1"},
                            is_error=False,
                        )
                    )

                event = await asyncio.wait_for(subscription.get(), timeout=1.0)
            finally:
                await service_module.session_event_bus.unsubscribe("7", subscription)

            self.assertEqual(get_session.call_args.args, (7, "session-editor-write"))
            self.assertEqual(event.type, "session_updated")
            self.assertEqual(event.session_id, "session-editor-write")
            self.assertEqual(event.source, "agent")
            self.assertEqual(event.tool_call_id, "tool-call-1")
            self.assertEqual(event.tool_name, "mcp__editor__write_segment")
            self.assertEqual(state.editor_state["cells"][0]["content"], "new")

        _run(scenario())


class TestClaudeAgentServiceStopCancellation(unittest.TestCase):
    def test_execute_session_cancel_flushes_partial_and_closes_stream(self):
        async def scenario():
            service = ClaudeAgentService()
            queue: asyncio.Queue[str | None] = asyncio.Queue()
            turn_ctx = _TurnContext(
                queue=queue,
                confirmation_store=ToolConfirmationStore(),
            )
            state = AgentRunState(session_id="thread-stop-service")
            request = ClaudeAgentRunRequest(
                user_id="7",
                thread_id="thread-stop-service",
                message_parts=[{"type": "text", "text": "hello"}],
            )

            class _CancelRunner:
                async def run_streaming(self, opts, callbacks):
                    del opts
                    await callbacks.on_text_delta("partial")
                    raise asyncio.CancelledError()

            execution = service_module._TurnExecution(
                request=request,
                state=state,
                runner=_CancelRunner(),
                run_options=unittest.mock.Mock(),
                turn_context=turn_ctx,
            )

            with (
                unittest.mock.patch.object(
                    service,
                    "_persist_user_message",
                    new=unittest.mock.AsyncMock(),
                ) as persist_user,
                unittest.mock.patch.object(
                    service,
                    "_persist_partial_assistant",
                    new=unittest.mock.AsyncMock(),
                ) as persist_partial,
            ):
                with self.assertRaises(asyncio.CancelledError):
                    await service.execute_session(execution)

            frames: list[str | None] = []
            while not queue.empty():
                frames.append(queue.get_nowait())
            return persist_user, persist_partial, frames

        persist_user, persist_partial, frames = _run(scenario())

        persist_user.assert_awaited_once()
        persist_partial.assert_awaited_once()
        parsed_frames = [_parse_sse(frame) for frame in frames if frame is not None]
        self.assertEqual(parsed_frames[-1]["type"], "finish")
        self.assertEqual(parsed_frames[-1]["finishReason"], "stop")
        self.assertIsNone(frames[-1])


class TestClaudeAgentServiceErrorFormatting(unittest.TestCase):
    def test_make_error_cb_includes_exception_notes(self):
        async def scenario():
            queue: asyncio.Queue[str] = asyncio.Queue()
            callback = ClaudeAgentService._make_error_cb(queue)
            exc = RuntimeError("Command failed with exit code 1")
            exc.add_note("[claude_agent_kit] sandbox_hint: apply-seccomp denied")
            await callback(exc)
            return _parse_sse(queue.get_nowait())

        frame = _run(scenario())
        self.assertEqual(frame["type"], "error")
        self.assertIn("Command failed with exit code 1", frame["errorText"])
        self.assertIn("sandbox_hint", frame["errorText"])


if __name__ == "__main__":
    unittest.main()
