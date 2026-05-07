from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from paperpilot.models.results import PipelineResult, StageResult


@dataclass
class RunLogContext:
    run_id: str
    command: str
    started_at: str
    log_file: Path
    events_file: Path
    start_monotonic: float


CURRENT_RUN: RunLogContext | None = None
_SENSITIVE_MARKERS = ("key", "token", "secret", "password")


def setup_run_logging(
    *,
    command: str = "unknown",
    argv: Iterable[str] | None = None,
    log_dir: str | Path | None = None,
    level: str | None = None,
) -> RunLogContext:
    """Configure process-wide logging and create a per-run log context."""
    global CURRENT_RUN
    root = _project_root()
    target_dir = Path(log_dir or os.environ.get("PAPERPILOT_LOG_DIR") or root / ".paperpilot" / "logs").expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    safe_command = _safe_filename(command or "unknown")
    log_file = target_dir / f"{stamp}-{safe_command}-{run_id[-8:]}.log"
    events_file = target_dir / f"{stamp}-{safe_command}-{run_id[-8:]}.jsonl"
    log_level = _parse_level(level or os.environ.get("PAPERPILOT_LOG_LEVEL") or "INFO")
    console_level = _parse_level(os.environ.get("PAPERPILOT_LOG_CONSOLE_LEVEL") or "WARNING")

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] run_id=%(paperpilot_run_id)s %(message)s"
    )
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "paperpilot_run_id"):
            record.paperpilot_run_id = run_id
        return record

    logging.setLogRecordFactory(record_factory)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if getattr(handler, "_paperpilot_handler", False):
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.setLevel(min(root_logger.level or logging.WARNING, log_level))

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler._paperpilot_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    console_handler._paperpilot_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(console_handler)

    CURRENT_RUN = RunLogContext(
        run_id=run_id,
        command=command,
        started_at=started_at,
        log_file=log_file,
        events_file=events_file,
        start_monotonic=time.monotonic(),
    )
    log_event("command_start", {"command": command, "argv": redact_argv(list(argv or sys.argv))})
    logging.getLogger(__name__).info("command started: %s", command)
    return CURRENT_RUN


def log_command_finish(*, success: bool, exit_code: int = 0) -> None:
    if CURRENT_RUN is None:
        return
    duration = round(time.monotonic() - CURRENT_RUN.start_monotonic, 3)
    log_event("command_finish", {"success": success, "exit_code": exit_code, "duration_sec": duration})
    logging.getLogger(__name__).info(
        "command finished: %s success=%s exit_code=%s duration_sec=%.3f",
        CURRENT_RUN.command,
        success,
        exit_code,
        duration,
    )


def log_exception(exc: BaseException) -> None:
    log_event(
        "exception",
        {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        },
    )
    logging.getLogger(__name__).exception("command failed with %s: %s", exc.__class__.__name__, exc)


def log_stage_result(result: StageResult) -> None:
    payload = asdict(result)
    log_event("stage_result", payload)
    logging.getLogger(__name__).info(
        "stage=%s processed=%s created=%s updated=%s skipped=%s failed=%s duration_sec=%s",
        result.stage,
        result.processed,
        result.created,
        result.updated,
        result.skipped,
        result.failed,
        result.duration_sec,
    )
    for error in result.errors:
        logging.getLogger(__name__).error("stage=%s error=%s", result.stage, error)


def log_stage_results(results: Iterable[StageResult]) -> None:
    for result in results:
        log_stage_result(result)


def log_pipeline_result(result: PipelineResult) -> None:
    log_event("pipeline_result", {"success": result.success, "stages": [asdict(stage) for stage in result.stages]})
    log_stage_results(result.stages)


def log_event(event: str, payload: dict[str, Any] | None = None) -> None:
    if CURRENT_RUN is None:
        return
    record = {
        "ts": _utc_now(),
        "run_id": CURRENT_RUN.run_id,
        "command": CURRENT_RUN.command,
        "event": event,
        "payload": payload or {},
    }
    try:
        CURRENT_RUN.events_file.parent.mkdir(parents=True, exist_ok=True)
        with CURRENT_RUN.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        logging.getLogger(__name__).debug("failed to write run event", exc_info=True)


def redact_argv(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for arg in argv:
        lowered = arg.lower()
        if redact_next:
            redacted.append("***")
            redact_next = False
            continue
        if arg.startswith("--") and any(marker in lowered for marker in _SENSITIVE_MARKERS):
            if "=" in arg:
                key, _ = arg.split("=", 1)
                redacted.append(f"{key}=***")
            else:
                redacted.append(arg)
                redact_next = True
            continue
        redacted.append(arg)
    return redacted


def _parse_level(value: str) -> int:
    return getattr(logging, value.upper(), logging.INFO)


def _safe_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip().lower())
    return cleaned.strip("-") or "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]
