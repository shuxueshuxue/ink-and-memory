# [Input] Consume ClaudeAgentRunner, AgentRunOptions, AgentStreamingCallbacks,
#         AgentRunResult from backend/libs/claude_agent_kit/runner.py and types.py.
# [Output] Verify streaming callbacks, session_id extraction, error handling,
#          on_text_done, on_tool_event, tool confirmation flow, env aliases.
# [Pos] test node in backend/tests
# [Sync] 2026-05-22: migrated from Pawkeyland scripts/test_claude_agent_runner.py.
#                    Removed: necklace/memory/touch_animation MCP tests,
#                    PAWKEYLAND_AGENT_* env mapping tests, thinking proxy tests.
#                    Adapted: module import path backend/libs/claude_agent_kit/runner.py.
# [Sync] 2026-05-24: cover INK_AGENT_MEM0_* aliases for memory MCP/hook env.
# [Sync] 2026-05-24: cover direct ANTHROPIC_AUTH_TOKEN SDK auth diagnostics.
# [Sync] 2026-05-24: assert SDK runner failures emit backend exception logs with traceback.
# [Sync] 2026-05-29: add TestEditorIndexRedirectHelper — 15 tests for _apply_editor_index_redirect
#                    module-level helper (redirect creates tempfile, updatedInput, fallthrough
#                    on None state / non-Read / non-.editor path, tmp_paths cleanup contract).
# [Sync] 2026-06-07: add PreToolUse sensitivity-policy coverage: auto mode allows
#                    explicit low-risk query tools without frontend confirmation
#                    while execution/write/state tools continue to require it.
# [Sync] 2026-06-09: cover Claude Code Skill tool low-sensitivity allow and default
#                    allowed-tools exposure.
# [Sync] 2026-06-09: cover camelCase hook payloads such as {"toolName": "Skill"}
#                    and auto-mode reinjection of required low-sensitivity tools.
# [Sync] 2026-06-09: cover Settings-controlled im_full_access_enabled forcing
#                    explicit PreToolUse allow for high-sensitivity tools.
# [Sync] 2026-06-13: cover full-access exception for AskUserQuestion-style tools
#                    so frontend answer forms still appear and populate updatedInput.
# [Sync] 2026-06-14: cover full-access/camelCase Grep workspace-boundary deny
#                    for built-in file/search tools outside thread cwd.
# [Sync] 2026-06-07: add Bash low-sensitivity and switch_editor tests; expand
#                    Bash safe-command set from {ls} to full navigation/read set.
# [Sync] 2026-06-12: cover Cloud Run/process env injection into Claude SDK
#                    subprocess options.
# [Sync] 2026-06-13: message factory helpers read SDK stub classes from the
#                    imported agent_runner module so runner tests remain
#                    order-independent when another test imported shared stubs first.
# [Sync] 2026-06-17: cover seccomp-denied sandbox hint detection for
#                    apply-seccomp/bubblewrap startup failures.
# [Sync] 2026-06-21: cover sandbox_network_mode="disabled" denying network
#                    tools before full-access or low-sensitivity allows.
# [Sync] 2026-07-20: cover EnterPlanMode/ExitPlanMode low-sensitivity allow in
#                    auto mode and frontend-confirmation side-channel in manual
#                    mode (claude-plan §5.7).
# [Sync] 2026-07-23: cover the can_use_tool channel — SDK options receive a
#                    non-None can_use_tool; SandboxNetworkAccess asks route
#                    through the confirmation side-channel; approval →
#                    PermissionResultAllow (updated_input passthrough),
#                    rejection/chain failure/missing callback →
#                    PermissionResultDeny fail-closed with the host and
#                    Settings allowedDomains remedy in the message; generic
#                    tool names route without the discriminator and merge
#                    AskUserQuestion answers.
# [Sync] 2026-07-26: remove the PreToolUse-layer network-gate tests (14 hook
#                    tests + TestSandboxNetworkDomainMatcher) and the
#                    sandbox_network_allowed_domains capture-helper param —
#                    the gate was wrong-layer duplication; can_use_tool is the
#                    single network-confirmation channel.  Disabled-mode
#                    regression tests (pre-existing) are unchanged.
# [Sync] 2026-07-26: HOTFIX — add _hook_specific() dict-aware reader (34
#                    getattr call sites replaced) and TestHookDictLiteralContract
#                    (5 tests): claude-agent-sdk 0.2.128 makes HookJSONOutput a
#                    non-callable TypedDict Union, so hooks return plain dicts;
#                    the old stub class had masked the production TypeError.

"""Tests for ClaudeAgentRunner (Ink & Memory).

Exercises the major callback paths without calling the real Claude subprocess.

Key differences from Pawkeyland:
- ClaudeAgentRunner() — original Pawkeyland API (no session_id in constructor).
- Text arrives via AssistantMessage content blocks, not StreamEvent text_delta.
- Tool confirmation is triggered by tool_use blocks (not PreToolUse hooks).
- No MCP subprocess setup; no pet/persona/necklace/memory-specific paths.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Minimal SDK stubs so tests run without claude_agent_sdk installed.
# These must be injected before importing libs.claude_agent_kit.server.agent_runner so that
# isinstance() checks in the runner resolve to the same stub classes.
# ---------------------------------------------------------------------------

import types as _types


def _make_sdk_stubs() -> None:
    """Inject lightweight stubs for claude_agent_sdk into sys.modules."""

    sdk = _types.ModuleType("claude_agent_sdk")
    sdk_types = _types.ModuleType("claude_agent_sdk.types")

    class AssistantMessage:
        def __init__(self, content=None):
            self.content = content or []

    class UserMessage:
        def __init__(self, content=None):
            self.content = content or []

    class ResultMessage:
        def __init__(self, subtype="success", session_id=None, usage=None):
            self.subtype = subtype
            self.session_id = session_id
            self.usage = usage or {}

    class StreamEvent:
        def __init__(self, event=None, session_id=None):
            self.event = event or {}
            self.session_id = session_id

    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # Additional stub classes required by the original Pawkeyland agent_runner.py
    class SystemMessage:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class HookContext:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class HookJSONOutput:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class HookMatcher:
        def __init__(self, matcher=None, hooks=None, **kwargs):
            self.matcher = matcher
            self.hooks = hooks or []
            for k, v in kwargs.items():
                setattr(self, k, v)

    class McpServerConfig:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class McpStdioServerConfig:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # can_use_tool permission types (SDK 0.0.25+)
    class PermissionResultAllow:
        def __init__(self, behavior="allow", updated_input=None, updated_permissions=None, **kwargs):
            self.behavior = behavior
            self.updated_input = updated_input
            self.updated_permissions = updated_permissions

    class PermissionResultDeny:
        def __init__(self, behavior="deny", message="", interrupt=False, **kwargs):
            self.behavior = behavior
            self.message = message
            self.interrupt = interrupt

    class ToolPermissionContext:
        def __init__(self, signal=None, suggestions=None, **kwargs):
            self.signal = signal
            self.suggestions = suggestions or []

    for _cls in [
        AssistantMessage,
        UserMessage,
        ResultMessage,
        StreamEvent,
        ClaudeAgentOptions,
        SystemMessage,
        HookContext,
        HookJSONOutput,
        HookMatcher,
        McpServerConfig,
        McpStdioServerConfig,
        PermissionResultAllow,
        PermissionResultDeny,
        ToolPermissionContext,
    ]:
        setattr(sdk_types, _cls.__name__, _cls)

    sdk_types.PermissionResult = (PermissionResultAllow, PermissionResultDeny)

    async def _noop_query(*args, **kwargs):
        return
        yield  # make it an async generator  # noqa: unreachable

    sdk.query = _noop_query
    sdk.ClaudeSDKClient = object
    sdk.types = sdk_types
    sys.modules["claude_agent_sdk"] = sdk
    sys.modules["claude_agent_sdk.types"] = sdk_types


_make_sdk_stubs()


def _hook_specific(result, default=None):
    """Read ``hookSpecificOutput`` from a PreToolUse/PostToolUse hook result.

    claude-agent-sdk 0.2.128 makes ``HookJSONOutput`` a Union of TypedDicts
    (types.py:561) — NOT callable — so hook callbacks return plain dicts
    (``{}`` no-op, ``{"hookSpecificOutput": {...}}`` for decisions).  Older
    tests used stub class instances with attribute access; accept both so
    assertions work regardless of which shape a helper produced.
    """
    if isinstance(result, dict):
        return result.get("hookSpecificOutput", default)
    return getattr(result, "hookSpecificOutput", default)


# ---------------------------------------------------------------------------
# Now import the modules under test (after stubs are in place)
# ---------------------------------------------------------------------------

import libs.claude_agent_kit.server.agent_runner as agent_runner_module  # noqa: E402
import libs.claude_agent_kit.server.sdk_env as sdk_env_module  # noqa: E402
from libs.claude_agent_kit.server.agent_runner import ClaudeAgentRunner  # noqa: E402
from libs.claude_agent_kit.types import (  # noqa: E402
    AgentRunOptions,
    AgentStreamingCallbacks,
    AgentRunResult,
    ToolEventPayload,
)

# ---------------------------------------------------------------------------
# Message factory helpers — wrap stub classes for test convenience.
# Grabbed after runner import so the classes match the runner's isinstance refs.
# ---------------------------------------------------------------------------

_SDK_ASSISTANT = agent_runner_module.AssistantMessage
_SDK_HOOK_CONTEXT = agent_runner_module.HookContext
_SDK_OPTIONS = agent_runner_module.ClaudeAgentOptions
_SDK_RESULT = agent_runner_module.ResultMessage
_SDK_STREAM_EVENT = agent_runner_module.StreamEvent
_SDK_USER = agent_runner_module.UserMessage


def AssistantMessage(content=None):
    return _SDK_ASSISTANT(content or [])


def ResultMessage(session_id=None, subtype="success", usage=None):
    return _SDK_RESULT(subtype=subtype, session_id=session_id, usage=usage)


def StreamEvent(event=None, session_id=None):
    return _SDK_STREAM_EVENT(event=event or {}, session_id=session_id)


def UserMessage(content=None):
    return _SDK_USER(content or [])


def _text_block(text: str):
    """Return a minimal text content block stub (for AssistantMessage)."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _text_delta_event(text: str, index: int = 0):
    """Return a StreamEvent carrying a content_block_delta text_delta.

    Original agent_runner.py dispatches on_text_delta from StreamEvent
    content_block_delta events (include_partial_messages=True by default).
    """
    return StreamEvent(event={
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": text},
    })


