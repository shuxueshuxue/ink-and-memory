# [Input] Notion connector SQLite store and canonical snapshot persistence.
# [Output] Verify connector CRUD, resource selection persistence, and snapshot
#          identity storage.
# [Pos] test node in backend/tests
# [Sync] 2026-07-04: initial store coverage for Notion connector persistence.
# [Sync] 2026-07-08: cover connector list/detail sources hydration for refresh-safe
#                    resource selections.

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.claude_agent_kit.server.notion_snapshot import (
    CanonicalWorkspaceSnapshot,
    SnapshotMetadata,
    snapshot_identity,
)
from notion import store


class TestNotionStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "notion-connectors.db"
        self._old_db_path = store.DB_PATH
        store.DB_PATH = self._db_path

    def tearDown(self):
        store.DB_PATH = self._old_db_path
        self._tmp.cleanup()

    def _sample_snapshot(self, connector_id: str, workspace_id: str = "workspace-1") -> CanonicalWorkspaceSnapshot:
        metadata = SnapshotMetadata(
            workspace_id=workspace_id,
            resource_connector_id=connector_id,
            snapshot_version="snap-001",
            source_revision="rev-001",
            sync_cursor="cursor-001",
            fetched_at="2026-07-04T00:00:00Z",
        )
        return CanonicalWorkspaceSnapshot(
            metadata=metadata,
            connector={
                "id": connector_id,
                "platform": "notion",
                "auth_status": "authenticated",
                "selected_databases": ["db-1"],
                "selected_pages": ["page-standalone"],
            },
            index=[
                {"page_id": "page-db-1", "title": "Database Page", "url": "https://www.notion.so/page-db-1", "last_edited": "2026-07-03T10:00:00Z"},
                {"page_id": "page-standalone", "title": "Standalone Page", "url": "https://www.notion.so/page-standalone", "last_edited": "2026-07-02T10:00:00Z"},
            ],
            databases=[
                {
                    "database_id": "db-1",
                    "title": "Tasks",
                    "page_count": 1,
                    "properties_schema": {"Name": {"type": "title"}},
                    "last_edited": "2026-07-03T10:00:00Z",
                    "url": "https://www.notion.so/db-1",
                }
            ],
            database_pages={
                "db-1": [
                    {
                        "page_id": "page-db-1",
                        "title": "Database Page",
                        "last_edited": "2026-07-03T10:00:00Z",
                        "status": "In Progress",
                    }
                ]
            },
            pages={
                "page-db-1": {
                    "page_id": "page-db-1",
                    "title": "Database Page",
                    "url": "https://www.notion.so/page-db-1",
                    "last_edited": "2026-07-03T10:00:00Z",
                    "properties": {"Name": {"title": [{"plain_text": "Database Page"}]}},
                    "blocks": [{"type": "paragraph", "text": "Ship it"}],
                },
                "page-standalone": {
                    "page_id": "page-standalone",
                    "title": "Standalone Page",
                    "url": "https://www.notion.so/page-standalone",
                    "last_edited": "2026-07-02T10:00:00Z",
                    "properties": {"Name": {"title": [{"plain_text": "Standalone Page"}]}},
                    "blocks": [{"type": "paragraph", "text": "Read me"}],
                },
            },
        )

    def test_connector_resource_selection_and_snapshot_roundtrip(self):
        connector = store.create_connector(7, name="Notion", config={"notion_home": "/tmp/notion-home"})
        self.assertEqual(connector["auth_status"], "pending")
        self.assertEqual(store.list_connectors(7)[0]["id"], connector["id"])

        updated = store.save_auth_state(
            connector["id"],
            7,
            auth_status="authenticated",
            config_patch={"notion_home": "/tmp/notion-home"},
            verification_url="https://www.notion.so/workers/cli-login",
            verification_code="VAF-HWY",
            poll_interval_seconds=5,
        )
        self.assertEqual(updated["auth_status"], "authenticated")

        selected = store.replace_connector_resources(
            connector["id"],
            7,
            databases=[
                {
                    "database_id": "db-1",
                    "title": "Tasks",
                    "page_count": 1,
                    "properties_schema": {"Name": {"type": "title"}},
                    "last_edited": "2026-07-03T10:00:00Z",
                    "url": "https://www.notion.so/db-1",
                }
            ],
            pages=[
                {
                    "page_id": "page-standalone",
                    "title": "Standalone Page",
                    "last_edited": "2026-07-02T10:00:00Z",
                    "url": "https://www.notion.so/page-standalone",
                }
            ],
        )
        self.assertEqual(len(selected["resources"]), 2)
        self.assertEqual(selected["connector"]["selected_databases"], ["db-1"])
        self.assertEqual(selected["connector"]["selected_pages"], ["page-standalone"])
        self.assertEqual(len(selected["connector"]["sources"]), 2)
        self.assertEqual(selected["connector"]["sources"][0]["external_id"], "db-1")
        self.assertEqual(store.list_connectors(7)[0]["sources"][0]["external_id"], "db-1")
        self.assertEqual(store.get_connector(connector["id"], 7)["sources"][1]["external_id"], "page-standalone")

        snapshot = self._sample_snapshot(connector["id"])
        saved = store.save_snapshot(connector["id"], 7, "workspace-1", snapshot)
        self.assertEqual(saved["metadata"]["snapshot_version"], "snap-001")
        self.assertEqual(snapshot_identity(saved)["resource_connector_id"], connector["id"])

        current = store.get_current_snapshot("workspace-1", connector["id"], 7)
        self.assertIsNotNone(current)
        self.assertEqual(current["metadata"]["snapshot_version"], "snap-001")
        self.assertEqual(current["pages"]["page-standalone"]["title"], "Standalone Page")
        self.assertEqual(store.list_snapshots(connector["id"], 7)[0]["snapshot"]["metadata"]["snapshot_version"], "snap-001")
        self.assertEqual(len(store.list_connector_resources(connector["id"], 7)), 2)

    def test_attach_thread_finds_connector(self):
        connector = store.create_connector(7, name="Notion")
        store.attach_thread_to_connector(connector["id"], 7, "thread-1")

        found = store.get_connector_for_thread("thread-1", 7)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], connector["id"])


if __name__ == "__main__":
    unittest.main()
