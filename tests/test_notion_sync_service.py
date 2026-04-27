import unittest

from paperpilot.services.notion_sync_service import (
    NotionSyncOptions,
    NotionSyncService,
    build_notion_properties,
    build_property_mapping,
)


class FakeNotion:
    def __init__(self):
        self.created = []
        self.updated = []

    def get_database(self):
        return {
            "properties": {
                "Paper Title": {"type": "title"},
                "Authors": {"type": "multi_select"},
                "Year": {"type": "number"},
                "Abstract": {"type": "rich_text"},
                "Tags": {"type": "multi_select"},
                "URL": {"type": "url"},
                "DOI": {"type": "rich_text"},
                "Zotero Key": {"type": "rich_text"},
            }
        }

    def query_by_text(self, prop_name, text):
        return None

    def query_by_title(self, title_prop, title):
        return None

    def create_page(self, props):
        self.created.append(props)
        return "page_1"

    def update_page(self, page_id, props):
        self.updated.append((page_id, props))


class NotionSyncServiceTest(unittest.TestCase):
    def test_build_property_mapping(self):
        mapping = build_property_mapping(FakeNotion().get_database())
        self.assertEqual(mapping["title"]["name"], "Paper Title")
        self.assertEqual(mapping["zotero_key"]["name"], "Zotero Key")

    def test_build_notion_properties(self):
        item = {
            "data": {
                "key": "ABCD1234",
                "title": "Test Paper",
                "creators": [{"firstName": "A", "lastName": "B"}],
                "date": "2024-01-01",
                "abstractNote": "Abstract here",
                "tags": [{"tag": "VLA"}],
                "url": "https://example.com",
                "DOI": "10.1234/test",
            }
        }
        mapping = build_property_mapping(FakeNotion().get_database())
        props = build_notion_properties(item, mapping)
        self.assertIn("Paper Title", props)
        self.assertIn("Authors", props)
        self.assertIn("Zotero Key", props)

    def test_sync_items_create(self):
        notion = FakeNotion()
        service = NotionSyncService(notion)
        items = [{"data": {"key": "ABCD1234", "title": "Test Paper"}}]
        result = service.sync_items(items, NotionSyncOptions(limit=10, dry_run=False, skip_untitled=True))
        self.assertEqual(result.created, 1)
        self.assertEqual(len(notion.created), 1)

    def test_sync_items_dry_run(self):
        notion = FakeNotion()
        service = NotionSyncService(notion)
        items = [{"data": {"key": "ABCD1234", "title": "Test Paper"}}]
        result = service.sync_items(items, NotionSyncOptions(limit=10, dry_run=True, skip_untitled=True))
        self.assertEqual(result.created, 1)
        self.assertEqual(len(notion.created), 0)


if __name__ == "__main__":
    unittest.main()
