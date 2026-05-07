import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

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

    def test_create_file_attachment_uploads_and_registers(self):
        client = ZoteroClient("1", "key")
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/items") and method == "post":
                return FakeResponse(["ATTACH1"])
            if url.endswith("/items/ATTACH1/file") and kwargs.get("data", {}).get("upload"):
                response = MagicMock()
                response.json.return_value = {}
                return response
            if url.endswith("/items/ATTACH1/file"):
                response = MagicMock()
                response.json.return_value = {
                    "url": "https://upload.example.test",
                    "contentType": "multipart/form-data; boundary=x",
                    "prefix": "PREFIX",
                    "suffix": "SUFFIX",
                    "uploadKey": "UPLOAD1",
                }
                return response
            raise AssertionError(url)

        client._request = fake_request
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "_upload_file_with_retry") as upload:
            upload.return_value.raise_for_status.return_value = None
            path = Path(tmp) / "summary.html"
            path.write_text("<p>summary</p>", encoding="utf-8")

            key = client.create_file_attachment("PARENT1", path, title="Summary", content_type="text/html", tags=["AI精读附件"])

        self.assertEqual(key, "ATTACH1")
        self.assertEqual(calls[0][2]["json"][0]["linkMode"], "imported_file")
        self.assertEqual(calls[0][2]["json"][0]["parentItem"], "PARENT1")
        self.assertEqual(calls[-1][2]["data"], {"upload": "UPLOAD1"})
        self.assertIn(b"<p>summary</p>", upload.call_args.args[1])

    def test_update_note_preserves_existing_item_data(self):
        client = ZoteroClient("1", "key")
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method == "get":
                response = MagicMock()
                response.json.return_value = {
                    "key": "NOTE1",
                    "version": 12,
                    "data": {
                        "key": "NOTE1",
                        "version": 12,
                        "itemType": "note",
                        "parentItem": "PARENT1",
                        "note": "old",
                        "tags": [],
                    },
                }
                return response
            response = MagicMock()
            response.json.return_value = {}
            return response

        client._request = fake_request

        client.update_note("NOTE1", 7, "<h1>new</h1>", tags=["AI精读-v2"])

        put_call = calls[-1]
        self.assertEqual(put_call[0], "put")
        self.assertEqual(put_call[2]["json"]["parentItem"], "PARENT1")
        self.assertEqual(put_call[2]["json"]["note"], "<h1>new</h1>")
        self.assertEqual(put_call[2]["headers"], {"If-Unmodified-Since-Version": "12"})


if __name__ == "__main__":
    unittest.main()
