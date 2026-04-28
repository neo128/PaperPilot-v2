import unittest
from unittest.mock import MagicMock

import requests

from paperpilot.clients.zotero import parse_next_link
from paperpilot.clients.zotero import ZoteroClient


class FakeResponse:
    def __init__(self, keys):
        self._keys = keys

    def json(self):
        return {"successful": {str(index): {"key": key} for index, key in enumerate(self._keys)}}


class ZoteroClientHelpersTest(unittest.TestCase):
    def test_parse_next_link(self):
        header = '<https://api.zotero.org/users/1/items?start=100>; rel="next", <https://api.zotero.org/users/1/items?start=0>; rel="first"'
        self.assertEqual(
            parse_next_link(header),
            "https://api.zotero.org/users/1/items?start=100",
        )

    def test_parse_next_link_none(self):
        self.assertIsNone(parse_next_link(None))

    def test_create_items_batches_requests(self):
        client = ZoteroClient("1", "key")
        calls = []

        def fake_request(method, url, **kwargs):
            payload = kwargs["json"]
            calls.append(payload)
            return FakeResponse([f"KEY{len(calls)}_{i}" for i, _ in enumerate(payload)])

        client._request = fake_request

        keys = client.create_items([{"title": str(i)} for i in range(60)])

        self.assertEqual([len(call) for call in calls], [25, 25, 10])
        self.assertEqual(len(keys), 60)

    def test_create_items_splits_on_413(self):
        client = ZoteroClient("1", "key")
        calls = []

        def fake_request(method, url, **kwargs):
            payload = kwargs["json"]
            calls.append(len(payload))
            if len(payload) > 1:
                response = MagicMock()
                response.status_code = 413
                raise requests.exceptions.HTTPError(response=response)
            return FakeResponse([f"KEY_{len(calls)}"])

        client._request = fake_request

        keys = client.create_items([{"title": "a"}, {"title": "b"}, {"title": "c"}])

        self.assertEqual(len(keys), 3)
        self.assertIn(3, calls)
        self.assertIn(2, calls)
        self.assertEqual(calls.count(1), 3)


if __name__ == "__main__":
    unittest.main()
