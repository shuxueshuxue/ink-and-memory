# [Input] Consume get_workspace_root, init_workspace, get_or_create_workspace
#         from libs/claude_agent_kit/server/workspace.py.
# [Output] Validate workspace root resolution, skeleton creation, idempotency,
#          path traversal rejection, AGENT_CWD env var handling, and .editor/
#          virtual index initialisation (Hook execution order & read path), and
#          per-thread Claude Code sandbox settings sync.
# [Pos] test node in backend/tests
# [Sync] 2026-05-22: migrated from Pawkeyland scripts/test_workspace_manager.py.
#                    Removed legacy skills/symlink tests during early migration,
#                    resolve_safe_path tests (not in simplified workspace.py).
#                    Adapted: module path libs/claude_agent_kit/server/workspace.py,
#                    default workspace dir renamed ink-agent-workspaces.
# [Sync] 2026-05-28: add TestEditorIndexInit — covers .editor/ placeholder directory
#                    creation driven by _init_editor_index(), which is the workspace
#                    initialisation step that enables the PreToolUse read-path redirect.
# [Sync] 2026-06-13: cover per-thread .claude/settings.json sandbox config derived
#                    from AGENT_CWD/{session_id}.
# [Sync] 2026-06-14: cover read-only runtime dependency allowlist in sandbox
#                    settings without adding the project root as a default read path.
# [Sync] 2026-06-14: cover automatic Docker nested Bash sandbox detection.
# [Sync] 2026-06-16: assert .claude/skills stays writable in sandbox denyWrite.
# [Sync] 2026-06-16: cover direct .claude/skills writes imported back into
#                    workspace/skills before discovery symlinks are rebuilt.
# [Sync] 2026-06-17: cover Linux sbin runtime allowlist needed by bubblewrap.
# [Sync] 2026-06-17: cover preserving literal symlink aliases for rootfs mount
#                    points such as /sbin.
# [Sync] 2026-06-21: cover Settings-backed sandbox network policy emission.
# [Sync] 2026-06-25: cover open sandbox network mode omitting sandbox.network
#                    instead of writing unsupported allowedDomains ["*"].
# [Sync] 2026-07-26: cover sandbox fs write policy — default Claude TMPDIR
#                    allowWrite (cwd-* zsh noise fix), CLAUDE_TMPDIR override,
#                    sandbox_fs_allowed_write_paths append + denyWrite
#                    unchanged, disabled-sandbox shape unchanged.

"""Regression tests for libs/claude_agent_kit/server/workspace.py."""
from __future__ import annotations

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
from libs.claude_agent_kit.server.editor_index import EDITOR_RESOURCES
from libs.claude_agent_kit.server.workspace import (
    SANDBOX_EXTRA_ALLOW_READ_ENV,
    WORKSPACE_SUBDIRS,
    _append_existing_sandbox_read_path,
    _sandbox_claude_tmp_write_paths,
    get_or_create_workspace,
    get_workspace_root,
    init_workspace,
    sync_workspace_sandbox_settings,
)


class TestGetWorkspaceRoot(unittest.TestCase):
    def test_returns_temp_subdir_when_env_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "AGENT_CWD"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            root = get_workspace_root()
        self.assertTrue(root.is_absolute())
        self.assertEqual(root.name, "ink-agent-workspaces")

    def test_respects_absolute_agent_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            with unittest.mock.patch.dict(os.environ, {"AGENT_CWD": td}):
                root = get_workspace_root()
            self.assertEqual(root.resolve(), Path(td).resolve())

    def test_ignores_relative_agent_cwd_and_falls_back(self):
        with unittest.mock.patch.dict(os.environ, {"AGENT_CWD": "relative/path"}):
            root = get_workspace_root()
        self.assertTrue(root.is_absolute())
        self.assertEqual(root.name, "ink-agent-workspaces")


class TestInitWorkspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name
        self._container_patch = unittest.mock.patch(
            "libs.claude_agent_kit.server.workspace._running_in_linux_container",
            return_value=False,
        )
        self._container_patch.start()

    def tearDown(self):
        self._container_patch.stop()
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_creates_standard_subdirectories(self):
        ws = init_workspace("sess-001")
        for subdir in WORKSPACE_SUBDIRS:
            self.assertTrue((ws / subdir).is_dir(), f"{subdir}/ should exist")

    def test_creates_claude_directory(self):
        ws = init_workspace("sess-001")
        self.assertTrue((ws / ".claude").is_dir())

    def test_idempotent_on_repeat_calls(self):
        ws1 = init_workspace("sess-repeat")
        ws2 = init_workspace("sess-repeat")
        self.assertEqual(ws1, ws2)

    def test_repairs_deleted_subdir(self):
        ws = init_workspace("sess-repair")
        logs_dir = ws / "logs"
        logs_dir.rmdir()
        self.assertFalse(logs_dir.exists())
        init_workspace("sess-repair")
        self.assertTrue(logs_dir.is_dir())

    def test_preserves_existing_claude_content_on_repeat(self):
        ws = init_workspace("sess-copy")
        marker = ws / ".claude" / "test_marker.txt"
        marker.write_text("kept")
        init_workspace("sess-copy")
        self.assertEqual(marker.read_text(), "kept")

    def test_creates_workspace_under_agent_cwd(self):
        ws = init_workspace("my-session")
        self.assertTrue(ws.is_dir())
        self.assertEqual(ws.resolve().parent, Path(self._tmp.name).resolve())
        self.assertEqual(ws.name, "my-session")

    def test_writes_enabled_sandbox_settings_for_thread_workspace(self):
        ws = init_workspace("sandbox-session")
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertTrue(sandbox["enabled"])
        self.assertTrue(sandbox["failIfUnavailable"])
        self.assertTrue(sandbox["autoAllowBashIfSandboxed"])
        self.assertFalse(sandbox["allowUnsandboxedCommands"])
        self.assertNotIn("enableWeakerNestedSandbox", sandbox)
        self.assertEqual(sandbox["filesystem"]["denyRead"], ["/"])
        self.assertEqual(sandbox["filesystem"]["allowRead"][0], str(ws.resolve()))
        self.assertEqual(
            sandbox["filesystem"]["allowWrite"],
            [str(ws.resolve()), *_sandbox_claude_tmp_write_paths()],
        )
        self.assertEqual(sandbox["network"]["allowedDomains"], [])
        self.assertNotIn(
            str((ws / ".claude").resolve()),
            sandbox["filesystem"]["denyWrite"],
        )
        self.assertNotIn(
            str((ws / ".claude" / "skills").resolve()),
            sandbox["filesystem"]["denyWrite"],
        )
        self.assertIn(
            str((ws / ".claude" / "settings.json").resolve()),
            sandbox["filesystem"]["denyWrite"],
        )
        self.assertIn(
            str((ws / ".claude" / "hooks").resolve()),
            sandbox["filesystem"]["denyWrite"],
        )
        self.assertIn(
            str((ws / ".editor").resolve()),
            sandbox["filesystem"]["denyWrite"],
        )

    def test_can_disable_sandbox_settings_for_workspace_mode_off(self):
        ws = init_workspace("sandbox-disabled", sandbox_enabled=False)
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertFalse(sandbox["enabled"])
        self.assertFalse(sandbox["failIfUnavailable"])
        self.assertFalse(sandbox["autoAllowBashIfSandboxed"])
        self.assertTrue(sandbox["allowUnsandboxedCommands"])
        self.assertNotIn("enableWeakerNestedSandbox", sandbox)

    def test_can_disable_sandbox_network_access(self):
        ws = init_workspace(
            "sandbox-network-disabled",
            sandbox_network_mode="disabled",
            sandbox_network_allowed_domains=["github.com"],
        )
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertEqual(
            sandbox["network"],
            {"allowedDomains": [], "deniedDomains": ["*"]},
        )

    def test_can_pre_allow_sandbox_network_domains(self):
        ws = init_workspace(
            "sandbox-network-allowlist",
            sandbox_network_mode="allowlist",
            sandbox_network_allowed_domains=["github.com", "*.npmjs.org", "github.com"],
        )
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertEqual(
            sandbox["network"],
            {"allowedDomains": ["github.com", "*.npmjs.org"]},
        )

    def test_can_open_sandbox_network_access(self):
        ws = init_workspace(
            "sandbox-network-open",
            sandbox_network_mode="open",
            sandbox_network_allowed_domains=["github.com"],
        )
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertNotIn("network", sandbox)

    def test_enabled_sandbox_allows_claude_tmpdir_writes(self):
        """Claude Code's sandbox TMPDIR (cwd-* shell-hook files) is writable
        by default — kills the zsh operation-not-permitted noise."""
        ws = init_workspace("sandbox-claude-tmp")
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
        self.assertEqual(allow_write[0], str(ws.resolve()))
        self.assertEqual(allow_write[1:], _sandbox_claude_tmp_write_paths())

    def test_claude_tmpdir_env_override_is_honored(self):
        with unittest.mock.patch.dict(
            os.environ, {"CLAUDE_TMPDIR": "/custom/claude-tmp"}
        ):
            ws = init_workspace("sandbox-claude-tmp-env")
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
        self.assertIn("/custom/claude-tmp", allow_write)

    def test_extra_fs_write_paths_appended_after_workspace_and_tmp(self):
        ws = init_workspace(
            "sandbox-fs-extra",
            sandbox_fs_allowed_write_paths=[
                "/data/out",
                "relative/bad",
                "/data/out/",
                "/var/cache",
            ],
        )
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        allow_write = sandbox["filesystem"]["allowWrite"]
        # Relative paths dropped, trailing-slash dedupe, order preserved:
        # workspace → claude tmp → user extras.
        self.assertEqual(
            allow_write,
            [
                str(ws.resolve()),
                *_sandbox_claude_tmp_write_paths(),
                "/data/out",
                "/var/cache",
            ],
        )
        # denyWrite list is unchanged (deny always wins over allow).
        self.assertEqual(
            sandbox["filesystem"]["denyWrite"],
            [
                str(ws.resolve() / ".claude" / "settings.json"),
                str(ws.resolve() / ".claude" / "settings.local.json"),
                str(ws.resolve() / ".claude" / "hooks"),
                str(ws.resolve() / ".claude" / ".clawhub"),
                str(ws.resolve() / ".claude" / "worktrees"),
                str(ws.resolve() / ".editor"),
                str(ws.resolve() / ".mcp.json"),
            ],
        )

    def test_disabled_sandbox_write_policy_unchanged(self):
        """sandbox_enabled=False keeps the pre-feature allowWrite shape."""
        ws = init_workspace("sandbox-fs-disabled", sandbox_enabled=False)
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertFalse(sandbox["enabled"])
        self.assertEqual(
            sandbox["filesystem"]["allowWrite"],
            [str(ws.resolve())],
        )

    def test_can_enable_weaker_nested_sandbox_for_docker(self):
        with unittest.mock.patch(
            "libs.claude_agent_kit.server.workspace._running_in_linux_container",
            return_value=True,
        ):
            ws = init_workspace("sandbox-docker-nested")

        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        sandbox = settings["sandbox"]
        self.assertTrue(sandbox["enabled"])
        self.assertTrue(sandbox["enableWeakerNestedSandbox"])

    def test_sandbox_allow_read_includes_runtime_deps_but_not_project_root(self):
        ws = init_workspace("sandbox-runtime-read")
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        allow_read = settings["sandbox"]["filesystem"]["allowRead"]
        project_root = Path(__file__).resolve().parents[2].resolve()

        self.assertEqual(allow_read[0], str(ws.resolve()))
        self.assertIn(str(Path(tempfile.gettempdir()).resolve(strict=False)), allow_read)
        for raw_path in ("/sbin", "/usr/sbin", "/usr/local/sbin"):
            system_path = Path(raw_path)
            if system_path.exists():
                self.assertIn(str(system_path.resolve(strict=False)), allow_read)
        self.assertNotIn(str(project_root), allow_read)

    def test_sandbox_allow_read_accepts_explicit_extra_runtime_paths(self):
        extra_dir = Path(self._tmp.name) / "runtime-extra"
        extra_dir.mkdir()

        with unittest.mock.patch.dict(
            os.environ,
            {
                "AGENT_CWD": self._tmp.name,
                SANDBOX_EXTRA_ALLOW_READ_ENV: str(extra_dir),
            },
            clear=False,
        ):
            ws = init_workspace("sandbox-extra-runtime")

        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        allow_read = settings["sandbox"]["filesystem"]["allowRead"]
        self.assertIn(str(extra_dir.resolve()), allow_read)

    def test_sandbox_read_allow_preserves_literal_symlink_aliases(self):
        target = Path(self._tmp.name) / "runtime-target"
        alias = Path(self._tmp.name) / "runtime-alias"
        target.mkdir()
        alias.symlink_to(target, target_is_directory=True)

        paths: list[Path] = []
        _append_existing_sandbox_read_path(paths, alias, preserve_alias=True)

        self.assertIn(alias, paths)
        self.assertIn(target.resolve(strict=False), paths)

    def test_sandbox_settings_sync_preserves_non_sandbox_settings(self):
        ws = init_workspace("sandbox-preserve")
        settings_path = ws / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["language"] = "chinese"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        sync_workspace_sandbox_settings(ws, enabled=False)
        updated = json.loads(settings_path.read_text())
        self.assertEqual(updated["language"], "chinese")
        self.assertFalse(updated["sandbox"]["enabled"])


class TestGetOrCreateWorkspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_returns_same_path_for_same_session(self):
        ws1 = get_or_create_workspace("conv-abc")
        ws2 = get_or_create_workspace("conv-abc")
        self.assertEqual(ws1, ws2)

    def test_different_sessions_get_different_paths(self):
        ws1 = get_or_create_workspace("conv-111")
        ws2 = get_or_create_workspace("conv-222")
        self.assertNotEqual(ws1, ws2)

    def test_creates_workspace_skeleton_on_first_call(self):
        ws = get_or_create_workspace("fresh-session")
        for subdir in WORKSPACE_SUBDIRS:
            self.assertTrue((ws / subdir).is_dir(), f"missing {subdir}/")

    def test_returns_existing_path_without_error(self):
        ws1 = get_or_create_workspace("existing")
        ws2 = get_or_create_workspace("existing")
        self.assertEqual(ws1, ws2)
        self.assertTrue(ws2.is_dir())

    def test_passes_sandbox_enabled_flag_to_init(self):
        ws = get_or_create_workspace("sandbox-off-entry", sandbox_enabled=False)
        settings = json.loads((ws / ".claude" / "settings.json").read_text())
        self.assertFalse(settings["sandbox"]["enabled"])


class TestSkillsSync(unittest.TestCase):
    """Workspace skill sync should accept both user-facing and Claude-facing writes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_imports_new_directory_created_directly_in_claude_skills(self):
        ws = init_workspace("skills-direct-create")
        direct_skill = ws / ".claude" / "skills" / "direct-skill"
        direct_skill.mkdir()
        (direct_skill / "SKILL.md").write_text("direct create", encoding="utf-8")

        init_workspace("skills-direct-create")

        workspace_skill = ws / "skills" / "direct-skill"
        claude_skill = ws / ".claude" / "skills" / "direct-skill"
        self.assertTrue(workspace_skill.is_dir())
        self.assertEqual(
            (workspace_skill / "SKILL.md").read_text(encoding="utf-8"),
            "direct create",
        )
        self.assertTrue(claude_skill.is_symlink())
        self.assertEqual(claude_skill.resolve(), workspace_skill.resolve())

    def test_replaces_workspace_skill_from_direct_claude_skill_file(self):
        ws = init_workspace("skills-direct-replace")
        workspace_skill = ws / "skills" / "replace-me.md"
        workspace_skill.write_text("old", encoding="utf-8")
        init_workspace("skills-direct-replace")

        claude_skill = ws / ".claude" / "skills" / "replace-me.md"
        self.assertTrue(claude_skill.is_symlink())
        claude_skill.unlink()
        claude_skill.write_text("new", encoding="utf-8")

        init_workspace("skills-direct-replace")

        self.assertEqual(workspace_skill.read_text(encoding="utf-8"), "new")
        self.assertTrue(claude_skill.is_symlink())
        self.assertEqual(claude_skill.resolve(), workspace_skill.resolve())


class TestSessionIdValidation(unittest.TestCase):
    """Workspace functions should reject dangerous session IDs."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    def test_rejects_session_id_with_slash(self):
        from claude_agent.thread_pool import _validate_session_id
        with self.assertRaises(ValueError):
            _validate_session_id("../../etc/passwd")

    def test_rejects_session_id_with_double_dot(self):
        from claude_agent.thread_pool import _validate_session_id
        with self.assertRaises(ValueError):
            _validate_session_id("..evil")

    def test_rejects_session_id_with_backslash(self):
        from claude_agent.thread_pool import _validate_session_id
        with self.assertRaises(ValueError):
            _validate_session_id("a\\b")

    def test_accepts_plain_user_id(self):
        from claude_agent.thread_pool import _validate_session_id
        _validate_session_id("user_42")  # should not raise


