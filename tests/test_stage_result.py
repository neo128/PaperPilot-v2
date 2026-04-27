import unittest

from paperpilot.models.results import PipelineResult, StageResult


class StageResultTest(unittest.TestCase):
    def test_pipeline_success_default(self):
        pipeline = PipelineResult()
        pipeline.add_stage(StageResult(stage="watch", processed=10))
        self.assertTrue(pipeline.success)

    def test_pipeline_fails_when_stage_failed(self):
        pipeline = PipelineResult()
        pipeline.add_stage(StageResult(stage="summary", failed=1))
        self.assertFalse(pipeline.success)


if __name__ == "__main__":
    unittest.main()
