import io
import unittest
from argparse import Namespace
from unittest.mock import patch

from paperpilot.cli import review as review_cli
from paperpilot.cli.review import _keyword_args, _settings_and_clients, build_parser
from paperpilot.models.results import StageResult
from paperpilot.utils.config import AISettings, AppSettings, ZoteroSettings


class ReviewCliTest(unittest.TestCase):
    def test_read_parser_accepts_local_pdf_options(self):
        args = build_parser().parse_args([
            "read",
            "--slug",
            "world-models",
            "--paper-id",
            "P001",
            "--no-local-pdfs",
            "--pdf-max-pages",
            "20",
        ])
        self.assertEqual(args.command, "read")
        self.assertEqual(args.paper_id, ["P001"])
        self.assertTrue(args.no_local_pdfs)
        self.assertEqual(args.pdf_max_pages, 20)

    def test_qc_parser_accepts_draft_path(self):
        args = build_parser().parse_args([
            "qc",
            "--slug",
            "world-models",
            "--draft-path",
            "reports/custom_draft.md",
        ])
        self.assertEqual(args.command, "qc")
        self.assertEqual(args.draft_path, "reports/custom_draft.md")

    def test_matrix_parser_accepts_include_tiers(self):
        args = build_parser().parse_args([
            "matrix",
            "--slug",
            "world-models",
            "--include-tier",
            "A",
            "--include-tier",
            "B",
        ])
        self.assertEqual(args.command, "matrix")
        self.assertEqual(args.include_tier, ["A", "B"])

    def test_verify_parser_accepts_storage_and_skip_zotero(self):
        args = build_parser().parse_args([
            "verify",
            "--slug",
            "world-models",
            "--include-tier",
            "A",
            "--storage-dir",
            "/tmp/zotero",
            "--skip-zotero",
        ])
        self.assertEqual(args.command, "verify")
        self.assertEqual(args.include_tier, ["A"])
        self.assertEqual(args.storage_dir, "/tmp/zotero")
        self.assertTrue(args.skip_zotero)

    def test_fetch_pdfs_parser_accepts_automation_options(self):
        args = build_parser().parse_args([
            "fetch-pdfs",
            "--slug",
            "world-models",
            "--include-tier",
            "A",
            "--unpaywall-email",
            "user@example.com",
            "--output-dir",
            "/tmp/pdfs",
            "--attach-zotero",
            "--dry-run",
            "--limit",
            "2",
        ])
        self.assertEqual(args.command, "fetch-pdfs")
        self.assertEqual(args.include_tier, ["A"])
        self.assertEqual(args.unpaywall_email, "user@example.com")
        self.assertEqual(args.output_dir, "/tmp/pdfs")
        self.assertTrue(args.attach_zotero)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.limit, 2)

    def test_curate_parser_accepts_keywords(self):
        args = build_parser().parse_args([
            "curate",
            "--slug",
            "world-models",
            "--include-keyword",
            "robotics,world model",
            "--exclude-keyword",
            "clinical",
            "--apply",
        ])
        self.assertEqual(args.command, "curate")
        self.assertTrue(args.apply)
        self.assertEqual(_keyword_args(args.include_keyword), ("robotics", "world model"))
        self.assertEqual(_keyword_args(args.exclude_keyword), ("clinical",))

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

    @patch("paperpilot.cli.review.DeepXivClient")
    @patch("paperpilot.cli.review.WatchService")
    @patch("paperpilot.cli.review.LiteratureReviewService")
    @patch("paperpilot.cli.review.AIClient")
    @patch("paperpilot.cli.review.ZoteroClient")
    @patch("paperpilot.cli.review.load_app_settings")
    def test_run_uses_arxiv_only_unless_deepxiv_requested(
        self,
        load_settings,
        zotero_client,
        ai_client,
        review_service,
        watch_service,
        deepxiv_client,
    ):
        load_settings.return_value = AppSettings(
            zotero=ZoteroSettings(user_id="123", api_key="zkey"),
            notion=None,
            ai=AISettings(provider="openai", api_key="akey", model="gpt-test"),
        )
        zotero_client.return_value.iter_items.return_value = []

        service = review_service.return_value
        service.init_project.return_value = StageResult(stage="review:init")
        service.build_pool_from_zotero_items.return_value = StageResult(stage="review:build-pool")
        service.read_and_code.return_value = StageResult(stage="review:read")
        service.draft_review.return_value = StageResult(stage="review:draft")
        watch_service.return_value.search_and_import.return_value = StageResult(
            stage="watch",
            artifacts={"managed_keys": []},
        )

        with patch("sys.stdout", io.StringIO()), patch(
            "sys.argv",
            [
                "prog",
                "review",
                "run",
                "--topic",
                "agent memory",
                "--slug",
                "agent-memory",
            ],
        ):
            review_cli.main()

        deepxiv_client.assert_not_called()
        self.assertIsNone(watch_service.call_args.kwargs["deepxiv"])


if __name__ == "__main__":
    unittest.main()