def _tool_use_block(tool_name: str, tool_input: dict, tool_id: str = "tu-1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    return block


def _make_fake_query(messages: list):
    """Return an async generator function that yields the given messages."""
    async def _fake(*args, **kwargs):
        for msg in messages:
            yield msg
    return _fake


# ---------------------------------------------------------------------------
# Mock SDK client — injected into ClaudeAgentRunner(sdk_client=...) so no
# real subprocess is launched during tests.
# ---------------------------------------------------------------------------

_FAKE_WORKSPACE = Path("/tmp/ink-agent-tests")


class _MockSDKClient:
    """Minimal IClaudeAgentSDKClient implementation for testing.

    Call ``set_messages()`` before each ``run_streaming`` to configure
    what the fake query stream should yield.
    """

    def __init__(self):
        self._messages: list = []
        self.last_options = None

    def set_messages(self, messages: list) -> None:
        self._messages = list(messages)

    async def query_stream(self, prompt, options=None):
        self.last_options = options
        for msg in self._messages:
            yield msg

    async def load_messages(self, session_id=None):
        return {"messages": []}


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------


class _RunnerBase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self._mock_client = _MockSDKClient()
        # Bypass the real auth-key check: these tests exercise runner logic,
        # not env propagation (see TestClaudeAgentRunnerSdkEnvDiagnostics).
        self._verify_patch = patch.object(
            agent_runner_module,
            "_verify_claude_sdk_env_for_query_stream",
        )
        self._verify_patch.start()

    def tearDown(self):
        self._verify_patch.stop()

    def make_runner(self, session_id: str = "test-session") -> ClaudeAgentRunner:
        return ClaudeAgentRunner(sdk_client=self._mock_client)

    def set_query(self, messages: list) -> None:
        """Configure the mock SDK client to yield the given messages."""
        self._mock_client.set_messages(messages)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClaudeAgentRunnerBasicText(_RunnerBase):
    """Basic text streaming — text arrives via StreamEvent content_block_delta.

    Original runner uses include_partial_messages=True by default, so text is
    dispatched from StreamEvent text_delta events, not AssistantMessage blocks.
    """

    async def test_on_text_delta_called_and_result_contains_full_text(self):
        self.set_query([
            _text_delta_event("Hello"),
            _text_delta_event(" World"),
        ])
        runner = self.make_runner()
        received: list[str] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="test-session-001",
                user_message="请用 Python 写一个 Hello World",
                max_turns=10,
                tool_choice="none",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: received.append(d),
            ),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.full_text, "Hello World")
        self.assertEqual(received, ["Hello", " World"])


class TestClaudeAgentRunnerOnTextDone(_RunnerBase):
    """on_text_done receives the concatenated full text after streaming."""

    async def test_on_text_done_receives_full_text(self):
        self.set_query([
            _text_delta_event("foo"),
            _text_delta_event("bar"),
        ])
        runner = self.make_runner()
        done_texts: list[str] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="td-001",
                user_message="hi",
                tool_choice="none",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_text_done=lambda t: done_texts.append(t),
            ),
        )

        self.assertEqual(done_texts, ["foobar"])
        self.assertEqual(result.full_text, "foobar")


class TestClaudeAgentRunnerSessionId(_RunnerBase):
    """session_id is extracted from ResultMessage."""

    async def test_session_id_from_result_message(self):
        self.set_query([ResultMessage(session_id="sess-xyz")])
        runner = self.make_runner()

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="any",
                user_message="ping",
                tool_choice="none",
            ),
            callbacks=AgentStreamingCallbacks(on_text_delta=lambda d: None),
        )

        self.assertEqual(result.session_id, "sess-xyz")


class TestClaudeAgentRunnerOnToolEvent(_RunnerBase):
    """on_tool_event is fired for tool_use blocks in AssistantMessage."""

    async def test_tool_use_fires_on_tool_event(self):
        self.set_query([
            AssistantMessage([
                _tool_use_block("Bash", {"command": "ls"}, tool_id="tu-42"),
            ]),
        ])
        runner = self.make_runner()
        tool_events: list[ToolEventPayload] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="te-001",
                user_message="list files",
                tool_choice="auto",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_event=lambda e: tool_events.append(e),
            ),
        )

        self.assertTrue(result.success)
        tool_use_events = [e for e in tool_events if e.type == "tool_use"]
        self.assertEqual(len(tool_use_events), 1)
        ev = tool_use_events[0]
        self.assertEqual(ev.tool_name, "Bash")
        self.assertEqual(ev.tool_call_id, "tu-42")
        self.assertEqual(ev.input, {"command": "ls"})

    async def test_multiple_tool_use_blocks_all_fire_events(self):
        """Multiple tool_use blocks in one AssistantMessage each fire on_tool_event."""
        self.set_query([
            AssistantMessage([
                _tool_use_block("Bash", {"command": "ls"}, tool_id="tu-1"),
                _tool_use_block("Read", {"file_path": "/tmp/x.txt"}, tool_id="tu-2"),
            ]),
        ])
        runner = self.make_runner()
        tool_events: list[ToolEventPayload] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="te-multi-001",
                user_message="list and read",
                tool_choice="auto",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_event=lambda e: tool_events.append(e),
            ),
        )

        self.assertTrue(result.success)
        tool_use_events = [e for e in tool_events if e.type == "tool_use"]
        self.assertEqual(len(tool_use_events), 2)
        names = {e.tool_name for e in tool_use_events}
        self.assertEqual(names, {"Bash", "Read"})


