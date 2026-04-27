import unittest
from unittest.mock import Mock, patch

from paperpilot.clients.deepxiv import DeepXivClient


class DeepXivClientTest(unittest.TestCase):
    @patch("paperpilot.clients.deepxiv.Reader")
    def test_search_delegates_to_reader(self, mock_reader_cls):
        reader = Mock()
        reader.search.return_value = {"items": []}
        mock_reader_cls.return_value = reader

        client = DeepXivClient(token="abc")
        result = client.search("agent memory", limit=3)

        self.assertEqual(result, {"items": []})
        reader.search.assert_called_once_with("agent memory", size=3, search_mode="hybrid")

    @patch("paperpilot.clients.deepxiv.Reader")
    def test_brief_delegates_to_reader(self, mock_reader_cls):
        reader = Mock()
        reader.brief.return_value = {"title": "Paper"}
        mock_reader_cls.return_value = reader

        client = DeepXivClient()
        result = client.brief("2409.05591")

        self.assertEqual(result["title"], "Paper")
        reader.brief.assert_called_once_with("2409.05591")


if __name__ == "__main__":
    unittest.main()
