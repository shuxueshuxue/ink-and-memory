# [Input] Consume notion_snapshot.py contract helpers.
# [Output] Unit tests for Notion canonical snapshot virtual path resolution and proposal staleness.
# [Pos] test node in backend/tests
# [Sync] 2026-06-28: initial contract tests for resource-connector-owned canonical snapshots.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from libs.claude_agent_kit.server.notion_snapshot import (
    CanonicalWorkspaceSnapshot,
    SnapshotMetadata,
    SnapshotWriteProposal,
    get_notion_snapshot_resource_data,
    is_notion_snapshot_path,
    resolve_notion_snapshot_resource,
    snapshot_identity,
    write_proposal_is_stale,
)


class NotionSnapshotContractTest(unittest.TestCase):
    def _snapshot(self) -> CanonicalWorkspaceSnapshot:
        return CanonicalWorkspaceSnapshot(
            metadata=SnapshotMetadata(
                workspace_id="workspace-1",
                resource_connector_id="connector-1",
                snapshot_version="snap-001",
                source_revision="rev-001",
                sync_cursor="cursor-001",
                fetched_at="2026-06-28T00:00:00Z",
            ),
            connector={"platform": "notion", "auth_status": "authenticated"},
            index=[{"page_id": "page-1", "title": "Roadmap"}],
            databases=[{"database_id": "db-1", "title": "Tasks"}],
            database_pages={"db-1": [{"page_id": "page-1", "title": "Roadmap"}]},
            pages={"page-1": {"page_id": "page-1", "blocks": [{"type": "paragraph", "text": "Ship MVP"}]}},
        )

    def test_resolves_supported_notion_virtual_paths(self):
        self.assertTrue(is_notion_snapshot_path(".notion/connector.json"))
        self.assertTrue(is_notion_snapshot_path("/tmp/ws/.notion/pages/page-1.json"))
        self.assertEqual(resolve_notion_snapshot_resource(".notion/databases/db-1.json"), "databases/db-1")
        self.assertEqual(resolve_notion_snapshot_resource(".notion/pages/page-1.json"), "pages/page-1")
        self.assertIsNone(resolve_notion_snapshot_resource(".notion/pages/.json"))
        self.assertIsNone(resolve_notion_snapshot_resource(".notion/unknown.json"))

    def test_extracts_snapshot_resources_with_metadata(self):
        snapshot = self._snapshot()

        connector = get_notion_snapshot_resource_data(".notion/connector.json", snapshot)
        self.assertEqual(connector["platform"], "notion")
        self.assertEqual(connector["snapshot"]["snapshot_version"], "snap-001")

        index = get_notion_snapshot_resource_data(".notion/index.json", snapshot)
        self.assertEqual(index["pages"][0]["page_id"], "page-1")
        self.assertEqual(index["snapshot"]["source_revision"], "rev-001")

        page = get_notion_snapshot_resource_data(".notion/pages/page-1.json", snapshot)
        self.assertEqual(page["blocks"][0]["text"], "Ship MVP")
        self.assertEqual(page["snapshot"]["sync_cursor"], "cursor-001")

    def test_missing_page_reports_snapshot_scoped_miss(self):
        missing = get_notion_snapshot_resource_data(".notion/pages/page-missing.json", self._snapshot())

        self.assertTrue(missing["missing"])
        self.assertEqual(missing["reason"], "not_materialized_in_snapshot")
        self.assertEqual(missing["snapshot"]["snapshot_version"], "snap-001")

    def test_snapshot_identity_and_write_staleness(self):
        snapshot = self._snapshot()
        self.assertEqual(
            snapshot_identity(snapshot),
            {
                "workspace_id": "workspace-1",
                "resource_connector_id": "connector-1",
                "snapshot_version": "snap-001",
                "source_revision": "rev-001",
                "sync_cursor": "cursor-001",
            },
        )

        fresh = SnapshotWriteProposal(
            proposal_id="proposal-1",
            workspace_id="workspace-1",
            resource_connector_id="connector-1",
            base_snapshot_version="snap-001",
            base_source_revision="rev-001",
            base_sync_cursor="cursor-001",
        )
        stale = SnapshotWriteProposal(
            proposal_id="proposal-2",
            workspace_id="workspace-1",
            resource_connector_id="connector-1",
            base_snapshot_version="snap-old",
            base_source_revision="rev-001",
            base_sync_cursor="cursor-001",
        )

        self.assertFalse(write_proposal_is_stale(fresh, snapshot))
        self.assertTrue(write_proposal_is_stale(stale, snapshot))


if __name__ == "__main__":
    unittest.main()
