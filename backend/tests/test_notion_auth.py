# [Input] Notion auth CLI helpers.
# [Output] Verify login parsing, poll classification, and Notion home/env setup.
# [Pos] test node in backend/tests
# [Sync] 2026-07-04: initial auth helper coverage for Notion CLI login flows.

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion import auth as notion_auth


class TestNotionAuthHelpers(unittest.IsolatedAsyncioTestCase):
    def test_resolve_notion_home_prefers_configured_value(self):
        resolved = notion_auth.resolve_notion_home({"notion_home": "~/custom-notion"})
        self.assertTrue(str(resolved).endswith("custom-notion"))

    def test_build_notion_env_sets_notion_home(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = notion_auth.build_notion_env({"notion_home": tmp_dir})

        self.assertEqual(env["NOTION_HOME"], tmp_dir)
        self.assertIn("PATH", env)

    async def test_start_login_parses_verification_url_and_code(self):
        async def fake_run(*args, **kwargs):
            self.assertEqual(args, ("login", "--no-browser"))
            return 0, (
                "Open this URL in your browser to log in:\n"
                "https://www.notion.so/workers/cli-login?verificationCode=VAF-HWY\n"
                "Confirm that this verification code matches: VAF-HWY\n"
            ), ""

        with unittest.mock.patch.object(notion_auth, "_run_ntn_command", side_effect=fake_run):
            result = await notion_auth.start_login({"notion_home": "/tmp/notion-home"})

        self.assertEqual(
            result.verification_url,
            "https://www.notion.so/workers/cli-login?verificationCode=VAF-HWY",
        )
        self.assertEqual(result.verification_code, "VAF-HWY")
        self.assertEqual(result.notion_home, "/tmp/notion-home")

    async def test_poll_login_classifies_pending_output(self):
        async def fake_run(*args, **kwargs):
            self.assertEqual(args, ("login", "poll"))
            return 1, "", "authorization_pending"

        with unittest.mock.patch.object(notion_auth, "_run_ntn_command", side_effect=fake_run):
            result = await notion_auth.poll_login({"notion_home": "/tmp/notion-home"})

        self.assertEqual(result.status, "pending")
        self.assertEqual(result.notion_home, "/tmp/notion-home")

    async def test_poll_login_classifies_no_pending_session_output(self):
        async def fake_run(*args, **kwargs):
            self.assertEqual(args, ("login", "poll"))
            return 1, "", "No pending login session found."

        with unittest.mock.patch.object(notion_auth, "_run_ntn_command", side_effect=fake_run):
            result = await notion_auth.poll_login({"notion_home": "/tmp/notion-home"})

        self.assertEqual(result.status, "pending")
        self.assertEqual(result.notion_home, "/tmp/notion-home")
        self.assertIn("No pending login session found", result.detail)

    async def test_verify_status_reports_authenticated(self):
        async def fake_run(*args, **kwargs):
            self.assertEqual(args, ("auth", "status"))
            return 0, "authenticated", ""

        with unittest.mock.patch.object(notion_auth, "_run_ntn_command", side_effect=fake_run):
            result = await notion_auth.verify_status({"notion_home": "/tmp/notion-home"})

        self.assertEqual(result.status, "authenticated")
        self.assertEqual(result.detail, "authenticated")


if __name__ == "__main__":
    unittest.main()
