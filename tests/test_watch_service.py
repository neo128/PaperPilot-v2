import unittest

from paperpilot.services.watch_service import (
    WatchOptions,
    WatchService,
    build_literature_search_queries,
    build_zotero_item,
)


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
        self.existing = None
        self.added_to_collections = []

    def create_collection_if_missing(self, name):
        return "COL123"

    def find_existing_item(self, candidate):
        return self.existing

    def add_item_to_collection(self, item_key, collection_key):
        self.added_to_collections.append((item_key, collection_key))
        return True

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
        self.assertEqual(item["DOI"], "")

    def test_build_zotero_item_limits_large_fields(self):
        item = build_zotero_item(
            {
                "title": "T" * 2000,
                "authors": [{"name": f"Author {i}"} for i in range(25)],
                "abstract": "<p>" + ("A" * 20000) + "</p>",
                "url": "https://example.com/" + ("u" * 3000),
                "doi": "10.123/" + ("d" * 1000),
                "venue": "V" * 2000,
            }
        )

        self.assertLessEqual(len(item["title"]), 1000)
        self.assertEqual(len(item["creators"]), 20)
        self.assertLessEqual(len(item["abstractNote"]), 8000)
        self.assertLessEqual(len(item["url"]), 2000)
        self.assertLessEqual(len(item["DOI"]), 500)
        self.assertLessEqual(len(item["publicationTitle"]), 1000)
        self.assertNotIn("<p>", item["abstractNote"])

    def test_build_literature_search_queries(self):
        queries = build_literature_search_queries("agent memory", prompt="long-term autonomous agent")
        self.assertIn("agent memory benchmark", queries)
        self.assertIn("agent memory survey", queries)
        self.assertIn("long-term autonomous agent", queries)
        self.assertEqual(len(queries), len(set(q.lower() for q in queries)))

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

    def test_search_and_import_reuses_existing_zotero_item(self):
        zotero = FakeZotero()
        zotero.existing = {"key": "EXISTING1", "data": {"key": "EXISTING1", "title": "Test Paper"}}
        service = WatchService(zotero=zotero, deepxiv=FakeDeepXiv(), arxiv=FakeArxiv())

        result = service.search_and_import(WatchOptions(query="agent memory", dry_run=False))

        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        self.assertIsNone(zotero.created_payloads)
        self.assertEqual(result.artifacts["existing_keys"], ["EXISTING1"])
        self.assertEqual(result.artifacts["managed_keys"], ["EXISTING1"])

    def test_search_and_import_adds_existing_item_to_collection(self):
        zotero = FakeZotero()
        zotero.existing = {"key": "EXISTING1", "data": {"key": "EXISTING1", "title": "Test Paper"}}
        service = WatchService(zotero=zotero, deepxiv=FakeDeepXiv(), arxiv=FakeArxiv())

        result = service.search_and_import(
            WatchOptions(query="agent memory", create_collections=True, collection_name="Review Pool", dry_run=False)
        )

        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 1)
        self.assertEqual(zotero.added_to_collections, [("EXISTING1", "COL123")])

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
