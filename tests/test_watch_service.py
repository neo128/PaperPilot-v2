import unittest

from paperpilot.services.watch_service import WatchOptions, WatchService, build_zotero_item


class FakeDeepXiv:
    def search(self, query, limit=10):
        return {
            "items": [
                {
                    "title": "Test Paper",
                    "authors": [{"name": "Alice"}, {"name": "Bob"}],
                    "abstract": "Test abstract",
                    "src_url": "https://arxiv.org/abs/2401.00001",
                    "arxiv_id": "2401.00001",
                    "published": "2024-01-01",
                }
            ]
        }


class FakeArxiv:
    def search_recent(self, query, limit=10, days=30):
        return [
            {
                "title": "Arxiv Fallback Paper",
                "authors": [{"name": "Charlie"}],
                "abstract": "Arxiv abstract",
                "src_url": "https://arxiv.org/abs/2401.00002",
                "arxiv_id": "2401.00002",
                "published": "2024-01-02",
            }
        ]


class FakeZotero:
    def __init__(self):
        self.created_payloads = None

    def create_collection_if_missing(self, name):
        return "COL123"

    def create_items(self, payloads):
        self.created_payloads = payloads
        return ["ITEM123"]


class WatchServiceTest(unittest.TestCase):
    def test_build_zotero_item(self):
        item = build_zotero_item(
            {
                "title": "Test Paper",
                "authors": [{"name": "Alice"}],
                "abstract": "Abstract",
                "src_url": "https://arxiv.org/abs/2401.00001",
                "arxiv_id": "2401.00001",
                "published": "2024-01-01",
            },
            collection_key="COL123",
        )
        self.assertEqual(item["title"], "Test Paper")
        self.assertEqual(item["collections"], ["COL123"])
        self.assertEqual(item["archiveLocation"], "2401.00001")

    def test_search_and_import_dry_run(self):
        zotero = FakeZotero()
        service = WatchService(zotero=zotero, deepxiv=FakeDeepXiv(), arxiv=FakeArxiv())
        result = service.search_and_import(WatchOptions(query="agent memory", dry_run=True))
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 1)

    def test_search_and_import_accepts_deepxiv_results_key(self):
        zotero = FakeZotero()

        class DeepXivResultsFormat:
            def search(self, query, limit=10):
                return {
                    "total": 1,
                    "results": [
                        {
                            "title": "DeepXiv Result",
                            "authors": [{"name": "Dana"}],
                            "abstract": "DeepXiv abstract",
                            "arxiv_id": "2402.03824",
                            "publish_at": "2024-02-06 00:00:00",
                        }
                    ],
                }

        service = WatchService(zotero=zotero, deepxiv=DeepXivResultsFormat(), arxiv=FakeArxiv())
        result = service.search_and_import(WatchOptions(query="embodied ai", dry_run=True))
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.artifacts.get("source"), "deepxiv")

    def test_search_and_import_real(self):
        zotero = FakeZotero()
        service = WatchService(zotero=zotero, deepxiv=FakeDeepXiv(), arxiv=FakeArxiv())
        result = service.search_and_import(
            WatchOptions(query="agent memory", create_collections=True, collection_name="AI Papers", dry_run=False)
        )
        self.assertEqual(result.created, 1)
        self.assertIsNotNone(zotero.created_payloads)

    def test_arxiv_fallback_when_deepxiv_fails(self):
        """Should fall back to arXiv when DeepXiv raises an exception."""
        zotero = FakeZotero()

        class BrokenDeepXiv:
            def search(self, query, limit=10):
                raise RuntimeError("DeepXiv server down")

        service = WatchService(zotero=zotero, deepxiv=BrokenDeepXiv(), arxiv=FakeArxiv())
        result = service.search_and_import(WatchOptions(query="test", dry_run=True))
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.artifacts.get("source"), "arxiv")

    def test_no_results_when_both_fail(self):
        """Should return zero results when both DeepXiv and arXiv fail."""
        zotero = FakeZotero()

        class BrokenDeepXiv:
            def search(self, query, limit=10):
                raise RuntimeError("DeepXiv down")

        class BrokenArxiv:
            def search_recent(self, query, limit=10, days=30):
                raise RuntimeError("arXiv down")

        service = WatchService(zotero=zotero, deepxiv=BrokenDeepXiv(), arxiv=BrokenArxiv())
        result = service.search_and_import(WatchOptions(query="test", dry_run=True))
        self.assertEqual(result.processed, 0)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.artifacts.get("source"), "none")


if __name__ == "__main__":
    unittest.main()