class TestClaudeAgentRunnerStreamEvent(_RunnerBase):
    """StreamEvent handling — original runner dispatches text from StreamEvents.

    Original Pawkeyland agent_runner.py uses include_partial_messages=True by
    default, so text_delta StreamEvents are the primary text dispatch path.
    """

    async def test_stream_event_text_delta_is_dispatched(self):
        """Runner dispatches on_text_delta from StreamEvent content_block_delta.

        Original runner with include_partial_messages=True dispatches text
        via StreamEvent text_delta, not via AssistantMessage text blocks.
        """
        self.set_query([
            StreamEvent(
                event={
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "streamed text"},
                },
                session_id="stream-sess",
            ),
        ])
        runner = self.make_runner()
        received: list[str] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="se-001",
                user_message="hello",
                tool_choice="none",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: received.append(d),
            ),
        )

        self.assertTrue(result.success)
        self.assertEqual(received, ["streamed text"])

    async def test_stream_event_thinking_delta_fires_tool_event(self):
        """thinking_delta StreamEvents are dispatched as thinking_delta tool events.

        Original runner accumulates thinking blocks by index and dispatches
        them as ToolEventPayload(type='thinking_delta').
        """
        self.set_query([
            StreamEvent(event={
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": "", "signature": ""},
            }),
            StreamEvent(event={
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "The"},
            }),
            StreamEvent(event={
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": " user"},
            }),
            StreamEvent(event={
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "signature_delta",
                    "signature": "3f1a1344-dece-4409-8d44-097891e0cd01",
                },
            }),
            StreamEvent(event={"type": "content_block_stop", "index": 0}),
        ])
        runner = self.make_runner()
        tool_events: list[ToolEventPayload] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="se-thinking-001",
                user_message="hello",
                tool_choice="none",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_event=lambda e: tool_events.append(e),
            ),
        )

        self.assertTrue(result.success)
        # thinking_delta StreamEvents are dispatched as tool events by the original runner
        thinking_events = [e for e in tool_events if e.type == "thinking_delta"]
        self.assertGreater(len(thinking_events), 0, "Expected thinking_delta tool events")


def _runner_with_error_query(exc):
    """Return a ClaudeAgentRunner whose SDK client raises *exc* on query_stream."""

    class _ErrorClient(_MockSDKClient):
        async def query_stream(self, prompt, options=None):
            raise exc
            yield  # pragma: no cover

    return ClaudeAgentRunner(sdk_client=_ErrorClient())


def _runner_with_exception_group(exceptions):
    """Return a runner that raises a BaseExceptionGroup from query_stream."""

    class _GroupClient(_MockSDKClient):
        async def query_stream(self, prompt, options=None):
            raise BaseExceptionGroup("test group", list(exceptions))
            yield  # pragma: no cover

    return ClaudeAgentRunner(sdk_client=_GroupClient())


class TestSandboxFailureHintHelper(unittest.TestCase):
    def test_apply_seccomp_permission_denied_returns_hint(self):
        hint = agent_runner_module._sandbox_runtime_failure_hint(
            "Command failed with exit code 1",
            "apply-seccomp: Permission denied",
        )
        self.assertIsNotNone(hint)
        self.assertIn("apply seccomp", hint.lower())

    def test_unrelated_error_returns_none(self):
        hint = agent_runner_module._sandbox_runtime_failure_hint(
            "Command failed with exit code 1",
            "npm: command not found",
        )
        self.assertIsNone(hint)


class TestClaudeAgentRunnerErrorHandling(_RunnerBase):
    """Errors from the SDK are caught and reported via on_error."""

    async def test_sdk_error_sets_success_false(self):
        boom = RuntimeError("sdk exploded")
        runner = _runner_with_error_query(boom)
        errors: list[Exception] = []

        with self.assertLogs(agent_runner_module.logger, level="ERROR") as log_cm:
            result = await runner.run_streaming(
                opts=AgentRunOptions(
                    thread_id="err-001",
                    user_message="explode",
                    tool_choice="none",
                ),
                callbacks=AgentStreamingCallbacks(
                    on_text_delta=lambda d: None,
                    on_error=lambda e: errors.append(e),
                ),
            )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(len(log_cm.records), 1)
        self.assertIn("Claude SDK run failed", log_cm.output[0])
        self.assertIsNotNone(log_cm.records[0].exc_info)
        self.assertIs(log_cm.records[0].exc_info[1], boom)

    async def test_base_exception_group_with_cli_failure_fires_on_error(self):
        """anyio TaskGroup wraps CLI failure + sibling CancelledError into a
        BaseExceptionGroup; runner must fire on_error and return success=False.
        """
        cli_failure = Exception("Command failed with exit code 1")
        runner = _runner_with_exception_group([cli_failure, asyncio.CancelledError()])
        errors: list[Exception] = []

        with self.assertLogs(agent_runner_module.logger, level="ERROR") as log_cm:
            result = await runner.run_streaming(
                opts=AgentRunOptions(
                    thread_id="err-base-group-001",
                    user_message="explode",
                    tool_choice="none",
                ),
                callbacks=AgentStreamingCallbacks(
                    on_text_delta=lambda d: None,
                    on_error=lambda e: errors.append(e),
                ),
            )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(len(errors), 1)
        # Group is flattened to a readable plain Exception (not a group).
        self.assertNotIsInstance(errors[0], BaseExceptionGroup)
        self.assertIsInstance(errors[0], Exception)
        self.assertIn("Command failed with exit code 1", str(errors[0]))
        self.assertEqual(len(log_cm.records), 1)
        self.assertIn("Claude SDK run failed", log_cm.output[0])
        self.assertIsNotNone(log_cm.records[0].exc_info)
        self.assertIsInstance(log_cm.records[0].exc_info[1], BaseExceptionGroup)

    async def test_pure_cancellation_group_is_reraised(self):
        """A BaseExceptionGroup whose every leaf is CancelledError is a true outer
        cancel (FastAPI shutdown / client disconnect / explicit task.cancel()) and
        must propagate so the surrounding task hierarchy unwinds correctly.
        on_error must NOT fire and run_streaming must NOT return an AgentRunResult.

        The current runner's ``except Exception`` does not catch BaseExceptionGroup,
        so pure-cancellation groups already propagate correctly.
        """

        runner = _runner_with_exception_group([asyncio.CancelledError(), asyncio.CancelledError()])
        errors: list[Exception] = []

        with self.assertRaises(BaseExceptionGroup):
            await runner.run_streaming(
                opts=AgentRunOptions(
                    thread_id="cancel-001",
                    user_message="cancel",
                    tool_choice="none",
                ),
                callbacks=AgentStreamingCallbacks(
                    on_text_delta=lambda d: None,
                    on_error=lambda e: errors.append(e),
                ),
            )

        self.assertEqual(errors, [])

    async def test_bare_cancelled_error_is_reraised(self):
        """A bare CancelledError (legacy cancellation path) must propagate untouched.
        The runner's ``except Exception`` does not catch CancelledError (BaseException),
        so it re-raises correctly.
        """

        runner = _runner_with_error_query(asyncio.CancelledError())
        errors: list[Exception] = []

        with self.assertRaises(asyncio.CancelledError):
            await runner.run_streaming(
                opts=AgentRunOptions(
                    thread_id="cancel-bare-001",
                    user_message="cancel",
                    tool_choice="none",
                ),
                callbacks=AgentStreamingCallbacks(
                    on_text_delta=lambda d: None,
                    on_error=lambda e: errors.append(e),
                ),
            )

        self.assertEqual(errors, [])


