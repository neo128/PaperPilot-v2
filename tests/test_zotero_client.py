import unittest

from paperpilot.clients.zotero import parse_next_link


class ZoteroClientHelpersTest(unittest.TestCase):
    def test_parse_next_link(self):
        header = '<https://api.zotero.org/users/1/items?start=100>; rel="next", <https://api.zotero.org/users/1/items?start=0>; rel="first"'
        self.assertEqual(
            parse_next_link(header),
            "https://api.zotero.org/users/1/items?start=100",
        )

    def test_parse_next_link_none(self):
        self.assertIsNone(parse_next_link(None))


if __name__ == "__main__":
    unittest.main()
