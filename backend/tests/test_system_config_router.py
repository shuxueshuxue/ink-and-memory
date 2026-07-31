# [Input] Consume backend/routers/system_config.py FastAPI router.
# [Output] Verify Settings system-config save responses include sanitized data.
# [Pos] test node in backend/tests
# [Sync] 2026-06-25: cover PUT /api/system-config returning merged sandbox
#                    network config so frontend Settings can hydrate after save.
# [Sync] 2026-07-26: cover sandbox_fs_allowed_write_paths sanitizer (absolute-
#                    only, trailing-slash strip, dedupe, caps) via PUT.

"""Regression tests for the system-config router."""
from __future__ import annotations

import sys
import unittest
import unittest.mock
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routers import system_config as system_config_router


class TestSystemConfigRouter(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.dependency_overrides[system_config_router.get_current_user] = (
            lambda: {"user_id": 7, "email": "settings@example.com"}
        )
        app.include_router(system_config_router.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_put_returns_merged_sanitized_sandbox_network_config(self):
        saved_patch: dict = {}

        def save_config(user_id: int, patch: dict) -> None:
            self.assertEqual(user_id, 7)
            saved_patch.update(patch)

        def get_config(user_id: int) -> dict:
            self.assertEqual(user_id, 7)
            return {"workspace_enabled": True, **saved_patch}

        with (
            unittest.mock.patch.object(
                system_config_router.database,
                "save_system_config",
                side_effect=save_config,
            ),
            unittest.mock.patch.object(
                system_config_router.database,
                "get_system_config",
                side_effect=get_config,
            ),
        ):
            response = self.client.put(
                "/api/system-config",
                json={
                    "sandbox_network_mode": "allowlist",
                    "sandbox_network_allowed_domains": [
                        "HTTPS://Raw.GitHubUserContent.com/path/file.txt",
                        "*.githubusercontent.com",
                        "githubusercontent.com",
                        "*",
                        "raw.githubusercontent.com",
                    ],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["data"],
            {
                "workspace_enabled": True,
                "sandbox_network_mode": "allowlist",
                "sandbox_network_allowed_domains": [
                    "raw.githubusercontent.com",
                    "*.githubusercontent.com",
                    "githubusercontent.com",
                ],
            },
        )


class TestSandboxFsAllowedWritePathsSanitizer(unittest.TestCase):
    """_sanitize_sandbox_fs_allowed_write_paths contract."""

    def _sanitize(self, raw):
        return system_config_router._sanitize_sandbox_fs_allowed_write_paths(raw)

    def test_accepts_absolute_paths_only(self):
        self.assertEqual(
            self._sanitize(["/data/out", "relative/path", "", "  ", "~/x", "data"]),
            ["/data/out"],
        )

    def test_strips_trailing_slashes_except_root(self):
        self.assertEqual(
            self._sanitize(["/data/out/", "/", "//"]),
            ["/data/out", "/"],
        )

    def test_dedupes_preserving_order(self):
        self.assertEqual(
            self._sanitize(["/b", "/a", "/b/", "/a", "/c"]),
            ["/b", "/a", "/c"],
        )

    def test_accepts_separated_string_input(self):
        self.assertEqual(
            self._sanitize("/data/out\n/data/cache, relative/bad;/data/logs"),
            ["/data/out", "/data/cache", "/data/logs"],
        )

    def test_rejects_non_list_non_string_input(self):
        self.assertEqual(self._sanitize(None), [])
        self.assertEqual(self._sanitize(42), [])
        self.assertEqual(self._sanitize({"path": "/x"}), [])

    def test_rejects_non_string_entries_silently(self):
        self.assertEqual(
            self._sanitize(["/ok", None, 123, ["nested"], "/ok2"]),
            ["/ok", "/ok2"],
        )

    def test_caps_entry_count(self):
        limit = system_config_router._SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_ENTRIES
        result = self._sanitize([f"/p{i}" for i in range(limit + 10)])
        self.assertEqual(len(result), limit)
        self.assertEqual(result[0], "/p0")

    def test_caps_path_length(self):
        limit = system_config_router._SANDBOX_FS_ALLOWED_WRITE_PATH_MAX_LEN
        result = self._sanitize(["/" + "a" * (limit + 50)])
        self.assertEqual(result, [("/" + "a" * (limit + 50))[:limit]])


class TestSandboxFsAllowedWritePathsPut(unittest.TestCase):
    """PUT /api/system-config wires the fs write paths key like the domains key."""

    def setUp(self):
        app = FastAPI()
        app.dependency_overrides[system_config_router.get_current_user] = (
            lambda: {"user_id": 7, "email": "settings@example.com"}
        )
        app.include_router(system_config_router.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_put_returns_merged_sanitized_fs_write_paths(self):
        saved_patch: dict = {}

        def save_config(user_id: int, patch: dict) -> None:
            saved_patch.update(patch)

        def get_config(user_id: int) -> dict:
            return {"workspace_enabled": True, **saved_patch}

        with (
            unittest.mock.patch.object(
                system_config_router.database,
                "save_system_config",
                side_effect=save_config,
            ),
            unittest.mock.patch.object(
                system_config_router.database,
                "get_system_config",
                side_effect=get_config,
            ),
        ):
            response = self.client.put(
                "/api/system-config",
                json={
                    "sandbox_fs_allowed_write_paths": [
                        "/data/out/",
                        "relative/bad",
                        "/data/out",
                        "/var/cache",
                    ],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["data"],
            {
                "workspace_enabled": True,
                "sandbox_fs_allowed_write_paths": ["/data/out", "/var/cache"],
            },
        )


if __name__ == "__main__":
    unittest.main()