class TestClaudeAgentRunnerToolConfirmation(_RunnerBase):
    """Tool confirmation callback is invoked when tool_choice='manual'."""

    @unittest.skip(
        "Tool confirmation uses PreToolUse SDK hooks which require a real Claude Code "
        "SDK subprocess. Mock query_stream yields AssistantMessage snapshots (post-execution) "
        "and cannot trigger PreToolUse hooks. Test requires real SDK integration."
    )
    async def test_tool_confirmation_callback_is_called(self):
        """on_tool_confirmation_request is wired to the PreToolUse SDK hook.

        This test is skipped in unit testing because PreToolUse fires before tool
        execution inside the real Claude Code SDK subprocess; a mock client that
        yields AssistantMessage snapshots cannot trigger it.
        See libs/claude_agent_kit/server/agent_runner.py _pre_tool_use_hook for
        the implementation.
        """
        pass  # skipped

    async def test_post_execution_snapshot_does_not_trigger_pretool_confirmation(self):
        """Mock AssistantMessage snapshots do not exercise PreToolUse hooks."""
        self.set_query([
            AssistantMessage([
                _tool_use_block("Bash", {"command": "ls"}, tool_id="tu-auto-1"),
            ]),
        ])
        runner = self.make_runner()
        confirmation_requests: list[dict] = []

        result = await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="tc-auto-001",
                user_message="list",
                tool_choice="auto",
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_confirmation_request=lambda p: confirmation_requests.append(p),
            ),
        )

        self.assertTrue(result.success)
        self.assertEqual(confirmation_requests, [])


