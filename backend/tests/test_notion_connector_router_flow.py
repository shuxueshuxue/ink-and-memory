# [Input] Notion connector router and facade wiring for the business flow.
# [Output] Exercise the create → auth → resources → sync path through the real
#          FastAPI router with a temp SQLite store and mocked Notion CLI calls.
# [Pos] test node in backend/tests
# [Sync] 2026-07-04: route-level business flow coverage for Notion connector
#                    create/auth/discovery/selection/sync.
# [Sync] 2026-07-08: assert selected sources hydrate through connector responses so
#                    Settings refresh and Chat linked-resource summaries stay in sync.

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from notion import auth as notion_auth
from notion import operations as notion_operations
from notion import store as notion_store
from notion import sync as notion_sync
from routers import notion as notion_router


class TestNotionConnectorRouterFlow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "notion-connectors.db"
        self._old_db_path = notion_store.DB_PATH
        notion_store.DB_PATH = self._db_path
        self._notion_home = str(Path(self._tmp.name) / "notion-home")
        self._workspace_id = "workspace-business"
        self._snapshot_version = "snap-business-001"
        self._source_revision = "rev-business-001"
        self._sync_cursor = "cursor-business-001"
        self._patches = [
            patch.object(
                notion_auth,
                "start_login",
                new=AsyncMock(side_effect=self._mock_start_login),
            ),
            patch.object(
                notion_auth,
                "poll_login",
                new=AsyncMock(side_effect=self._mock_poll_login),
            ),
            patch.object(
                notion_operations,
                "discover_databases",
                new=AsyncMock(side_effect=self._mock_discover_databases),
            ),
            patch.object(
                notion_operations,
                "discover_pages",
                new=AsyncMock(side_effect=self._mock_discover_pages),
            ),
            patch.object(
                notion_sync,
                "build_canonical_snapshot",
                new=AsyncMock(side_effect=self._mock_build_snapshot),
            ),
        ]
        for patcher in self._patches:
            patcher.start()

        app = FastAPI()
        app.dependency_overrides[notion_router.get_current_user] = (
            lambda: {"user_id": 7, "email": "board@example.com"}
        )
        app.include_router(notion_router.router)
        self.client = TestClient(app)
        self.snapshot_calls: list[dict[str, object]] = []

    def tearDown(self):
        self.client.close()
        for patcher in reversed(self._patches):
            patcher.stop()
        notion_store.DB_PATH = self._old_db_path
        self._tmp.cleanup()

    def _mock_start_login(self, config=None):
        del config
        return notion_auth.LoginInitResult(
            verification_url="https://www.notion.so/workers/cli-login?verificationCode=VAF-HWY",
            verification_code="VAF-HWY",
            poll_interval_seconds=5,
            notion_home=self._notion_home,
        )

    def _mock_poll_login(self, config=None):
        del config
        return notion_auth.AuthStatusResult(
            status="authenticated",
            notion_home=self._notion_home,
            detail="authenticated",
        )

    def _mock_discover_databases(self, config=None, query=None, page_size=100):
        del config, query, page_size
        return [
            {
                "database_id": "db-team",
                "title": "Team Knowledge",
                "url": "https://www.notion.so/db-team",
                "page_count": 2,
                "properties_schema": {"Name": {"type": "title"}},
                "last_edited": "2026-07-04T13:30:00Z",
            }
        ]

    def _mock_discover_pages(self, config=None, query=None, page_size=100):
        del config, query, page_size
        return [
            {
                "page_id": "page-team",
                "title": "Team Notes",
                "url": "https://www.notion.so/page-team",
                "last_edited": "2026-07-04T13:30:00Z",
            }
        ]

    def _mock_build_snapshot(self, connector, selected_resources, workspace_id, operations):
        del operations
        selected_database_ids = [
            str(resource.get("external_id") or "")
            for resource in selected_resources
            if resource.get("resource_type") == "notion_database"
        ]
        selected_page_ids = [
            str(resource.get("external_id") or "")
            for resource in selected_resources
            if resource.get("resource_type") == "notion_page"
        ]
        self.snapshot_calls.append(
            {
                "connector_id": connector["id"],
                "workspace_id": workspace_id,
                "database_ids": selected_database_ids,
                "page_ids": selected_page_ids,
            }
        )
        return {
            "metadata": {
                "workspace_id": workspace_id,
                "resource_connector_id": str(connector["id"]),
                "snapshot_version": self._snapshot_version,
                "source_revision": self._source_revision,
                "sync_cursor": self._sync_cursor,
                "fetched_at": "2026-07-04T13:30:00Z",
                "state": "snapshot_ready",
            },
            "connector": {
                "id": connector["id"],
                "platform": "notion",
                "auth_status": "authenticated",
                "selected_databases": selected_database_ids,
                "selected_pages": selected_page_ids,
            },
            "index": [
                {
                    "page_id": "page-team",
                    "title": "Team Notes",
                    "url": "https://www.notion.so/page-team",
                    "last_edited": "2026-07-04T13:30:00Z",
                }
            ],
            "databases": [
                {
                    "database_id": "db-team",
                    "title": "Team Knowledge",
                    "page_count": 2,
                    "properties_schema": {"Name": {"type": "title"}},
                    "last_edited": "2026-07-04T13:30:00Z",
                    "url": "https://www.notion.so/db-team",
                }
            ],
            "database_pages": {
                "db-team": [
                    {
                        "page_id": "page-team",
                        "title": "Team Notes",
                        "last_edited": "2026-07-04T13:30:00Z",
                    }
                ]
            },
            "pages": {
                "page-team": {
                    "page_id": "page-team",
                    "title": "Team Notes",
                    "url": "https://www.notion.so/page-team",
                    "last_edited": "2026-07-04T13:30:00Z",
                    "blocks": [{"type": "paragraph", "text": "Ship the connector"}],
                }
            },
            "identity": {
                "workspace_id": workspace_id,
                "resource_connector_id": str(connector["id"]),
                "snapshot_version": self._snapshot_version,
                "source_revision": self._source_revision,
                "sync_cursor": self._sync_cursor,
            },
        }

    def test_connector_router_happy_path(self):
        create_response = self.client.post(
            "/api/connectors",
            json={
                "name": "Notion Resource Connector",
                "platform": "notion",
                "notion_home": self._notion_home,
            },
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        connector = create_response.json()["connector"]
        connector_id = connector["id"]
        self.assertEqual(connector["auth_status"], "pending")
        self.assertEqual(connector["config"]["notion_home"], self._notion_home)

        login_response = self.client.post(
            f"/api/connectors/{connector_id}/auth/login",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        login_payload = login_response.json()
        self.assertEqual(login_payload["verificationCode"], "VAF-HWY")
        self.assertEqual(login_payload["connector"]["auth_status"], "pending")

        poll_response = self.client.post(
            f"/api/connectors/{connector_id}/auth/poll",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(poll_response.status_code, 200, poll_response.text)
        poll_payload = poll_response.json()
        self.assertEqual(poll_payload["status"], "authenticated")
        self.assertEqual(poll_payload["connector"]["auth_status"], "authenticated")

        databases_response = self.client.get(
            f"/api/connectors/{connector_id}/databases",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(databases_response.status_code, 200, databases_response.text)
        databases = databases_response.json()["databases"]
        self.assertEqual(databases[0]["database_id"], "db-team")
        self.assertFalse(databases[0]["selected"])

        pages_response = self.client.get(
            f"/api/connectors/{connector_id}/pages",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(pages_response.status_code, 200, pages_response.text)
        pages = pages_response.json()["pages"]
        self.assertEqual(pages[0]["page_id"], "page-team")
        self.assertFalse(pages[0]["selected"])

        select_response = self.client.post(
            f"/api/connectors/{connector_id}/resources/select",
            json={
                "selected_databases": [databases[0]],
                "selected_pages": [pages[0]],
                "workspace_id": self._workspace_id,
            },
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(select_response.status_code, 200, select_response.text)
        select_payload = select_response.json()
        self.assertTrue(select_payload["synced"])
        self.assertEqual(select_payload["databaseCount"], 1)
        self.assertEqual(select_payload["pageCount"], 1)
        self.assertEqual(select_payload["snapshotIdentity"]["workspace_id"], self._workspace_id)
        self.assertEqual(select_payload["snapshotIdentity"]["snapshot_version"], self._snapshot_version)

        selected_resources_response = self.client.get(
            f"/api/connectors/{connector_id}/resources",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(selected_resources_response.status_code, 200, selected_resources_response.text)
        selected_resources = selected_resources_response.json()["resources"]
        self.assertEqual(len(selected_resources), 2)
        self.assertEqual(
            {resource["resource_type"] for resource in selected_resources},
            {"notion_database", "notion_page"},
        )

        databases_again_response = self.client.get(
            f"/api/connectors/{connector_id}/databases",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(databases_again_response.status_code, 200, databases_again_response.text)
        self.assertTrue(databases_again_response.json()["databases"][0]["selected"])

        pages_again_response = self.client.get(
            f"/api/connectors/{connector_id}/pages",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(pages_again_response.status_code, 200, pages_again_response.text)
        self.assertTrue(pages_again_response.json()["pages"][0]["selected"])

        sync_response = self.client.post(
            f"/api/connectors/{connector_id}/sync",
            json={"workspace_id": self._workspace_id},
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(sync_response.status_code, 200, sync_response.text)
        sync_payload = sync_response.json()
        self.assertTrue(sync_payload["synced"])
        self.assertEqual(sync_payload["databaseCount"], 1)
        self.assertEqual(sync_payload["pageCount"], 1)

        final_connector_response = self.client.get(
            f"/api/connectors/{connector_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(final_connector_response.status_code, 200, final_connector_response.text)
        final_connector = final_connector_response.json()["connector"]
        self.assertEqual(final_connector["current_snapshot_version"], self._snapshot_version)
        self.assertEqual(final_connector["current_source_revision"], self._source_revision)
        self.assertEqual(final_connector["selected_databases"], ["db-team"])
        self.assertEqual(final_connector["selected_pages"], ["page-team"])
        self.assertEqual(
            {source["external_id"] for source in final_connector["sources"]},
            {"db-team", "page-team"},
        )
        self.assertEqual(len(self.snapshot_calls), 2)

    def test_connector_auth_poll_no_pending_session_does_not_regress_auth(self):
        create_response = self.client.post(
            "/api/connectors",
            json={
                "name": "Notion Resource Connector",
                "platform": "notion",
                "notion_home": self._notion_home,
            },
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        connector_id = create_response.json()["connector"]["id"]

        login_response = self.client.post(
            f"/api/connectors/{connector_id}/auth/login",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        polling_sequence = [
            notion_auth.AuthStatusResult(
                status="authenticated",
                notion_home=self._notion_home,
                detail="authenticated",
            ),
            notion_auth.AuthStatusResult(
                status="pending",
                notion_home=self._notion_home,
                detail="No pending login session found.",
            ),
        ]
        with patch.object(
            notion_auth,
            "poll_login",
            new=AsyncMock(side_effect=polling_sequence),
        ):
            first_poll = self.client.post(
                f"/api/connectors/{connector_id}/auth/poll",
                headers={"Authorization": "Bearer test-token"},
            )
            self.assertEqual(first_poll.status_code, 200, first_poll.text)
            first_payload = first_poll.json()
            self.assertEqual(first_payload["status"], "authenticated")
            self.assertEqual(first_payload["auth_status"], "authenticated")

            second_poll = self.client.post(
                f"/api/connectors/{connector_id}/auth/poll",
                headers={"Authorization": "Bearer test-token"},
            )
            self.assertEqual(second_poll.status_code, 200, second_poll.text)
            second_payload = second_poll.json()
            self.assertEqual(second_payload["status"], "authenticated")
            self.assertEqual(second_payload["auth_status"], "authenticated")

        final_connector = self.client.get(
            f"/api/connectors/{connector_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(final_connector.status_code, 200, final_connector.text)
        final_payload = final_connector.json()["connector"]
        self.assertEqual(final_payload["auth_status"], "authenticated")
        self.assertEqual(final_payload["config"].get("auth_session", {}).get("auth_session_status"), "authenticated")

    def test_connector_auth_poll_no_pending_session_without_auth_marks_error(self):
        create_response = self.client.post(
            "/api/connectors",
            json={
                "name": "Notion Resource Connector",
                "platform": "notion",
                "notion_home": self._notion_home,
            },
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        connector_id = create_response.json()["connector"]["id"]

        login_response = self.client.post(
            f"/api/connectors/{connector_id}/auth/login",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        with patch.object(
            notion_auth,
            "poll_login",
            new=AsyncMock(
                return_value=notion_auth.AuthStatusResult(
                    status="pending",
                    notion_home=self._notion_home,
                    detail="No pending login session found.",
                )
            ),
        ):
            poll_response = self.client.post(
                f"/api/connectors/{connector_id}/auth/poll",
                headers={"Authorization": "Bearer test-token"},
            )
            self.assertEqual(poll_response.status_code, 200, poll_response.text)
            poll_payload = poll_response.json()
            self.assertEqual(poll_payload["status"], "error")
            self.assertEqual(poll_payload["auth_status"], "error")

        final_connector = self.client.get(
            f"/api/connectors/{connector_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(final_connector.status_code, 200, final_connector.text)
        final_payload = final_connector.json()["connector"]
        self.assertEqual(final_payload["auth_status"], "error")
        self.assertEqual(
            final_payload.get("config", {})
            .get("auth_session", {})
            .get("auth_session_status"),
            "consumed",
        )


if __name__ == "__main__":
    unittest.main()
