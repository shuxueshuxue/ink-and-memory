# [Input] Consume libs/claude_agent_kit/server/sdk_env.py apply_cli_path_to_options.
# [Output] Verify CLI binary resolution: CLAUDE_CODE_CLI_PATH override (existing path),
#          missing-path warning + fallthrough, shutil.which hit, bundled fallback
#          (unset), explicit cli_path preserved.
# [Pos] test node in backend/tests
# [Sync] 2026-07-26: initial — cli_path resolution coverage for the Docker
#                    apply-seccomp-patched npm CLI pinning (claude-sdk-env-design).

"""Tests for sdk_env.apply_cli_path_to_options (2026-07-26)."""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sdk_stubs  # noqa: F401
import libs.claude_agent_kit.server.sdk_env as sdk_env_module
from libs.claude_agent_kit.server.sdk_env import apply_cli_path_to_options


def _make_options(cli_path=None) -> types.SimpleNamespace:
    return types.SimpleNamespace(cli_path=cli_path)


class TestApplyCliPathToOptions(unittest.TestCase):
    def _env(self, **vars: str):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_CLI_PATH"}
        env.update(vars)
        return unittest.mock.patch.dict(os.environ, env, clear=True)

    def test_env_override_honored_when_path_exists(self):
        with tempfile.NamedTemporaryFile() as cli:
            options = _make_options()
            with self._env(CLAUDE_CODE_CLI_PATH=cli.name):
                result = apply_cli_path_to_options(options)
        self.assertIs(result, options)
        self.assertEqual(options.cli_path, cli.name)

    def test_missing_env_path_falls_through_to_which_with_warning(self):
        options = _make_options()
        with (
            self._env(CLAUDE_CODE_CLI_PATH="/nonexistent/claude"),
            unittest.mock.patch.object(
                sdk_env_module.shutil, "which", return_value="/usr/local/bin/claude"
            ),
            self.assertLogs(sdk_env_module.logger, level="WARNING") as logs,
        ):
            apply_cli_path_to_options(options)
        self.assertEqual(options.cli_path, "/usr/local/bin/claude")
        self.assertTrue(any("CLAUDE_CODE_CLI_PATH" in m for m in logs.output))

    def test_which_hit_sets_cli_path_when_env_unset(self):
        options = _make_options()
        with (
            self._env(),
            unittest.mock.patch.object(
                sdk_env_module.shutil, "which", return_value="/opt/npm/bin/claude"
            ),
        ):
            apply_cli_path_to_options(options)
        self.assertEqual(options.cli_path, "/opt/npm/bin/claude")

    def test_no_system_claude_leaves_cli_path_unset(self):
        """Bundled fallback: no env, no which() hit → cli_path stays None."""
        options = _make_options()
        with (
            self._env(),
            unittest.mock.patch.object(
                sdk_env_module.shutil, "which", return_value=None
            ),
        ):
            apply_cli_path_to_options(options)
        self.assertIsNone(options.cli_path)

    def test_explicit_cli_path_preserved(self):
        options = _make_options(cli_path="/explicit/claude")
        with tempfile.NamedTemporaryFile() as cli:
            with self._env(CLAUDE_CODE_CLI_PATH=cli.name):
                apply_cli_path_to_options(options)
        self.assertEqual(options.cli_path, "/explicit/claude")

    def test_explicit_cli_path_preserved_over_which(self):
        options = _make_options(cli_path="/explicit/claude")
        with (
            self._env(),
            unittest.mock.patch.object(
                sdk_env_module.shutil, "which", return_value="/usr/local/bin/claude"
            ),
        ):
            apply_cli_path_to_options(options)
        self.assertEqual(options.cli_path, "/explicit/claude")

    def test_which_checked_with_claude_name(self):
        options = _make_options()
        with (
            self._env(),
            unittest.mock.patch.object(
                sdk_env_module.shutil, "which", return_value=None
            ) as which_mock,
        ):
            apply_cli_path_to_options(options)
        which_mock.assert_called_once_with("claude")


if __name__ == "__main__":
    unittest.main()