class TestClaudeAgentRunnerPreToolUsePolicy(_RunnerBase):
    """PreToolUse policy branches that can be exercised through SDK hooks."""

    async def _capture_pre_tool_use_hook(
        self,
        *,
        cwd: str,
        tool_choice: str = "auto",
        allowed_tools: Optional[list[str]] = None,
        im_full_access_enabled: bool = False,
        sandbox_network_mode: str = "allowlist",
        on_tool_confirmation_request=None,
    ):
        self.set_query([])
        runner = self.make_runner()

        await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="pretool-policy-001",
                user_message="write a workspace file",
                cwd=cwd,
                tool_choice=tool_choice,  # type: ignore[arg-type]
                allowed_tools=allowed_tools,
                im_full_access_enabled=im_full_access_enabled,
                sandbox_network_mode=sandbox_network_mode,  # type: ignore[arg-type]
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_confirmation_request=on_tool_confirmation_request,
            ),
        )

        options = self._mock_client.last_options
        matcher = options.hooks["PreToolUse"][0]
        return matcher.hooks[0]

    async def test_auto_write_under_workspace_files_gets_explicit_allow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            target = workspace / "files" / "hello.md"
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": str(target),
                        "content": "# hello\n",
                    },
                },
                "call-write-files",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")
        self.assertNotIn("updatedInput", specific)

    async def test_auto_relative_write_under_workspace_files_gets_explicit_allow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "files/hello.md",
                        "content": "# hello\n",
                    },
                },
                "call-write-relative-files",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_write_outside_workspace_files_without_callback_denies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": str(workspace / "outside.md"),
                        "content": "# outside\n",
                    },
                },
                "call-write-outside",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "需要用户确认但未收到响应")

    async def test_auto_write_path_traversal_out_of_files_without_callback_denies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "files/../outside.md",
                        "content": "# outside\n",
                    },
                },
                "call-write-traversal",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "需要用户确认但未收到响应")

    async def test_auto_read_inside_workspace_root_gets_query_allow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "thread-1"
            workspace.mkdir()
            (workspace / "files").mkdir()
            target = workspace / "notes.md"
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(target)},
                },
                "call-read-inside-workspace",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")
        self.assertNotIn("updatedInput", specific)

    async def test_auto_read_outside_workspace_root_is_hard_denied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "thread-1"
            sibling = root / "thread-2"
            workspace.mkdir()
            sibling.mkdir()
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(sibling / "notes.md")},
                },
                "call-read-outside-workspace",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertIn("current thread workspace", specific.get("permissionDecisionReason", ""))

    async def test_auto_grep_outside_workspace_root_is_hard_denied(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "thread-1"
            outside = root / "thread-2"
            workspace.mkdir()
            outside.mkdir()
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Grep",
                    "tool_input": {"pattern": "hello", "path": str(outside)},
                },
                "call-grep-outside-workspace",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertIn("current thread workspace", specific.get("permissionDecisionReason", ""))

    async def test_full_access_grep_outside_workspace_root_is_hard_denied(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "thread-1"
            outside = Path(temp_dir) / "source-root" / "backend"
            workspace.mkdir()
            outside.mkdir(parents=True)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="auto",
                im_full_access_enabled=True,
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Grep",
                    "tool_input": {
                        "pattern": "from.*libs",
                        "path": str(outside),
                        "glob": "*.py",
                    },
                },
                "call-grep-full-access-outside-workspace",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertIn("current thread workspace", specific.get("permissionDecisionReason", ""))

    async def test_camel_case_grep_outside_workspace_root_is_hard_denied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "thread-1"
            outside = Path(temp_dir) / "source-root" / "backend"
            workspace.mkdir()
            outside.mkdir(parents=True)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="auto",
                im_full_access_enabled=True,
            )

            result = await hook(
                {
                    "toolName": "Grep",
                    "toolInput": {
                        "pattern": "backend\\.libs",
                        "path": str(outside),
                    },
                },
                "call-grep-camel-outside-workspace",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertIn("current thread workspace", specific.get("permissionDecisionReason", ""))

    async def test_auto_grep_gets_query_allow_without_confirmation(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Grep",
                    "tool_input": {"pattern": "hello", "path": str(workspace)},
                },
                "call-grep-query",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_sessions_range_mcp_gets_query_allow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(cwd=str(workspace))

            result = await hook(
                {
                    "tool_name": "mcp__user__get_sessions_range",
                    "tool_input": {"start": 0, "limit": 20},
                },
                "call-sessions-query",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_bash_uses_frontend_confirmation_and_approval_allows(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "echo hello > files/hello.md",
                    },
                },
                "call-bash-auto-confirm",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "Bash")
        self.assertEqual(
            confirmation_requests[0]["input"],
            {"command": "echo hello > files/hello.md"},
        )
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_bash_confirmation_rejection_denies(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "needs review"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "echo hello > files/hello.md",
                    },
                },
                "call-bash-auto-reject",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "needs review")

    async def test_auto_bash_low_sensitivity_commands_get_query_allow(self):
        """Bash read-only/navigation commands bypass confirmation in auto mode."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            safe_commands = [
                "ls",
                "ls -la",
                "ls /tmp",
                "cd /tmp",
                "cd ..",
                "pwd",
                "echo hello",
                "cat notes.md",
                "head -n 20 file.txt",
                "tail -f log.txt",
                "wc -l file.txt",
                "find . -name '*.py'",
                "which python",
                "date",
                "whoami",
                "uname -a",
                "hostname",
            ]
            for command in safe_commands:
                with self.subTest(command=command):
                    result = await hook(
                        {
                            "tool_name": "Bash",
                            "tool_input": {"command": command},
                        },
                        f"call-bash-safe-{command[:20]}",
                        _SDK_HOOK_CONTEXT(),
                    )
                    self.assertEqual(confirmation_requests, [], f"Should not confirm for: {command!r}")
                    specific = _hook_specific(result, {})
                    self.assertEqual(specific.get("hookEventName"), "PreToolUse")
                    self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_disabled_sandbox_network_denies_webfetch_before_full_access(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                im_full_access_enabled=True,
                sandbox_network_mode="disabled",
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://example.com"},
                },
                "call-webfetch-network-disabled",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertIn("代理网络访问已关闭", specific.get("permissionDecisionReason", ""))

    async def test_disabled_sandbox_network_denies_network_bash_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                sandbox_network_mode="disabled",
            )

            network_commands = [
                "curl https://example.com",
                "wget https://example.com/archive.tgz",
                "git fetch origin",
                "npm install",
                "python -m pip install requests",
                "env HTTPS_PROXY=http://proxy.local curl https://example.com",
            ]
            for command in network_commands:
                with self.subTest(command=command):
                    result = await hook(
                        {
                            "tool_name": "Bash",
                            "tool_input": {"command": command},
                        },
                        f"call-bash-disabled-{command[:20]}",
                        _SDK_HOOK_CONTEXT(),
                    )
                    specific = _hook_specific(result, {})
                    self.assertEqual(specific.get("hookEventName"), "PreToolUse")
                    self.assertEqual(specific.get("permissionDecision"), "deny")
                    self.assertIn(
                        "代理网络访问已关闭",
                        specific.get("permissionDecisionReason", ""),
                    )

    async def test_disabled_sandbox_network_still_allows_local_safe_bash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                sandbox_network_mode="disabled",
            )

            result = await hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls -la"},
                },
                "call-local-bash-network-disabled",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_bash_with_metachar_uses_frontend_confirmation(self):
        """Bash command with shell metachar is NOT low-sensitivity — falls to confirmation."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls | grep foo"},
                },
                "call-bash-ls-pipe",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "Bash")
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_switch_editor_gets_query_allow_without_confirmation(self):
        """mcp__editor__switch_editor is low-sensitivity and bypasses confirmation."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "mcp__editor__switch_editor",
                    "tool_input": {"editor_session_id": "sess-abc123"},
                },
                "call-switch-editor",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_plan_mode_tools_get_query_allow_without_confirmation(self):
        """EnterPlanMode/ExitPlanMode are low-sensitivity in auto mode (claude-plan §5.7)."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            for tool_name in ("EnterPlanMode", "ExitPlanMode"):
                with self.subTest(tool_name=tool_name):
                    result = await hook(
                        {
                            "tool_name": tool_name,
                            "tool_input": {},
                        },
                        f"call-{tool_name.lower()}-auto",
                        _SDK_HOOK_CONTEXT(),
                    )
                    self.assertEqual(confirmation_requests, [])
                    specific = _hook_specific(result, {})
                    self.assertEqual(specific.get("hookEventName"), "PreToolUse")
                    self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_manual_plan_mode_tools_use_frontend_confirmation(self):
        """manual mode keeps EnterPlanMode/ExitPlanMode on the confirmation side-channel."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="manual",
                on_tool_confirmation_request=confirm,
            )

            for tool_name in ("EnterPlanMode", "ExitPlanMode"):
                with self.subTest(tool_name=tool_name):
                    result = await hook(
                        {
                            "tool_name": tool_name,
                            "tool_input": {},
                        },
                        f"call-{tool_name.lower()}-manual",
                        _SDK_HOOK_CONTEXT(),
                    )
                    specific = _hook_specific(result, {})
                    self.assertEqual(specific.get("permissionDecision"), "allow")

        self.assertEqual(
            [p["tool_name"] for p in confirmation_requests],
            ["EnterPlanMode", "ExitPlanMode"],
        )

    async def test_auto_skill_tool_gets_query_allow_without_confirmation(self):
        """Claude Code's built-in Skill tool is low-sensitivity in auto mode."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Skill",
                    "tool_input": {"name": "doc-coauthoring", "arguments": ""},
                },
                "call-skill-tool",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_auto_skill_tool_camel_case_hook_payload_gets_allow(self):
        """SDK/control payloads with toolName/toolInput still bypass confirmation."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "toolName": "Skill",
                    "toolInput": {"skill": "doc-coauthoring", "args": ""},
                },
                "call-skill-tool",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_skill_tool_is_in_default_allowed_tools(self):
        self.assertIn("Skill", agent_runner_module.DEFAULT_ALLOWED_TOOLS)

    async def test_auto_mode_reinserts_skill_when_allowed_tools_override_omits_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                allowed_tools=[],
            )

        options = self._mock_client.last_options
        self.assertIn("Skill", options.allowed_tools)

    async def test_none_mode_does_not_reinsert_skill(self):
        self.set_query([])
        runner = self.make_runner()

        await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="pretool-policy-none-skill",
                user_message="no tools",
                tool_choice="none",
                allowed_tools=[],
            ),
            callbacks=AgentStreamingCallbacks(on_text_delta=lambda d: None),
        )

        options = self._mock_client.last_options
        self.assertEqual(options.allowed_tools, [])

    async def test_full_access_allows_high_sensitivity_tool_without_confirmation(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "should not ask"}

        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                tool_choice="auto",
                im_full_access_enabled=True,
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python - <<'PY'\nprint('mutating command')\nPY"},
                },
                "call-bash-full-access",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(confirmation_requests, [])
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")

    async def test_full_access_ask_user_question_still_uses_confirmation_form(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {
                "approved": True,
                "answers": {"q1": "yes"},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                tool_choice="auto",
                im_full_access_enabled=True,
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "AskUserQuestion",
                    "tool_input": {
                        "questions": [
                            {"id": "q1", "question": "Continue?"},
                        ],
                    },
                },
                "call-ask-user-full-access",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "AskUserQuestion")
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")
        self.assertEqual(specific.get("permissionDecision"), "allow")
        self.assertEqual(
            specific.get("updatedInput"),
            {
                "questions": [
                    {"id": "q1", "question": "Continue?"},
                ],
                "answers": {"q1": "yes"},
            },
        )

    async def test_full_access_mcp_ask_user_still_uses_confirmation_form(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {
                "approved": True,
                "answers": {"choice": "confirm"},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            hook = await self._capture_pre_tool_use_hook(
                cwd=temp_dir,
                tool_choice="auto",
                im_full_access_enabled=True,
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "mcp__user__ask_user",
                    "tool_input": {
                        "questions": [
                            {"id": "choice", "question": "Confirm?"},
                        ],
                    },
                },
                "call-mcp-ask-user-full-access",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "mcp__user__ask_user")
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "allow")
        self.assertEqual(
            specific.get("updatedInput", {}).get("answers"),
            {"choice": "confirm"},
        )

    async def test_manual_read_still_uses_confirmation(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "manual review"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="manual",
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(workspace / "notes.md")},
                },
                "call-read-manual",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "Read")
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "manual review")

    async def test_none_mode_does_not_apply_auto_query_allow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="none",
            )

            result = await hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(workspace / "notes.md")},
                },
                "call-read-none",
                _SDK_HOOK_CONTEXT(),
            )

        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "需要用户确认但未收到响应")

    async def test_manual_write_under_workspace_files_still_uses_confirmation(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": False, "reason": "manual mode"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hook = await self._capture_pre_tool_use_hook(
                cwd=str(workspace),
                tool_choice="manual",
                on_tool_confirmation_request=confirm,
            )

            result = await hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": str(workspace / "files" / "hello.md"),
                        "content": "# hello\n",
                    },
                },
                "call-write-manual-files",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertEqual(len(confirmation_requests), 1)
        self.assertEqual(confirmation_requests[0]["tool_name"], "Write")
        specific = _hook_specific(result, {})
        self.assertEqual(specific.get("permissionDecision"), "deny")
        self.assertEqual(specific.get("permissionDecisionReason"), "manual mode")


class TestClaudeAgentRunnerMemoryEnvAliases(unittest.TestCase):
    """Memory MCP env uses Ink-owned names with Pawkeyland aliases as fallback."""

    def test_ink_memory_mcp_disable_flag_takes_precedence(self):
        with patch.dict(
            os.environ,
            {
                "INK_AGENT_ENABLE_MEMORY_MCP": "0",
                "PAWKEYLAND_ENABLE_AGENT_MEMORY_MCP": "1",
            },
            clear=True,
        ):
            self.assertFalse(agent_runner_module._memory_mcp_enabled())

    def test_mem0_hook_env_maps_ink_names_and_legacy_aliases(self):
        options = _SDK_OPTIONS(env={})
        request_env = {
            "INK_AGENT_MEM0_USER_ID": "ink-memory-user",
            "INK_AGENT_USER_MESSAGE": "remember this",
        }

        with patch.dict(
            os.environ,
            {
                "INK_AGENT_MEM0_API_KEY": "ink-mem0-key",
                "INK_AGENT_MEM0_API_HOST": "https://mem0.example",
                "INK_AGENT_MEM0_TOP_K": "7",
            },
            clear=True,
        ):
            agent_runner_module._inject_mem0_session_hook_env(options, request_env)

        self.assertEqual(options.env["MEM0_USER_ID"], "ink-memory-user")
        self.assertNotIn("INK_AGENT_MEM0_USER_ID", options.env)
        self.assertNotIn("PAWKEYLAND_MEM0_USER_ID", options.env)
        self.assertEqual(options.env["INK_AGENT_MEM0_API_KEY"], "ink-mem0-key")
        self.assertEqual(options.env["PAWKEYLAND_MEM0_API_KEY"], "ink-mem0-key")
        self.assertEqual(options.env["INK_AGENT_USER_MESSAGE"], "remember this")
        self.assertEqual(options.env["PAWKEYLAND_AGENT_USER_MESSAGE"], "remember this")


class TestClaudeAgentRunnerSdkEnvDiagnostics(unittest.TestCase):
    """SDK env diagnostics use direct Anthropic credentials."""

    def test_anthropic_auth_token_counts_as_auth(self):
        options = _SDK_OPTIONS(env={"ANTHROPIC_AUTH_TOKEN": "sk-test"})

        with patch.object(agent_runner_module.logger, "warning") as warning:
            agent_runner_module._verify_claude_sdk_env_for_query_stream(options)

        warning.assert_not_called()

    def test_missing_auth_warns_and_raises_for_anthropic_auth_token(self):
        options = _SDK_OPTIONS(env={})

        with patch.object(agent_runner_module.logger, "warning") as warning:
            with self.assertRaises(RuntimeError) as ctx:
                agent_runner_module._verify_claude_sdk_env_for_query_stream(options)

        warning.assert_called_once()
        warning_args = warning.call_args.args
        self.assertIn("has no auth key", warning_args[0])
        self.assertIn("ANTHROPIC_AUTH_TOKEN", warning_args[2])
        self.assertIn("no auth key", str(ctx.exception))


class TestClaudeSdkEnvHelper(unittest.TestCase):
    """Project dotenv loading only forwards SDK-level keys."""

    def test_project_dotenv_env_filters_non_sdk_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "ANTHROPIC_AUTH_TOKEN=sk-test",
                        "ANTHROPIC_API_KEY=legacy-test",
                        "API_TIMEOUT_MS=1000",
                        "INK_AGENT_MEM0_API_KEY=mem0-test",
                        "INK_AGENT_TTL_S=600",
                    ]
                ),
                encoding="utf-8",
            )

            loaded = sdk_env_module.project_dotenv_env(env_file)

        self.assertEqual(
            loaded,
            {
                "ANTHROPIC_AUTH_TOKEN": "sk-test",
                "API_TIMEOUT_MS": "1000",
            },
        )

    def test_merge_project_dotenv_env_removes_legacy_api_key_override(self):
        loaded = sdk_env_module.merge_project_dotenv_env(
            {"ANTHROPIC_API_KEY": "legacy-test", "ANTHROPIC_AUTH_TOKEN": "sk-test"},
            env_file=Path("/tmp/does-not-exist"),
            process_env={},
        )

        self.assertEqual(loaded, {"ANTHROPIC_AUTH_TOKEN": "sk-test"})

    def test_merge_project_dotenv_env_includes_process_sdk_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "ANTHROPIC_MODEL=dotenv-model",
                        "ANTHROPIC_BASE_URL=https://dotenv.example",
                    ]
                ),
                encoding="utf-8",
            )

            loaded = sdk_env_module.merge_project_dotenv_env(
                {"API_TIMEOUT_MS": "5000"},
                env_file=env_file,
                process_env={
                    "ANTHROPIC_AUTH_TOKEN": "cloud-secret-token",
                    "ANTHROPIC_BASE_URL": "https://cloud.example",
                    "INK_AGENT_TTL_S": "600",
                    "ANTHROPIC_API_KEY": "legacy-test",
                },
            )

        self.assertEqual(
            loaded,
            {
                "ANTHROPIC_MODEL": "dotenv-model",
                "ANTHROPIC_BASE_URL": "https://cloud.example",
                "ANTHROPIC_AUTH_TOKEN": "cloud-secret-token",
                "API_TIMEOUT_MS": "5000",
            },
        )

    def test_merge_project_dotenv_env_keeps_existing_env_highest_priority(self):
        loaded = sdk_env_module.merge_project_dotenv_env(
            {"ANTHROPIC_AUTH_TOKEN": "explicit-token"},
            env_file=Path("/tmp/does-not-exist"),
            process_env={"ANTHROPIC_AUTH_TOKEN": "cloud-secret-token"},
        )

        self.assertEqual(loaded, {"ANTHROPIC_AUTH_TOKEN": "explicit-token"})

    def test_apply_project_dotenv_to_options_reads_process_env_by_default(self):
        options = _SDK_OPTIONS()

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_AUTH_TOKEN": "cloud-secret-token",
                "ANTHROPIC_MODEL": "cloud-model",
                "INK_AGENT_TTL_S": "600",
            },
            clear=True,
        ):
            sdk_env_module.apply_project_dotenv_to_options(
                options,
                env_file=Path("/tmp/does-not-exist"),
            )

        self.assertEqual(
            options.env,
            {
                "ANTHROPIC_AUTH_TOKEN": "cloud-secret-token",
                "ANTHROPIC_MODEL": "cloud-model",
            },
        )


# ---------------------------------------------------------------------------
# TestEditorIndexRedirectHelper
# ---------------------------------------------------------------------------


class TestEditorIndexRedirectHelper(unittest.TestCase):
    """Unit tests for _apply_editor_index_redirect (module-level helper).

    This helper is extracted from the .editor/ PreToolUse interception block
    so it can be tested without a real Claude Code SDK subprocess.

    Design reference:
        docs/design/claude-agent/edit-point/workspace-adapter.md §10.4
    """

    _SAMPLE_STATE: dict = {
        "id": "sess-test",
        "selectedState": "calm",
        "createdAt": "2026-05-01T00:00:00Z",
        "cells": [{"id": "c1", "type": "text", "content": "Hello world"}],
        "commentors": [],
        "tasks": [],
    }

    def _call_redirect(
        self,
        tool_name: str,
        file_path: str,
        editor_state,
        tmp_paths=None,
    ):
        if tmp_paths is None:
            tmp_paths = []
        return agent_runner_module._apply_editor_index_redirect(
            tool_name,
            {"file_path": file_path},
            editor_state,
            tmp_paths,
        )

    # ------------------------------------------------------------------
    # Positive: redirect activates for Read + editor_state + .editor/ path
    # ------------------------------------------------------------------

    def test_redirect_returns_hook_json_output(self):
        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read", ".editor/cells.json", self._SAMPLE_STATE, tmp_paths
        )
        self.assertIsNotNone(result)

    def test_redirect_hook_output_has_permission_allow(self):
        result = self._call_redirect("Read", ".editor/cells.json", self._SAMPLE_STATE)
        specific = _hook_specific(result, None)
        self.assertIsNotNone(specific)
        self.assertEqual(specific.get("permissionDecision"), "allow")
        self.assertEqual(specific.get("hookEventName"), "PreToolUse")

    def test_redirect_updated_input_points_to_existing_tempfile(self):
        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read", ".editor/cells.json", self._SAMPLE_STATE, tmp_paths
        )
        specific = _hook_specific(result, {})
        tmp_path = (specific.get("updatedInput") or {}).get("file_path", "")
        try:
            self.assertTrue(
                os.path.isfile(tmp_path),
                f"Tempfile {tmp_path!r} does not exist",
            )
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    def test_redirect_tempfile_contains_correct_cells_json(self):
        """The tempfile must contain the cells slice serialised as JSON."""
        import json as _json

        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read", ".editor/cells.json", self._SAMPLE_STATE, tmp_paths
        )
        specific = _hook_specific(result, {})
        tmp_path = (specific.get("updatedInput") or {}).get("file_path", "")
        try:
            with open(tmp_path, encoding="utf-8") as fh:
                data = _json.load(fh)
            # editor_index maps "cells" → {"cells": [...]}
            self.assertIn("cells", data)
            self.assertEqual(data["cells"], self._SAMPLE_STATE["cells"])
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    def test_redirect_tempfile_contains_session_json(self):
        """session.json resource → {id, selectedState, createdAt}."""
        import json as _json

        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read", ".editor/session.json", self._SAMPLE_STATE, tmp_paths
        )
        specific = _hook_specific(result, {})
        tmp_path = (specific.get("updatedInput") or {}).get("file_path", "")
        try:
            with open(tmp_path, encoding="utf-8") as fh:
                data = _json.load(fh)
            self.assertEqual(data.get("id"), "sess-test")
            self.assertEqual(data.get("selectedState"), "calm")
            self.assertNotIn("cells", data)
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    def test_redirect_tempfile_contains_full_state_json(self):
        """full_state.json resource → entire editor_state dict."""
        import json as _json

        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read", ".editor/full_state.json", self._SAMPLE_STATE, tmp_paths
        )
        specific = _hook_specific(result, {})
        tmp_path = (specific.get("updatedInput") or {}).get("file_path", "")
        try:
            with open(tmp_path, encoding="utf-8") as fh:
                data = _json.load(fh)
            self.assertEqual(data, self._SAMPLE_STATE)
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    def test_redirect_appends_path_to_tmp_paths_list(self):
        """The caller's tmp_paths list must have exactly one new entry."""
        tmp_paths: list[str] = []
        self._call_redirect("Read", ".editor/cells.json", self._SAMPLE_STATE, tmp_paths)
        self.assertEqual(len(tmp_paths), 1)
        # Clean up
        for p in tmp_paths:
            if os.path.isfile(p):
                os.unlink(p)

    # ------------------------------------------------------------------
    # Negative: fall-through conditions
    # ------------------------------------------------------------------

    def test_fallthrough_when_editor_state_is_none(self):
        """Condition 2 unmet (editor_state is None) → returns None."""
        result = self._call_redirect("Read", ".editor/cells.json", None)
        self.assertIsNone(result)

    def test_fallthrough_for_non_read_tool(self):
        """Condition 1 unmet (tool_name != 'Read') → returns None."""
        result = self._call_redirect("Write", ".editor/cells.json", self._SAMPLE_STATE)
        self.assertIsNone(result)

    def test_fallthrough_for_non_editor_path(self):
        """Condition 3 unmet (path not in .editor/) → returns None."""
        result = self._call_redirect("Read", "files/report.txt", self._SAMPLE_STATE)
        self.assertIsNone(result)

    def test_fallthrough_for_unknown_editor_resource(self):
        """Path is under .editor/ but stem is not a registered resource → None."""
        result = self._call_redirect(
            "Read", ".editor/unknown_resource.json", self._SAMPLE_STATE
        )
        self.assertIsNone(result)

    def test_fallthrough_for_editor_subdir_path(self):
        """.editor/subdir/cells.json must NOT match — only top-level files are virtual."""
        result = self._call_redirect(
            "Read", ".editor/subdir/cells.json", self._SAMPLE_STATE
        )
        self.assertIsNone(result)

    def test_no_tmpfile_created_on_fallthrough(self):
        """No tempfile should be created when the helper returns None."""
        tmp_paths: list[str] = []
        self._call_redirect("Read", "files/other.txt", self._SAMPLE_STATE, tmp_paths)
        self.assertEqual(tmp_paths, [])

    # ------------------------------------------------------------------
    # Tempfile cleanup contract
    # ------------------------------------------------------------------

    def test_tmp_paths_list_used_for_cleanup(self):
        """All redirect tempfiles appended to tmp_paths can be deleted via unlink."""
        tmp_paths: list[str] = []
        # Trigger two redirects to two different resources.
        self._call_redirect("Read", ".editor/cells.json", self._SAMPLE_STATE, tmp_paths)
        self._call_redirect(
            "Read", ".editor/session.json", self._SAMPLE_STATE, tmp_paths
        )
        self.assertEqual(len(tmp_paths), 2)
        all_exist = all(os.path.isfile(p) for p in tmp_paths)
        self.assertTrue(all_exist, "All created tempfiles must exist before cleanup")
        for p in tmp_paths:
            os.unlink(p)
        all_gone = all(not os.path.exists(p) for p in tmp_paths)
        self.assertTrue(all_gone, "All tempfiles must be gone after cleanup")

    def test_absolute_editor_path_is_redirected(self):
        """Absolute paths like /workspace/sess/.editor/cells.json must be intercepted."""
        tmp_paths: list[str] = []
        result = self._call_redirect(
            "Read",
            "/workspace/sess-abc/.editor/cells.json",
            self._SAMPLE_STATE,
            tmp_paths,
        )
        self.assertIsNotNone(result)
        for p in tmp_paths:
            if os.path.isfile(p):
                os.unlink(p)