class TestEditorIndexInit(unittest.TestCase):
    """Tests for the .editor/ virtual-index initialisation driven by _init_editor_index.

    The .editor/ directory is the workspace-layer prerequisite for the
    PreToolUse read-path redirect described in
    docs/design/claude-agent/edit-point/workspace-adapter.md §9.2.

    Assertions cover:
    - directory created by init_workspace
    - one placeholder JSON per EDITOR_RESOURCES stem
    - placeholder content is always empty-JSON ``{}``
    - README.md created with non-empty content
    - placeholder files are NOT overwritten on repeat init (preserving any
      early writes so the agent can continue from an existing session)
    - README.md IS refreshed on every init (instructions stay in sync)
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENT_CWD"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AGENT_CWD", None)
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    # Directory and file existence
    # ------------------------------------------------------------------

    def test_editor_directory_created(self):
        ws = init_workspace("editor-init-001")
        self.assertTrue((ws / ".editor").is_dir())

    def test_editor_readme_created(self):
        ws = init_workspace("editor-init-002")
        readme = ws / ".editor" / "README.md"
        self.assertTrue(readme.is_file())
        self.assertGreater(readme.stat().st_size, 0)

    def test_placeholder_files_created_for_all_resources(self):
        ws = init_workspace("editor-init-003")
        editor_dir = ws / ".editor"
        for stem in EDITOR_RESOURCES:
            placeholder = editor_dir / f"{stem}.json"
            self.assertTrue(placeholder.is_file(), f"missing .editor/{stem}.json")

    # ------------------------------------------------------------------
    # Placeholder content
    # ------------------------------------------------------------------

    def test_placeholder_content_is_empty_json(self):
        ws = init_workspace("editor-init-004")
        editor_dir = ws / ".editor"
        for stem in EDITOR_RESOURCES:
            content = (editor_dir / f"{stem}.json").read_text(encoding="utf-8")
            self.assertEqual(
                content.strip(),
                "{}",
                f".editor/{stem}.json should contain empty JSON, got {content!r}",
            )

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_placeholder_not_overwritten_on_repeat_init(self):
        """Existing placeholder files must survive a second init_workspace call.

        This mirrors the .editor/ idempotency contract: once a placeholder exists
        (possibly modified by a running agent session) it is never silently reset,
        so the agent can continue from its last checkpoint without data loss.
        """
        ws = init_workspace("editor-init-005")
        cells_json = ws / ".editor" / "cells.json"
        cells_json.write_text('{"cells": ["custom"]}', encoding="utf-8")

        # Re-init must NOT reset the file.
        init_workspace("editor-init-005")
        self.assertEqual(
            cells_json.read_text(encoding="utf-8"),
            '{"cells": ["custom"]}',
        )

    def test_readme_refreshed_on_repeat_init(self):
        """README.md should be rewritten on every init to keep instructions current."""
        ws = init_workspace("editor-init-006")
        readme = ws / ".editor" / "README.md"
        original_content = readme.read_text(encoding="utf-8")

        # Overwrite with stale content, then re-init.
        readme.write_text("stale content", encoding="utf-8")
        init_workspace("editor-init-006")
        self.assertEqual(
            readme.read_text(encoding="utf-8"),
            original_content,
            "README.md should be refreshed with the canonical template on re-init",
        )

    # ------------------------------------------------------------------
    # Interaction with standard workspace skeleton
    # ------------------------------------------------------------------

    def test_editor_dir_created_alongside_standard_subdirs(self):
        ws = init_workspace("editor-init-007")
        for subdir in WORKSPACE_SUBDIRS:
            self.assertTrue((ws / subdir).is_dir(), f"standard dir {subdir}/ missing")
        self.assertTrue((ws / ".editor").is_dir())


if __name__ == "__main__":
    unittest.main()
