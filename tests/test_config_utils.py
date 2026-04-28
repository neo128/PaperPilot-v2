import os
import tempfile
import unittest
from pathlib import Path

from paperpilot.utils.env import load_dotenv_if_present, require_env, optional_env
from paperpilot.utils.config import load_app_settings


class ConfigUtilsTest(unittest.TestCase):
    def test_load_dotenv_if_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("FOO=bar\n# comment\nBAZ=qux\n", encoding="utf-8")
            load_dotenv_if_present(env_path)
            self.assertEqual(os.environ.get("FOO"), "bar")
            self.assertEqual(os.environ.get("BAZ"), "qux")

    def test_require_env(self):
        os.environ["REQ_TEST"] = "ok"
        self.assertEqual(require_env("REQ_TEST"), "ok")

    def test_optional_env(self):
        self.assertEqual(optional_env("MISSING_ENV", "fallback"), "fallback")

    def test_load_app_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "ZOTERO_USER_ID=123\nZOTERO_API_KEY=abc\nNOTION_API_KEY=nk\nNOTION_DATABASE_ID=ndb\nAI_PROVIDER=openai\nAI_MODEL=gpt-test\n",
                encoding="utf-8",
            )
            # Clear existing env vars so setdefault picks up temp values
            for key in ["ZOTERO_USER_ID", "ZOTERO_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID", "AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "OPENAI_API_KEY"]:
                os.environ.pop(key, None)
            settings = load_app_settings(env_path)
            self.assertEqual(settings.zotero.user_id, "123")
            self.assertEqual(settings.zotero.api_key, "abc")
            self.assertEqual(settings.notion.database_id, "ndb")
            self.assertEqual(settings.ai.model, "gpt-test")

    def test_load_app_settings_uses_openai_api_key_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ZOTERO_USER_ID=123\nZOTERO_API_KEY=abc\nOPENAI_API_KEY=okey\n", encoding="utf-8")
            for key in ["ZOTERO_USER_ID", "ZOTERO_API_KEY", "AI_API_KEY", "OPENAI_API_KEY"]:
                os.environ.pop(key, None)
            settings = load_app_settings(env_path)
            self.assertEqual(settings.ai.api_key, "okey")


if __name__ == "__main__":
    unittest.main()
