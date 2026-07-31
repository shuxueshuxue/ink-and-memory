# [Input] None — module-level side-effecting stub setup.
# [Output] Inject claude_agent_sdk stub into sys.modules so libs/claude_agent_kit
#          can be imported in environments where claude-agent-sdk is not installed.
# [Pos] test-helper node in backend/tests
# [Sync] 2026-05-22: required because libs/claude_agent_kit/server/agent_runner.py
#                    has a top-level hard import of claude_agent_sdk.types.
#                    Import this module BEFORE any libs.claude_agent_kit import.
# [Sync] 2026-07-23: add can_use_tool permission types (PermissionResultAllow /
#                    PermissionResultDeny / PermissionResult /
#                    ToolPermissionContext) imported by agent_runner.py for the
#                    sandbox-runtime network ask channel.
# [Sync] 2026-07-26: SDK migration — stub module names follow the renamed
#                    claude_agent_sdk package; ClaudeCodeOptions →
#                    ClaudeAgentOptions.
# [Sync] 2026-07-26: HookJSONOutput note — in claude-agent-sdk 0.2.128 it is a
#                    Union of TypedDicts (types.py:561), NOT callable; the
#                    runner now returns plain dict literals and only imports
#                    the name for annotations, so the kwargs-class stub below
#                    exists solely to satisfy the import in stubbed runs.

"""Pre-import stubs for claude_agent_sdk.

Usage (at top of every test file that imports libs.claude_agent_kit):

    import tests._sdk_stubs  # noqa: F401 — must be first

or equivalently:

    from tests import _sdk_stubs  # noqa: F401
"""
import sys
import types as _t


def _stub_module(name: str, **attrs) -> _t.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = _t.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


# claude_agent_sdk — the Claude Code Python SDK.
# Stubbed with every symbol that agent_runner.py and types.py import at module level.
# Each class accepts **kwargs so agent_runner.py can instantiate them freely in tests.

class _KwargsBase:
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _HookMatcher(_KwargsBase):
    def __init__(self, matcher=None, hooks=None, **kwargs):
        self.matcher = matcher
        self.hooks = hooks or []
        super().__init__(**kwargs)


class _AssistantMessage:
    def __init__(self, content=None, **kwargs):
        self.content = content or []


class _ResultMessage:
    def __init__(self, subtype="success", session_id=None, usage=None, **kwargs):
        self.subtype = subtype
        self.session_id = session_id
        self.usage = usage


class _UserMessage:
    def __init__(self, content=None, **kwargs):
        self.content = content or []


class _StreamEvent(_KwargsBase):
    pass


# can_use_tool permission types (SDK 0.0.25+), mirrored as kwargs classes.
class _PermissionResultAllow(_KwargsBase):
    def __init__(self, behavior="allow", updated_input=None, updated_permissions=None, **kwargs):
        self.behavior = behavior
        self.updated_input = updated_input
        self.updated_permissions = updated_permissions
        super().__init__(**kwargs)


class _PermissionResultDeny(_KwargsBase):
    def __init__(self, behavior="deny", message="", interrupt=False, **kwargs):
        self.behavior = behavior
        self.message = message
        self.interrupt = interrupt
        super().__init__(**kwargs)


class _ToolPermissionContext(_KwargsBase):
    def __init__(self, signal=None, suggestions=None, **kwargs):
        self.signal = signal
        self.suggestions = suggestions or []
        super().__init__(**kwargs)


_stub_module("claude_agent_sdk",
    query=None,
    ClaudeSDKClient=_KwargsBase,
)
_stub_module("claude_agent_sdk.types",
    AssistantMessage=_AssistantMessage,
    ClaudeAgentOptions=_KwargsBase,
    HookContext=_KwargsBase,
    HookJSONOutput=_KwargsBase,
    HookMatcher=_HookMatcher,
    McpServerConfig=_KwargsBase,
    McpStdioServerConfig=_KwargsBase,
    PermissionResult=(_PermissionResultAllow, _PermissionResultDeny),
    PermissionResultAllow=_PermissionResultAllow,
    PermissionResultDeny=_PermissionResultDeny,
    ResultMessage=_ResultMessage,
    StreamEvent=_StreamEvent,
    SystemMessage=_KwargsBase,
    ToolPermissionContext=_ToolPermissionContext,
    UserMessage=_UserMessage,
)
