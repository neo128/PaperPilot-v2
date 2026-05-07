from __future__ import annotations

import json
import tempfile
from pathlib import Path

from paperpilot.models.results import StageResult
from paperpilot.utils.run_logging import (
    log_command_finish,
    log_stage_result,
    redact_argv,
    setup_run_logging,
)


def test_redact_argv_hides_sensitive_values():
    argv = [
        "paperpilot",
        "summary",
        "--api-key",
        "secret-value",
        "--token=abc",
        "--model",
        "qwen",
    ]

    assert redact_argv(argv) == [
        "paperpilot",
        "summary",
        "--api-key",
        "***",
        "--token=***",
        "--model",
        "qwen",
    ]


def test_run_logging_writes_log_and_jsonl_events():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = setup_run_logging(command="summary", argv=["paperpilot", "summary"], log_dir=Path(tmp))
        log_stage_result(StageResult(stage="summary", processed=2, created=1, skipped=1))
        log_command_finish(success=True)

        assert ctx.log_file.exists()
        assert ctx.events_file.exists()
        events = [json.loads(line) for line in ctx.events_file.read_text(encoding="utf-8").splitlines()]
        event_names = [event["event"] for event in events]
        assert event_names == ["command_start", "stage_result", "command_finish"]
        assert events[1]["payload"]["stage"] == "summary"
        assert "command started" in ctx.log_file.read_text(encoding="utf-8")
