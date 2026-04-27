import tempfile
import unittest
from pathlib import Path

from paperpilot.models.results import PipelineResult, StageResult
from paperpilot.storage.sqlite_state import SQLiteStateStore


class SQLiteStateStoreTest(unittest.TestCase):
    def test_create_and_complete_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStateStore(Path(tmp) / "state.sqlite3") as store:
                run_id = store.create_run({"foo": "bar"})
                store.record_stage(run_id, StageResult(stage="summary", processed=1, created=1))
                store.record_item_state(run_id, "summary", "ABC", "Paper", "success", {"x": 1})
                result = PipelineResult()
                result.add_stage(StageResult(stage="summary", processed=1, created=1))
                store.complete_run(run_id, result)
                runs = store.list_runs()
                self.assertEqual(len(runs), 1)
                self.assertEqual(runs[0]["run_id"], run_id)
                self.assertEqual(runs[0]["success"], 1)

    def test_get_latest_item_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStateStore(Path(tmp) / "state.sqlite3") as store:
                run_id = store.create_run({})
                store.record_item_state(run_id, "summary", "ABC", "Paper", "failed")
                store.record_item_state(run_id, "summary", "ABC", "Paper", "success")
                self.assertEqual(store.get_latest_item_status("ABC", "summary"), "success")
                self.assertTrue(store.has_item_succeeded("ABC", "summary"))


if __name__ == "__main__":
    unittest.main()
