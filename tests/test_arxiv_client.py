"""Tests for the ArxivClient fallback."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from paperpilot.clients.arxiv import ArxivClient, _build_search_query


ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2504.00001v1</id>
    <published>2026-04-01T00:00:00Z</published>
    <title>Test Paper via arXiv</title>
    <summary>This is a test abstract.</summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <link href="http://arxiv.org/abs/2504.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2504.00001v1" rel="related" type="application/pdf"/>
    <arxiv:doi>10.48550/arXiv.2504.00001</arxiv:doi>
  </entry>
</feed>
"""


class FakeResponse:
    text = ARXIV_ATOM


class ArxivClientTest(unittest.TestCase):
    def test_build_search_query_uses_keywords_for_plain_text(self):
        self.assertEqual(
            _build_search_query("active exploration with world models in embodied AI"),
            "all:active AND all:exploration AND all:world AND all:models AND all:embodied AND all:ai",
        )
        self.assertEqual(
            _build_search_query("all:active AND all:exploration"),
            "all:active AND all:exploration",
        )

    @patch("paperpilot.clients.arxiv.request_with_retry", return_value=FakeResponse())
    def test_search_returns_list(self, _request):
        """ArxivClient.search should return a list of paper dicts."""
        client = ArxivClient()
        results = client.search("large language model", limit=3)
        self.assertIsInstance(results, list)
        first = results[0]
        self.assertEqual(first["title"], "Test Paper via arXiv")
        self.assertEqual(first["arxiv_id"], "2504.00001v1")
        self.assertEqual(first["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(first["doi"], "10.48550/arXiv.2504.00001")

    @patch("paperpilot.clients.arxiv.request_with_retry", return_value=FakeResponse())
    def test_search_recent_returns_list(self, _request):
        """ArxivClient.search_recent should return recent papers."""
        client = ArxivClient()
        results = client.search_recent("transformer", limit=2, days=30)
        self.assertIsInstance(results, list)
        self.assertEqual(results[0]["title"], "Test Paper via arXiv")

    @patch(
        "paperpilot.clients.arxiv.request_with_retry",
        side_effect=[requests.exceptions.SSLError("transient EOF"), FakeResponse()],
    )
    def test_search_retries_transient_request_failures(self, request):
        client = ArxivClient()
        results = client.search_recent("active exploration with world models in embodied AI", limit=2)

        self.assertEqual(results[0]["title"], "Test Paper via arXiv")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[0].kwargs["params"]["search_query"],
            "all:active AND all:exploration AND all:world AND all:models AND all:embodied AND all:ai",
        )


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
