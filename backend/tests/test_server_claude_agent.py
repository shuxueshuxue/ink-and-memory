# [Input] Consume server.py (FastAPI app) and claude_agent module.
# [Output] Verify that claude-agent and Notion connector routes are registered,
#          factory is initialised, request/response models are correct, and
#          authentication is enforced.
# [Pos] test node in backend/tests
# [Sync] 2026-05-22: initial — smoke tests for /api/claude-agent/* routes in server.py.
#                    Adapted from Pawkeyland scripts/test_demo_server_import.py
#                    (removed pet/persona/sticker/necklace contract tests).
# [Sync] 2026-05-24: cover server startup cleanup of unsupported Agent env keys.
# [Sync] 2026-06-22: cover Claude Agent route attachment handling when Settings
#                    Workspace Mode is disabled.
# [Sync] 2026-06-25: cover thread-scoped stop endpoint registration and routing.
# [Sync] 2026-07-04: cover Notion connector router registration and auth gating.

"""Smoke tests for the Claude Agent HTTP routes in server.py.

Tests run without starting a real uvicorn server; they inspect route registration
and Pydantic model contracts via FastAPI's test client (httpx).

Requirements: server must be importable (database, config, etc. must initialise
without error in the test environment — SQLite is created at first import).
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest
import unittest.mock
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Lightweight stubs so server.py imports don't crash without full runtime.
# ---------------------------------------------------------------------------

def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


# Stub claude_agent_sdk so runner.py doesn't fail on import
if "claude_agent_sdk" not in sys.modules:
    sdk_types = _stub_module("claude_agent_sdk.types")

    class _SdkStub:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class AssistantMessage(_SdkStub):
        pass

    class ClaudeAgentOptions(_SdkStub):
        pass

    class HookContext(_SdkStub):
        pass

    class HookJSONOutput(_SdkStub):
        pass

    class HookMatcher(_SdkStub):
        pass

    class McpServerConfig(_SdkStub):
        pass

    class McpStdioServerConfig(_SdkStub):
        pass

    class ResultMessage(_SdkStub):
        pass

    class StreamEvent(_SdkStub):
        pass

    class SystemMessage(_SdkStub):
        pass

    class UserMessage(_SdkStub):
        pass

    for _cls in [
        AssistantMessage,
        ClaudeAgentOptions,
        HookContext,
        HookJSONOutput,
        HookMatcher,
        McpServerConfig,
        McpStdioServerConfig,
        ResultMessage,
        StreamEvent,
        SystemMessage,
        UserMessage,
    ]:
        setattr(sdk_types, _cls.__name__, _cls)

    class ClaudeSDKClient:
        pass

    _stub_module("claude_agent_sdk", ClaudeSDKClient=ClaudeSDKClient, query=None, types=sdk_types)

# Stub heavy optional dependencies so server.py can be imported in minimal envs.

def _stub_deep(dotted_path: str, **attrs):
    """Ensure every segment of dotted_path exists as a stub module."""
    parts = dotted_path.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            mod = _stub_module(name)
        else:
            mod = sys.modules[name]
    mod.__dict__.update(attrs)
    return mod


# apscheduler
if "apscheduler" not in sys.modules:
    class _FakeScheduler:
        def add_job(self, *a, **k): pass
        def start(self): pass
        def shutdown(self, *a, **k): pass

    _stub_deep("apscheduler")
    _stub_deep("apscheduler.schedulers")
    _stub_deep("apscheduler.schedulers.asyncio", AsyncIOScheduler=_FakeScheduler)

# polycli
if "polycli" not in sys.modules:
    def _session_def(*a, **k):
        def _dec(fn): return fn
        return _dec

    _stub_deep("polycli")
    _stub_deep("polycli.orchestration")
    _stub_deep("polycli.orchestration.session_registry",
               session_def=_session_def, get_registry=lambda: None)
    _stub_deep("polycli.integrations")
    _stub_deep("polycli.integrations.fastapi", mount_control_panel=lambda *a, **k: None)
    _stub_deep("polycli", PolyAgent=object)

# dashscope / speech recognition
if "dashscope" not in sys.modules:
    _stub_deep("dashscope")

# stateless_analyzer (local module, may not be importable without deps)
if "stateless_analyzer" not in sys.modules:
    _stub_deep("stateless_analyzer", analyze_stateless=lambda *a, **k: {})

# speech_recognition (local module)
if "speech_recognition" not in sys.modules:
    _stub_deep("speech_recognition", init_speech_recognition=lambda *a, **k: None)

# scheduler (local module)
if "scheduler" not in sys.modules:
    _stub_deep("scheduler", daily_generation_job=lambda: None)


# ---------------------------------------------------------------------------
# Try to import server — skip all tests if full deps not installed
# ---------------------------------------------------------------------------

_SERVER_MODULE = None
_SERVER_SKIP_REASON = None

try:
    import server as _SERVER_MODULE  # noqa: E402
except Exception as _e:  # noqa: BLE001
    _SERVER_SKIP_REASON = f"server.py cannot be imported in this environment: {_e}"


def _skip_if_no_server(cls):
    """Class decorator: skip all tests when server.py is not importable."""
    if _SERVER_SKIP_REASON:
        return unittest.skip(_SERVER_SKIP_REASON)(cls)
    return cls


@_skip_if_no_server
class TestServerAgentEnvCleanup(unittest.TestCase):
    """Verify server startup env cleanup preserves only supported Agent keys."""

    def test_cleanup_preserves_mem0_and_session_keys(self):
        with unittest.mock.patch.dict(
            os.environ,
            {
                "INK_AGENT_MEM0_API_KEY": "mem0-test",
                "INK_AGENT_TTL_S": "600",
                "INK_AGENT_UNSUPPORTED": "stale",
                "ANTHROPIC_API_KEY": "legacy",
                "ANTHROPIC_AUTH_TOKEN": "current",
                "CLAUDE_CODE_UNUSED_TOKEN": "stale",
            },
            clear=True,
        ):
            _SERVER_MODULE._drop_unsupported_agent_env()

            self.assertEqual(os.environ["INK_AGENT_MEM0_API_KEY"], "mem0-test")
            self.assertEqual(os.environ["INK_AGENT_TTL_S"], "600")
            self.assertEqual(os.environ["ANTHROPIC_AUTH_TOKEN"], "current")
            self.assertNotIn("INK_AGENT_UNSUPPORTED", os.environ)
            self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
            self.assertNotIn("CLAUDE_CODE_UNUSED_TOKEN", os.environ)

    def test_cleanup_preserves_sandbox_runtime_keys(self):
        # Regression for the 2026-07-26 production miss: the extra sandbox
        # read paths must survive startup cleanup or the sandbox silently
        # loses the contract.  (The apply-seccomp settings override key
        # briefly covered here was removed 2026-07-26 — proven dead in
        # production; Route A reverted to the vendor passthrough patch.)
        with unittest.mock.patch.dict(
            os.environ,
            {
                "INK_AGENT_SANDBOX_EXTRA_ALLOW_READ": "/app/claude_agent:/app/libs",
            },
            clear=True,
        ):
            _SERVER_MODULE._drop_unsupported_agent_env()

            self.assertEqual(
                os.environ["INK_AGENT_SANDBOX_EXTRA_ALLOW_READ"],
                "/app/claude_agent:/app/libs",
            )


# ---------------------------------------------------------------------------
# Route registration tests (import-level, no HTTP calls)
# ---------------------------------------------------------------------------


@_skip_if_no_server
class TestClaudeAgentRouteRegistration(unittest.TestCase):
    """Verify the 6 claude-agent routes are registered in server.py."""

    @classmethod
    def setUpClass(cls):
        cls.app = _SERVER_MODULE.app

        cls.routes = {
            (frozenset(r.methods or set()), r.path)
            for r in cls.app.routes
            if hasattr(r, "path") and "claude-agent" in getattr(r, "path", "")
        }

    def _has_route(self, method: str, path: str) -> bool:
        return any(
            method in (methods or set()) and p == path
            for methods, p in self.routes
        )

    def test_post_claude_agent_stream(self):
        self.assertTrue(self._has_route("POST", "/api/claude-agent"))

    def test_get_chat_history(self):
        self.assertTrue(self._has_route("GET", "/api/claude-agent/chat-history"))

    def test_post_message_latency(self):
        self.assertTrue(self._has_route("POST", "/api/claude-agent/message-latency"))

    def test_get_session_status(self):
        self.assertTrue(self._has_route("GET", "/api/claude-agent/session"))

    def test_delete_session(self):
        self.assertTrue(self._has_route("DELETE", "/api/claude-agent/session"))

    def test_post_tool_confirm(self):
        self.assertTrue(self._has_route("POST", "/api/claude-agent/tool-confirm"))

    def test_post_thread_stop(self):
        self.assertTrue(self._has_route("POST", "/api/claude-agent/threads/{thread_id}/stop"))


@_skip_if_no_server
class TestNotionRouteRegistration(unittest.TestCase):
    """Verify the Notion connector routes are registered in server.py."""

    @classmethod
    def setUpClass(cls):
        cls.app = _SERVER_MODULE.app
        cls.routes = {
            (frozenset(r.methods or set()), r.path)
            for r in cls.app.routes
            if hasattr(r, "path") and r.path.startswith("/api/connectors")
        }

    def _has_route(self, method: str, path: str) -> bool:
        return any(
            method in (methods or set()) and p == path
            for methods, p in self.routes
        )

    def test_get_connectors(self):
        self.assertTrue(self._has_route("GET", "/api/connectors"))

    def test_post_connectors(self):
        self.assertTrue(self._has_route("POST", "/api/connectors"))

    def test_get_connector(self):
        self.assertTrue(self._has_route("GET", "/api/connectors/{connector_id}"))

    def test_patch_connector(self):
        self.assertTrue(self._has_route("PATCH", "/api/connectors/{connector_id}"))

    def test_delete_connector(self):
        self.assertTrue(self._has_route("DELETE", "/api/connectors/{connector_id}"))

    def test_auth_login(self):
        self.assertTrue(self._has_route("POST", "/api/connectors/{connector_id}/auth/login"))

    def test_auth_poll(self):
        self.assertTrue(self._has_route("POST", "/api/connectors/{connector_id}/auth/poll"))

    def test_list_databases(self):
        self.assertTrue(self._has_route("GET", "/api/connectors/{connector_id}/databases"))

    def test_list_pages(self):
        self.assertTrue(self._has_route("GET", "/api/connectors/{connector_id}/pages"))

    def test_list_resources(self):
        self.assertTrue(self._has_route("GET", "/api/connectors/{connector_id}/resources"))

    def test_select_resources(self):
        self.assertTrue(self._has_route("POST", "/api/connectors/{connector_id}/resources/select"))

    def test_sync_connector(self):
        self.assertTrue(self._has_route("POST", "/api/connectors/{connector_id}/sync"))

    def test_delete_resource(self):
        self.assertTrue(self._has_route("DELETE", "/api/connectors/{connector_id}/resources/{resource_id}"))


# ---------------------------------------------------------------------------
# Pydantic model contract tests
# ---------------------------------------------------------------------------

@_skip_if_no_server
class TestClaudeAgentRequestModel(unittest.TestCase):
    """Verify ClaudeAgentRequestBody defaults and field types."""

    @classmethod
    def setUpClass(cls):
        if True:  # server already imported at module level
            _srv = _SERVER_MODULE
            cls.Model = _srv.ClaudeAgentRequestBody

    def test_message_defaults_to_none(self):
        m = self.Model()
        self.assertIsNone(m.message)

    def test_default_resume_false(self):
        m = self.Model(message="hello")
        self.assertFalse(m.resume)

    def test_default_tool_choice_auto(self):
        m = self.Model(message="hello")
        self.assertEqual(m.tool_choice, "auto")

    def test_default_max_turns_100(self):
        m = self.Model(message="hello")
        self.assertEqual(m.max_turns, 100)

    def test_model_optional(self):
        m = self.Model(message="hello")
        self.assertIsNone(m.model)

    def test_cwd_optional(self):
        m = self.Model(message="hello")
        self.assertIsNone(m.cwd)


@_skip_if_no_server
class TestToolConfirmRequestModel(unittest.TestCase):
    """Verify ToolConfirmRequestBody contract."""

    @classmethod
    def setUpClass(cls):
        if True:  # server already imported at module level
            _srv = _SERVER_MODULE
            cls.Model = _srv.ToolConfirmRequestBody

    def test_requires_tool_call_id(self):
        with self.assertRaises(Exception):
            self.Model(approved=True)

    def test_requires_approved(self):
        with self.assertRaises(Exception):
            self.Model(thread_id="thread-1", tool_call_id="xyz")

    def test_reason_optional(self):
        m = self.Model(thread_id="thread-1", tool_call_id="xyz", approved=True)
        self.assertIsNone(m.reason)

    def test_answers_optional(self):
        m = self.Model(thread_id="thread-1", tool_call_id="xyz", approved=False)
        self.assertIsNone(m.answers)


# ---------------------------------------------------------------------------
# Route behavior tests
# ---------------------------------------------------------------------------

@_skip_if_no_server
class TestClaudeAgentRouteWorkspaceMode(unittest.TestCase):
    """Workspace Mode disabled should not initialize workspaces from attachments."""

    def test_attachments_do_not_initialize_workspace_when_workspace_mode_disabled(self):
        import routers.claude_agent as route_module

        body = route_module.ClaudeAgentRequestBody(
            thread_id="thread-no-workspace",
            message="hello with attachment",
            attachments=[
                route_module.ChatAttachment(
                    type="file",
                    url="/api/files/file-1",
                    storageKey="file-1",
                    filename="note.txt",
                    mediaType="text/plain",
                )
            ],
        )

        async def _call_route():
            return await route_module.claude_agent_stream(
                body,
                current_user={"user_id": 7},
            )

        with (
            unittest.mock.patch.object(
                route_module.database,
                "get_chat_thread",
                return_value={"id": "thread-no-workspace"},
            ),
            unittest.mock.patch.object(
                route_module.database,
                "get_system_config",
                return_value={"workspace_enabled": False},
            ),
            unittest.mock.patch.object(
                route_module,
                "get_or_create_workspace",
            ) as get_or_create_workspace,
            unittest.mock.patch.object(
                route_module,
                "sync_attachments_to_workspace_files",
            ) as sync_attachments_to_workspace_files,
        ):
            response = asyncio.run(_call_route())

        self.assertEqual(response.media_type, "text/event-stream")
        get_or_create_workspace.assert_not_called()
        sync_attachments_to_workspace_files.assert_not_called()


@_skip_if_no_server
class TestClaudeAgentRouteStop(unittest.TestCase):
    """Thread stop route should validate ownership before cancelling runtime state."""

    def test_stop_thread_validates_owner_and_calls_factory(self):
        import routers.claude_agent as route_module

        async def _call_route():
            return await route_module.claude_agent_stop_thread(
                "thread-stop",
                current_user={"user_id": 7},
            )

        with (
            unittest.mock.patch.object(
                route_module.database,
                "get_chat_thread",
                return_value={"id": "thread-stop", "user_id": 7},
            ) as get_chat_thread,
            unittest.mock.patch.object(
                route_module.claude_agent_thread_factory,
                "stop_thread",
                new=unittest.mock.AsyncMock(
                    return_value={
                        "stop_requested": True,
                        "running": False,
                        "lifecycle": "idle",
                    }
                ),
            ) as stop_thread,
        ):
            response = asyncio.run(_call_route())

        get_chat_thread.assert_called_once_with("thread-stop", 7)
        stop_thread.assert_awaited_once_with("thread-stop")
        self.assertEqual(
            response,
            {
                "ok": True,
                "thread_id": "thread-stop",
                "stop_requested": True,
                "running": False,
                "lifecycle": "idle",
            },
        )


# ---------------------------------------------------------------------------
# Factory lifecycle tests
# ---------------------------------------------------------------------------

@_skip_if_no_server
class TestFactoryLifecycle(unittest.TestCase):
    """Verify the factory singleton is created and wired to startup/shutdown."""

    @classmethod
    def setUpClass(cls):
        if True:  # server already imported at module level
            _srv = _SERVER_MODULE
            cls.srv = _srv

    def test_factory_instance_exists(self):
        self.assertIsNotNone(self.srv.claude_agent_thread_factory)

    def test_factory_is_thread_factory_type(self):
        from claude_agent import ClaudeAgentThreadFactory
        self.assertIsInstance(
            self.srv.claude_agent_thread_factory,
            ClaudeAgentThreadFactory,
        )

    def test_startup_handler_registered(self):
        handler_names = [
            h.__name__
            for h in self.srv.app.router.on_startup
        ]
        self.assertIn("startup_claude_agent", handler_names)

    def test_shutdown_handler_registered(self):
        handler_names = [
            h.__name__
            for h in self.srv.app.router.on_shutdown
        ]
        self.assertIn("shutdown_claude_agent", handler_names)


# ---------------------------------------------------------------------------
# Authentication enforcement (401 without token)
# ---------------------------------------------------------------------------

@_skip_if_no_server
class TestClaudeAgentAuth(unittest.TestCase):
    """Claude agent routes must require JWT authentication."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("httpx not installed — skipping HTTP auth tests")
        if True:  # server already imported at module level
            _srv = _SERVER_MODULE
            cls.client = TestClient(_srv.app, raise_server_exceptions=False)

    def test_stream_requires_auth(self):
        resp = self.client.post(
            "/api/claude-agent",
            json={"message": "hi"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_chat_history_requires_auth(self):
        resp = self.client.get("/api/claude-agent/chat-history")
        self.assertEqual(resp.status_code, 401)

    def test_session_status_requires_auth(self):
        resp = self.client.get("/api/claude-agent/session")
        self.assertEqual(resp.status_code, 401)

    def test_tool_confirm_requires_auth(self):
        resp = self.client.post(
            "/api/claude-agent/tool-confirm",
            json={"tool_call_id": "x", "approved": True},
        )
        self.assertEqual(resp.status_code, 401)


@_skip_if_no_server
class TestNotionAuth(unittest.TestCase):
    """Notion connector routes must require JWT authentication."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("httpx not installed — skipping HTTP auth tests")
        cls.client = TestClient(_SERVER_MODULE.app, raise_server_exceptions=False)

    def test_list_connectors_requires_auth(self):
        resp = self.client.get("/api/connectors")
        self.assertEqual(resp.status_code, 401)

    def test_create_connector_requires_auth(self):
        resp = self.client.post(
            "/api/connectors",
            json={"name": "Notion"},
        )
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
