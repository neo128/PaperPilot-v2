"""Tests for the ArxivClient fallback."""

import unittest
from unittest.mock import MagicMock, patch

from paperpilot.clients.arxiv import ArxivClient


class ArxivClientTest(unittest.TestCase):
    def test_search_returns_list(self):
        """ArxivClient.search should return a list of paper dicts."""
        client = ArxivClient()
        # Use a very specific query that should return results
        results = client.search("large language model", limit=3)
        self.assertIsInstance(results, list)
        # arXiv API usually returns results for this query
        if results:
            first = results[0]
            self.assertIn("title", first)
            self.assertIn("arxiv_id", first)

    def test_search_recent_returns_list(self):
        """ArxivClient.search_recent should return recent papers."""
        client = ArxivClient()
        results = client.search_recent("transformer", limit=2, days=30)
        self.assertIsInstance(results, list)


class WatchServiceArxivFallbackTest(unittest.TestCase):
    def test_fallback_to_arxiv_when_deepxiv_fails(self):
        """WatchService should use arXiv when DeepXiv raises an exception."""
        from paperpilot.services.watch_service import WatchOptions, WatchService

        mock_zotero = MagicMock()
        mock_zotero.create_items.return_value = ["KEY1", "KEY2"]
        mock_deepxiv = MagicMock()
        mock_deepxiv.search.side_effect = RuntimeError("DeepXiv server down")
        mock_arxiv = MagicMock()
        mock_arxiv.search_recent.return_value = [
            {
                "arxiv_id": "2504.00001",
                "title": "Test Paper via arXiv Fallback",
                "abstract": "This is a test abstract.",
                "authors": [{"name": "Alice"}, {"name": "Bob"}],
                "published": "2026-04-01",
                "src_url": "https://arxiv.org/pdf/2504.00001.pdf",
            }
        ]

        service = WatchService(zotero=mock_zotero, deepxiv=mock_deepxiv, arxiv=mock_arxiv)
        result = service.search_and_import(WatchOptions(query="test query", limit=5))

        # Should have used arXiv fallback
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 2)  # mock returns 2 keys
        self.assertEqual(result.artifacts.get("source"), "arxiv")

        # Verify Zotero was called with properly structured items
        call_args = mock_zotero.create_items.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["title"], "Test Paper via arXiv Fallback")

    def test_uses_deepxiv_when_available(self):
        """WatchService should prefer DeepXiv when it works."""
        from paperpilot.services.watch_service import WatchOptions, WatchService

        mock_zotero = MagicMock()
        mock_zotero.create_items.return_value = ["KEY1"]
        mock_deepxiv = MagicMock()
        mock_deepxiv.search.return_value = {"items": [{"arxiv_id": "2504.00002", "title": "DeepXiv Paper"}]}
        mock_arxiv = MagicMock()

        service = WatchService(zotero=mock_zotero, deepxiv=mock_deepxiv, arxiv=mock_arxiv)
        result = service.search_and_import(WatchOptions(query="test", limit=5))

        self.assertEqual(result.artifacts.get("source"), "deepxiv")
        # arXiv should NOT have been called
        mock_arxiv.search_recent.assert_not_called()

    def test_handles_both_failing(self):
        """WatchService should handle both DeepXiv and arXiv failing."""
        from paperpilot.services.watch_service import WatchOptions, WatchService

        mock_zotero = MagicMock()
        mock_deepxiv = MagicMock()
        mock_deepxiv.search.side_effect = RuntimeError("DeepXiv down")
        mock_arxiv = MagicMock()
        mock_arxiv.search_recent.side_effect = RuntimeError("arXiv also down")

        service = WatchService(zotero=mock_zotero, deepxiv=mock_deepxiv, arxiv=mock_arxiv)
        result = service.search_and_import(WatchOptions(query="test", limit=5))

        self.assertEqual(result.processed, 0)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.artifacts.get("source"), "none")


if __name__ == "__main__":
    unittest.main()
