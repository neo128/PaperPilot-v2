from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from paperpilot.models.results import PipelineResult, StageResult


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        if getattr(self, "conn", None) is None:
            return
        self.conn.close()
        self.conn = None

    def __enter__(self) -> "SQLiteStateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                success INTEGER,
                config_json TEXT
            );

            CREATE TABLE IF NOT EXISTS stage_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                processed INTEGER DEFAULT 0,
                created_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                duration_sec REAL DEFAULT 0,
                artifacts_json TEXT,
                errors_json TEXT,
                FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS item_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                item_key TEXT,
                title TEXT,
                status TEXT,
                meta_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_item_states_item_stage ON item_states(item_key, stage_name, created_at);
            """
        )
        self.conn.commit()

    def create_run(self, config: dict) -> str:
        run_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO pipeline_runs(run_id, started_at, config_json) VALUES (?, ?, ?)",
            (run_id, utc_now(), json.dumps(config, ensure_ascii=False, default=str)),
        )
        self.conn.commit()
        return run_id

    def complete_run(self, run_id: str, result: PipelineResult) -> None:
        self.conn.execute(
            "UPDATE pipeline_runs SET finished_at = ?, success = ? WHERE run_id = ?",
            (utc_now(), 1 if result.success else 0, run_id),
        )
        self.conn.commit()

    def record_stage(self, run_id: str, stage: StageResult) -> None:
        self.conn.execute(
            """
            INSERT INTO stage_runs(
                run_id, stage_name, processed, created_count, updated_count,
                skipped_count, failed_count, duration_sec, artifacts_json, errors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                stage.stage,
                stage.processed,
                stage.created,
                stage.updated,
                stage.skipped,
                stage.failed,
                stage.duration_sec,
                json.dumps(stage.artifacts, ensure_ascii=False),
                json.dumps(stage.errors, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def record_item_state(
        self,
        run_id: str,
        stage_name: str,
        item_key: Optional[str],
        title: Optional[str],
        status: str,
        meta: Optional[dict] = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO item_states(run_id, stage_name, item_key, title, status, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                stage_name,
                item_key,
                title,
                status,
                json.dumps(meta or {}, ensure_ascii=False, default=str),
                utc_now(),
            ),
        )
        self.conn.commit()

    def get_latest_item_status(self, item_key: str, stage_name: str) -> Optional[str]:
        row = self.conn.execute(
            """
            SELECT status FROM item_states
            WHERE item_key = ? AND stage_name = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (item_key, stage_name),
        ).fetchone()
        return row["status"] if row else None

    def has_item_succeeded(self, item_key: str, stage_name: str) -> bool:
        return self.get_latest_item_status(item_key, stage_name) == "success"

    def list_runs(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC"))
