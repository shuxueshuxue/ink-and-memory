# [Input] Notion operation normalization and discovery helpers.
# [Output] Verify discovery filters system-only Notion resources from user-selectable lists.
# [Pos] test node in backend/tests
# [Sync] 2026-07-08: cover filtering of Notion People system data sources from database discovery.

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion import operations


class TestNotionOperations(unittest.IsolatedAsyncioTestCase):
    async def test_discover_databases_filters_people_system_database(self):
        client = operations.NotionOperationClient(config={})

        async def fake_search(self, search_filter):
            del self, search_filter
            return operations.SearchResult(
                results=[
                    {
                        "id": "people-db",
                        "object": "data_source",
                        "title": [{"plain_text": "People"}],
                        "properties": {
                            "Name": {"id": "title", "name": "Name", "type": "title"},
                            "Person": {"id": "people%3Aperson", "name": "Person", "type": "people"},
                            "Membership Type": {
                                "id": "people%3Amembership_type",
                                "name": "Membership Type",
                                "type": "select",
                                "select": {
                                    "options": [
                                        {"id": "owner", "name": "Workspace owner"},
                                        {"id": "membership_admin", "name": "Membership admin"},
                                        {"id": "member", "name": "Member"},
                                    ]
                                },
                            },
                        },
                    },
                    {
                        "id": "project-db",
                        "object": "data_source",
                        "title": [{"plain_text": "Projects"}],
                        "properties": {
                            "Name": {"id": "title", "name": "Name", "type": "title"},
                            "Status": {"id": "status", "name": "Status", "type": "select"},
                        },
                    },
                ],
                has_more=False,
                next_cursor=None,
            )

        client.search = MethodType(fake_search, client)

        databases = await client.discover_databases()

        self.assertEqual([item["database_id"] for item in databases], ["project-db"])
        self.assertEqual(databases[0]["title"], "Projects")


if __name__ == "__main__":
    unittest.main()
