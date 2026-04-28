import unittest
from argparse import Namespace
from unittest.mock import patch

from paperpilot.cli.review import _settings_and_clients
from paperpilot.utils.config import AISettings, AppSettings, ZoteroSettings


class ReviewCliTest(unittest.TestCase):
    @patch("paperpilot.cli.review.ZoteroClient")
    @patch("paperpilot.cli.review.load_app_settings")
    def test_need_ai_requires_api_key(self, load_settings, zotero_client):
        load_settings.return_value = AppSettings(
            zotero=ZoteroSettings(user_id="123", api_key="zkey"),
            notion=None,
            ai=AISettings(provider="openai", api_key=None, model="gpt-test"),
        )

        with self.assertRaises(SystemExit) as ctx:
            _settings_and_clients(Namespace(model=None), need_ai=True)

        self.assertIn("AI API key is required", str(ctx.exception))

    @patch("paperpilot.cli.review.ZoteroClient")
    @patch("paperpilot.cli.review.load_app_settings")
    def test_need_ai_requires_model(self, load_settings, zotero_client):
        load_settings.return_value = AppSettings(
            zotero=ZoteroSettings(user_id="123", api_key="zkey"),
            notion=None,
            ai=AISettings(provider="openai", api_key="akey", model=None),
        )

        with self.assertRaises(SystemExit) as ctx:
            _settings_and_clients(Namespace(model=None), need_ai=True)

        self.assertIn("AI model is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