# ---------------------------------------------------------------------------
# SDK can_use_tool channel — runtime sandbox-proxy network asks
# ---------------------------------------------------------------------------


class TestCanUseToolPermissionChannel(_RunnerBase):
    """SDK can_use_tool channel — runtime sandbox-proxy network asks.

    The CLI's sandbox-runtime network ask ("SandboxNetworkAccess") is a
    system-level control request invisible to PreToolUse; it arrives only via
    ClaudeAgentOptions.can_use_tool and must route through the same frontend
    confirmation side-channel (claude-agent-sandbox-network-permission-tool.md).
    """

    async def _capture_can_use_tool(
        self,
        *,
        cwd: str,
        sandbox_network_mode: str = "allowlist",
        on_tool_confirmation_request=None,
    ):
        self.set_query([])
        runner = self.make_runner()

        await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="can-use-tool-001",
                user_message="run a sandboxed command",
                cwd=cwd,
                tool_choice="auto",
                sandbox_network_mode=sandbox_network_mode,  # type: ignore[arg-type]
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_confirmation_request=on_tool_confirmation_request,
            ),
        )

        options = self._mock_client.last_options
        return options.can_use_tool

    async def test_can_use_tool_is_wired_into_sdk_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(cwd=temp_dir)
        self.assertIsNotNone(can_use_tool)
        self.assertTrue(callable(can_use_tool))

    async def test_sandbox_network_ask_approval_returns_allow(self):
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            result = await can_use_tool(
                "SandboxNetworkAccess",
                {"host": "cdn.example.com"},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultAllow)
        self.assertEqual(result.updated_input, {"host": "cdn.example.com"})
        self.assertEqual(len(confirmation_requests), 1)
        payload = confirmation_requests[0]
        self.assertEqual(payload.get("tool_name"), "SandboxNetworkAccess")
        self.assertEqual(payload.get("confirmationKind"), "sandbox_network")
        self.assertEqual(
            payload.get("networkRequest"),
            {
                "host": "cdn.example.com",
                "policyMode": "allowlist",
                "matchedAllowedDomain": None,
            },
        )

    async def test_sandbox_network_ask_rejection_denies_with_host_in_message(self):
        async def confirm(payload: dict):
            return {"approved": False}

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            result = await can_use_tool(
                "SandboxNetworkAccess",
                {"host": "cdn.example.com"},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultDeny)
        self.assertIn("cdn.example.com", result.message)
        self.assertIn("allowedDomains", result.message)

    async def test_sandbox_network_ask_confirmation_failure_denies_fail_closed(self):
        async def confirm(payload: dict):
            raise RuntimeError("store exploded")

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            with self.assertLogs(agent_runner_module.logger, level="WARNING"):
                result = await can_use_tool(
                    "SandboxNetworkAccess",
                    {"host": "cdn.example.com"},
                    agent_runner_module.ToolPermissionContext(),
                )

        self.assertIsInstance(result, agent_runner_module.PermissionResultDeny)
        self.assertIn("cdn.example.com", result.message)

    async def test_sandbox_network_ask_without_confirmation_callback_denies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(cwd=temp_dir)
            result = await can_use_tool(
                "SandboxNetworkAccess",
                {"host": "cdn.example.com"},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultDeny)
        self.assertIn("cdn.example.com", result.message)

    async def test_generic_tool_routes_to_generic_confirmation(self):
        """Non-sandbox tool names use the same chain WITHOUT the discriminator."""
        confirmation_requests: list[dict] = []

        async def confirm(payload: dict):
            confirmation_requests.append(payload)
            return {"approved": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            result = await can_use_tool(
                "mcp__foo__bar",
                {"x": 1},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultAllow)
        self.assertEqual(result.updated_input, {"x": 1})
        self.assertEqual(len(confirmation_requests), 1)
        payload = confirmation_requests[0]
        self.assertEqual(payload.get("tool_name"), "mcp__foo__bar")
        self.assertNotIn("confirmationKind", payload)
        self.assertNotIn("networkRequest", payload)

    async def test_generic_tool_askuser_answers_merged_into_updated_input(self):
        """AskUserQuestion-style tools merge frontend answers like step ⑦."""

        async def confirm(payload: dict):
            return {"approved": True, "answers": {"q1": "yes"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            result = await can_use_tool(
                "AskUserQuestion",
                {"questions": [{"question": "q1"}]},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultAllow)
        self.assertEqual(
            result.updated_input,
            {"questions": [{"question": "q1"}], "answers": {"q1": "yes"}},
        )

    async def test_generic_tool_rejection_denies(self):
        async def confirm(payload: dict):
            return {"approved": False, "reason": "not today"}

        with tempfile.TemporaryDirectory() as temp_dir:
            can_use_tool = await self._capture_can_use_tool(
                cwd=temp_dir,
                on_tool_confirmation_request=confirm,
            )
            result = await can_use_tool(
                "mcp__foo__bar",
                {"x": 1},
                agent_runner_module.ToolPermissionContext(),
            )

        self.assertIsInstance(result, agent_runner_module.PermissionResultDeny)
        self.assertEqual(result.message, "not today")


# ---------------------------------------------------------------------------
# Hook dict-literal contract (claude-agent-sdk 0.2.128 regression)
#
# HookJSONOutput is a Union of TypedDicts in the new SDK — NOT callable.
# Every hook path must return plain dicts ("{}" no-op /
# {"hookSpecificOutput": {...}} decisions) without raising.  The old stub
# class masked the production TypeError in tests; these tests pin the shape.
# ---------------------------------------------------------------------------


class TestHookDictLiteralContract(_RunnerBase):
    """Hook callbacks return plain dict literals (no HookJSONOutput calls)."""

    async def _capture_hooks(self, *, cwd: str, sandbox_network_mode: str = "allowlist", on_tool_confirmation_request=None):
        self.set_query([])
        runner = self.make_runner()

        await runner.run_streaming(
            opts=AgentRunOptions(
                thread_id="hook-dict-contract-001",
                user_message="exercise hooks",
                cwd=cwd,
                tool_choice="auto",
                sandbox_network_mode=sandbox_network_mode,  # type: ignore[arg-type]
            ),
            callbacks=AgentStreamingCallbacks(
                on_text_delta=lambda d: None,
                on_tool_confirmation_request=on_tool_confirmation_request,
            ),
        )
        return self._mock_client.last_options.hooks

    async def test_pre_tool_use_disabled_network_deny_returns_plain_dict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hooks = await self._capture_hooks(
                cwd=temp_dir, sandbox_network_mode="disabled"
            )
            pre_hook = hooks["PreToolUse"][0].hooks[0]

            result = await pre_hook(
                {
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://example.com"},
                },
                "call-dict-deny",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(
            result,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "代理网络访问已关闭，禁止网络访问。",
                }
            },
        )

    async def test_pre_tool_use_low_sensitivity_allow_returns_plain_dict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hooks = await self._capture_hooks(cwd=temp_dir)
            pre_hook = hooks["PreToolUse"][0].hooks[0]

            result = await pre_hook(
                {"tool_name": "TodoRead", "tool_input": {}},
                "call-dict-allow",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(
            result,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                }
            },
        )

    async def test_pre_tool_use_user_rejection_returns_plain_dict(self):
        async def confirm(payload: dict):
            return {"approved": False, "reason": "no"}

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "files").mkdir()
            hooks = await self._capture_hooks(
                cwd=str(workspace), on_tool_confirmation_request=confirm
            )
            pre_hook = hooks["PreToolUse"][0].hooks[0]

            result = await pre_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls | grep foo"},
                },
                "call-dict-reject",
                _SDK_HOOK_CONTEXT(),
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(
            result,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "no",
                }
            },
        )

    async def test_post_tool_use_hooks_return_plain_empty_dicts(self):
        """All three PostToolUse callbacks return {} for non-matching tools
        without raising (production crash sites: plan-file and tasks
        observers, agent_runner.py _plan_file/_tasks_changed hooks)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            hooks = await self._capture_hooks(cwd=temp_dir)
            post_hooks = hooks["PostToolUse"][0].hooks

        self.assertEqual(len(post_hooks), 3)
        for hook in post_hooks:
            with self.subTest(hook=getattr(hook, "__name__", repr(hook))):
                result = await hook(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "ls"},
                    },
                    "call-dict-post-noop",
                    _SDK_HOOK_CONTEXT(),
                )
                self.assertIsInstance(result, dict)
                self.assertEqual(result, {})

    async def test_post_tool_use_observers_noop_on_non_workspace_write(self):
        """Plan-file / tasks observers return {} (not raise) for built-in
        Write/TaskCreate calls that do not hit their watched directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            hooks = await self._capture_hooks(cwd=temp_dir)
            post_hooks = hooks["PostToolUse"][0].hooks
            plan_hook, tasks_hook = post_hooks[1], post_hooks[2]

            plan_result = await plan_hook(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": str(Path(temp_dir) / "outside.md"),
                        "content": "x",
                    },
                },
                "call-dict-plan-noop",
                _SDK_HOOK_CONTEXT(),
            )
            self.assertIsInstance(plan_result, dict)
            self.assertEqual(plan_result, {})

            tasks_result = await tasks_hook(
                {"tool_name": "TaskCreate", "tool_input": {"subject": "x"}},
                "call-dict-tasks-noop",
                _SDK_HOOK_CONTEXT(),
            )
            self.assertIsInstance(tasks_result, dict)
            self.assertEqual(tasks_result, {})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
