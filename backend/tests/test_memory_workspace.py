# [Input] Consume memory_workspace.py and claude-agent routes.
# [Output] Validate procedural Memory workspace source rules and initialization boundary.
# [Pos] test node in backend/tests
# [Sync] 2026-06-06: cover partition-config prompt sources, no .claude/memory fallback,
#                    no implicit thread initialization.
# [Sync] 2026-06-06: remove tests for POST /api/workspace/memory-init
#                    (Voice scenario memory init endpoint deleted).

"""Regression tests for procedural Memory workspace initialization."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401
from libs.claude_agent_kit.server.memory_workspace import (
    MEMORY_PROMPT_FILES,
    PROCEDURAL_MEMORY_FILES,
    _CONFIG_KEY_TO_FILE,
    apply_memory_config,
    get_memory_context_block,
    get_memory_prompt_files,
    init_memory_workspace,
)


def _make_workspace(tmp_dir: str) -> Path:
    """Create a minimal workspace directory and patch AGENT_CWD."""

    ws = Path(tmp_dir) / "test-session"
    ws.mkdir()
    os.environ["AGENT_CWD"] = tmp_dir
    return ws


def _prompt_file_config(prefix: str = "CONFIG") -> dict:
    return {
        "enabled": True,
        "workspace_type": "procedural",
        "prompt_files": {
            filename: f"{prefix}:{filename}"
            for filename in MEMORY_PROMPT_FILES
        },
    }


def _run(coro):
    """Run a coroutine without leaking a process-global event loop."""

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


class TestInitMemoryWorkspaceStructure(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._ws = _make_workspace(self._tmp.name)

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_memory_dir_created(self):
        memory_dir = init_memory_workspace(self._ws, _prompt_file_config())
        self.assertTrue(memory_dir.is_dir())
        self.assertEqual(memory_dir.name, "memory")

    def test_core_prompt_files_created_from_partition_config(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        for filename in MEMORY_PROMPT_FILES:
            content = (self._ws / "memory" / filename).read_text(encoding="utf-8")
            self.assertEqual(content.strip(), f"CONFIG:{filename}")

    def test_procedural_subdir_created(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        self.assertTrue((self._ws / "memory" / "procedural").is_dir())

    def test_procedural_starter_files_created(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        proc_dir = self._ws / "memory" / "procedural"
        for fname in PROCEDURAL_MEMORY_FILES:
            self.assertTrue((proc_dir / fname).is_file(), f"Missing {fname}")

    def test_procedural_json_files_are_valid_json(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        proc_dir = self._ws / "memory" / "procedural"
        for fname in PROCEDURAL_MEMORY_FILES:
            content = (proc_dir / fname).read_text(encoding="utf-8")
            try:
                json.loads(content)
            except json.JSONDecodeError:
                self.fail(f"{fname} is not valid JSON")

    def test_long_term_summary_file_not_created(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        self.assertFalse((self._ws / "memory" / "long_term_memory.md").exists())

    def test_idempotent_on_repeat_calls_preserves_state_files(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        prefs = self._ws / "memory" / "procedural" / "user_preferences.json"
        prefs.write_text('{"custom": true}', encoding="utf-8")
        init_memory_workspace(self._ws, _prompt_file_config("UPDATED"))
        self.assertEqual(prefs.read_text(encoding="utf-8"), '{"custom": true}')
        self.assertEqual(
            (self._ws / "memory" / "WORKFLOW.md").read_text(encoding="utf-8").strip(),
            "UPDATED:WORKFLOW.md",
        )


class TestTemplateSources(unittest.TestCase):
    """Verify all core templates are partition-config only."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._ws = _make_workspace(self._tmp.name)
        self._fake_project_root = Path(self._tmp.name) / "project"
        fake_memory = self._fake_project_root / ".claude" / "memory"
        fake_memory.mkdir(parents=True)
        for filename in MEMORY_PROMPT_FILES:
            (fake_memory / filename).write_text(
                f"FILESYSTEM:{filename}", encoding="utf-8"
            )

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_filesystem_templates_are_never_used(self):
        init_memory_workspace(self._ws, {})
        for filename in MEMORY_PROMPT_FILES:
            self.assertFalse(
                (self._ws / "memory" / filename).exists(),
                f"{filename} must not be copied from .claude/memory/",
            )

    def test_partial_prompt_files_config_writes_only_present_files(self):
        config = {"prompt_files": {"WORKFLOW.md": "CONFIG:workflow"}}
        init_memory_workspace(self._ws, config)
        self.assertEqual(
            (self._ws / "memory" / "WORKFLOW.md").read_text(encoding="utf-8").strip(),
            "CONFIG:workflow",
        )
        for filename in MEMORY_PROMPT_FILES:
            if filename == "WORKFLOW.md":
                continue
            self.assertFalse((self._ws / "memory" / filename).exists())

    def test_legacy_override_keys_still_supported_for_migration(self):
        config = {
            "workflow_prompt_override": "LEGACY:workflow",
            "query_prompt_override": "LEGACY:query",
            "distiller_prompt_override": "LEGACY:distiller",
            "answer_prompt_override": "LEGACY:answer",
            "update_prompt_override": "LEGACY:update",
        }
        prompt_files = get_memory_prompt_files(config)
        self.assertEqual(set(prompt_files), set(MEMORY_PROMPT_FILES))
        init_memory_workspace(self._ws, config)
        self.assertEqual(
            (self._ws / "memory" / "WORKFLOW.md").read_text(encoding="utf-8").strip(),
            "LEGACY:workflow",
        )


class TestApplyMemoryConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._ws = _make_workspace(self._tmp.name)
        (self._ws / "memory").mkdir()

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_applies_prompt_files(self):
        apply_memory_config(self._ws, _prompt_file_config("OVERRIDE"))
        for filename in MEMORY_PROMPT_FILES:
            content = (self._ws / "memory" / filename).read_text(encoding="utf-8")
            self.assertEqual(content.strip(), f"OVERRIDE:{filename}")

    def test_applies_canonical_keys(self):
        config = {key: f"CANONICAL:{filename}" for key, filename in _CONFIG_KEY_TO_FILE.items()}
        apply_memory_config(self._ws, config)
        for filename in MEMORY_PROMPT_FILES:
            content = (self._ws / "memory" / filename).read_text(encoding="utf-8")
            self.assertEqual(content.strip(), f"CANONICAL:{filename}")

    def test_noop_when_config_is_none(self):
        apply_memory_config(self._ws, None)


class TestGetMemoryContextBlock(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._ws = _make_workspace(self._tmp.name)

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_returns_empty_string_when_memory_dir_absent(self):
        block = get_memory_context_block(self._ws)
        self.assertEqual(block, "")

    def test_contains_procedural_only_label(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        block = get_memory_context_block(self._ws)
        self.assertIn("procedural only", block.lower())
        self.assertNotIn("long_term_memory.md", block)

    def test_mentions_prompt_and_state_files(self):
        init_memory_workspace(self._ws, _prompt_file_config())
        block = get_memory_context_block(self._ws)
        self.assertIn("WORKFLOW.md", block)
        self.assertIn("Procedural state files", block)


class TestInitWorkspaceDoesNotCreateMemoryDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_memory_dir_not_created_by_init_workspace(self):
        from libs.claude_agent_kit.server.workspace import init_workspace

        ws = init_workspace("no-memory-auto-init")
        self.assertFalse(
            (ws / "memory").exists(),
            "memory/ must be initialized through the workspace file interface",
        )


class TestMemoryInitRouteBoundary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_create_thread_route_does_not_initialize_memory(self):
        from routers.claude_agent import claude_agent_create_thread

        with unittest.mock.patch("database.create_chat_thread", return_value="thread-route"):
            result = _run(
                claude_agent_create_thread(current_user={"user_id": 1})
            )

        self.assertEqual(result["thread_id"], "thread-route")
        self.assertFalse((Path(self._tmp.name) / "thread-route").exists())



if __name__ == "__main__":
    unittest.main()
