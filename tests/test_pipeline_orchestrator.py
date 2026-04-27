import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paperpilot.models.results import StageResult
from paperpilot.pipeline.config import NotionStageConfig, PipelineConfig, SummaryStageConfig, WatchStageConfig
from paperpilot.pipeline.orchestrator import PipelineOrchestrator


class FakeWatchService:
    def search_and_import(self, options):
        return StageResult(stage="watch", processed=1, created=1)


class FakeSummaryService:
    def summarize_items(self, items, options, insert_note=True):
        return StageResult(stage="summary", processed=len(items), created=max(len(items), 0))


class FakeNotionService:
    def sync_items(self, items, options):
        return StageResult(stage="notion-sync", processed=len(items), created=max(len(items), 0))


class PipelineOrchestratorTest(unittest.TestCase):
    @patch("paperpilot.pipeline.orchestrator.load_app_settings")
    @patch("paperpilot.pipeline.orchestrator.ZoteroClient")
    @patch("paperpilot.pipeline.orchestrator.AIClient")
    def test_run_watch_summary_and_notion(self, mock_ai, mock_zotero_cls, mock_settings):
        with tempfile.TemporaryDirectory() as tmp:
            mock_settings.return_value = type("S", (), {
                "zotero": type("Z", (), {"user_id": "1", "api_key": "key", "storage_dir": None})(),
                "ai": type("A", (), {"provider": "openai", "base_url": None, "api_key": "x", "model": "m"})(),
                "notion": type("N", (), {"api_key": "nk", "database_id": "db"})(),
            })()
            zotero = mock_zotero_cls.return_value
            zotero.iter_items.return_value = [{"data": {"key": "A", "title": "Paper"}}]
            zotero.list_child_collections.return_value = []
            zotero.resolve_collection_key.return_value = None

            orchestrator = PipelineOrchestrator(PipelineConfig(
                state_db_path=Path(tmp) / "state.sqlite3",
                watch=WatchStageConfig(enabled=True, query="agent memory", dry_run=True),
                summary=SummaryStageConfig(enabled=True, limit=5),
                notion=NotionStageConfig(enabled=True, limit=5, dry_run=True),
            ))
            orchestrator.watch_service = FakeWatchService()
            orchestrator.summary_service = FakeSummaryService()
            orchestrator.notion_service = FakeNotionService()

            result = orchestrator.run()
            self.assertEqual(len(result.stages), 3)
            self.assertTrue(result.success)
            self.assertTrue((Path(tmp) / "state.sqlite3").exists())
            orchestrator.close()

    @patch("paperpilot.pipeline.orchestrator.load_app_settings")
    @patch("paperpilot.pipeline.orchestrator.ZoteroClient")
    @patch("paperpilot.pipeline.orchestrator.AIClient")
    def test_incremental_skips_success_items(self, mock_ai, mock_zotero_cls, mock_settings):
        with tempfile.TemporaryDirectory() as tmp:
            mock_settings.return_value = type("S", (), {
                "zotero": type("Z", (), {"user_id": "1", "api_key": "key", "storage_dir": None})(),
                "ai": type("A", (), {"provider": "openai", "base_url": None, "api_key": "x", "model": "m"})(),
                "notion": type("N", (), {"api_key": "nk", "database_id": "db"})(),
            })()
            zotero = mock_zotero_cls.return_value
            zotero.iter_items.return_value = [{"data": {"key": "A", "title": "Paper"}}]
            zotero.list_child_collections.return_value = []
            zotero.resolve_collection_key.return_value = None

            config = PipelineConfig(
                state_db_path=Path(tmp) / "state.sqlite3",
                watch=WatchStageConfig(enabled=False),
                summary=SummaryStageConfig(enabled=True, limit=5, incremental=True),
                notion=NotionStageConfig(enabled=False),
            )
            orchestrator = PipelineOrchestrator(config)
            orchestrator.summary_service = FakeSummaryService()
            first = orchestrator.run()
            self.assertEqual(first.stages[0].processed, 1)
            second = orchestrator.run()
            self.assertEqual(second.stages[0].processed, 0)
            orchestrator.close()


if __name__ == "__main__":
    unittest.main()
