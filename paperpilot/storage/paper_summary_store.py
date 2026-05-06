from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperSummary:
    """Structured representation of an AI-generated paper summary."""
    paper_id: str
    zotero_key: str
    title: str
    year: Optional[str] = None
    authors: Optional[str] = None
    institution: Optional[str] = None
    field: Optional[str] = None
    keywords: Optional[str] = None
    task_type: Optional[str] = None
    one_line_summary: Optional[str] = None
    research_problem: Optional[str] = None
    method_overview: Optional[str] = None
    technical_route: Optional[str] = None
    innovations: Optional[str] = None
    tech_coordination: Optional[str] = None  # 技术坐标系定位 (sec 7)
    experiments: Optional[str] = None
    limitations: Optional[str] = None
    failure_modes: Optional[str] = None  # 失败模式 (sec 10)
    review_value: Optional[str] = None
    tags: Optional[str] = None
    robot_task_modeling: Optional[str] = None  # 机器人任务建模 (sec 13.1)
    data_and_platform: Optional[str] = None  # 数据与本体 (sec 13.2)
    perception_decision_control: Optional[str] = None  # 感知-决策-控制链路 (sec 13.3)
    generalization_deployment: Optional[str] = None  # 泛化与部署能力 (sec 13.4)
    research_opportunities: Optional[str] = None
    evidence: Optional[str] = None
    full_summary_md: Optional[str] = None
    locale: str = "zh"
    model: Optional[str] = None
    created_at: Optional[str] = None
    source: Optional[str] = None  # e.g. "pdf", "deepxiv", "abstract"


class PaperSummaryStore:
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

    def __enter__(self) -> "PaperSummaryStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _init_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS paper_summaries (
                paper_id TEXT PRIMARY KEY,
                zotero_key TEXT NOT NULL,
                title TEXT,
                year TEXT,
                authors TEXT,
                institution TEXT,
                field TEXT,
                keywords TEXT,
                task_type TEXT,
                one_line_summary TEXT,
                research_problem TEXT,
                method_overview TEXT,
                technical_route TEXT,
                innovations TEXT,
                tech_coordination TEXT,
                experiments TEXT,
                limitations TEXT,
                failure_modes TEXT,
                review_value TEXT,
                tags TEXT,
                robot_task_modeling TEXT,
                data_and_platform TEXT,
                perception_decision_control TEXT,
                generalization_deployment TEXT,
                research_opportunities TEXT,
                evidence TEXT,
                full_summary_md TEXT,
                locale TEXT DEFAULT 'zh',
                model TEXT,
                created_at TEXT NOT NULL,
                source TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_summaries_zotero ON paper_summaries(zotero_key);
            CREATE INDEX IF NOT EXISTS idx_summaries_title ON paper_summaries(title);
            CREATE INDEX IF NOT EXISTS idx_summaries_field ON paper_summaries(field);
            CREATE INDEX IF NOT EXISTS idx_summaries_task_type ON paper_summaries(task_type);
            CREATE INDEX IF NOT EXISTS idx_summaries_created ON paper_summaries(created_at DESC);
            CREATE VIRTUAL TABLE IF NOT EXISTS paper_summaries_fts
                USING fts5(title, one_line_summary, research_problem, method_overview, innovations, experiments,
                           content='paper_summaries', content_rowid='rowid');
            CREATE TRIGGER IF NOT EXISTS paper_summaries_ai AFTER INSERT ON paper_summaries BEGIN
                INSERT INTO paper_summaries_fts(rowid, title, one_line_summary, research_problem,
                    method_overview, innovations, experiments)
                VALUES (new.rowid, new.title, new.one_line_summary, new.research_problem,
                    new.method_overview, new.innovations, new.experiments);
            END;
            """)
        # Backward-compat: add columns if table existed before migration
        for col in ["tech_coordination", "failure_modes", "robot_task_modeling",
                    "data_and_platform", "perception_decision_control", "generalization_deployment"]:
            try:
                self.conn.execute(f"ALTER TABLE paper_summaries ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        self.conn.commit()

    def save(self, summary: PaperSummary) -> None:
        self.conn.execute(
            """
            INSERT INTO paper_summaries (
                paper_id, zotero_key, title, year, authors, institution, field,
                keywords, task_type, one_line_summary, research_problem,
                method_overview, technical_route, innovations, tech_coordination,
                experiments, limitations, failure_modes, review_value, tags,
                robot_task_modeling, data_and_platform, perception_decision_control,
                generalization_deployment, research_opportunities,
                evidence, full_summary_md, locale, model, created_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.paper_id,
                summary.zotero_key,
                summary.title,
                summary.year,
                summary.authors,
                summary.institution,
                summary.field,
                summary.keywords,
                summary.task_type,
                summary.one_line_summary,
                summary.research_problem,
                summary.method_overview,
                summary.technical_route,
                summary.innovations,
                summary.tech_coordination,
                summary.experiments,
                summary.limitations,
                summary.failure_modes,
                summary.review_value,
                summary.tags,
                summary.robot_task_modeling,
                summary.data_and_platform,
                summary.perception_decision_control,
                summary.generalization_deployment,
                summary.research_opportunities,
                summary.evidence,
                summary.full_summary_md,
                summary.locale,
                summary.model,
                summary.created_at or utc_now(),
                summary.source,
            ),
        )
        self.conn.commit()

    def get_by_zotero_key(self, zotero_key: str) -> Optional[PaperSummary]:
        row = self.conn.execute(
            "SELECT * FROM paper_summaries WHERE zotero_key = ? ORDER BY created_at DESC LIMIT 1",
            (zotero_key,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_summary(row)

    def has_summary(self, zotero_key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM paper_summaries WHERE zotero_key = ? LIMIT 1",
            (zotero_key,),
        ).fetchone()
        return row is not None

    def search(self, query: str, limit: int = 20) -> list[PaperSummary]:
        rows = self.conn.execute(
            """
            SELECT ps.* FROM paper_summaries ps
            JOIN paper_summaries_fts fts ON ps.rowid = fts.rowid
            WHERE paper_summaries_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def list_summaries(self, limit: int = 50, offset: int = 0) -> list[PaperSummary]:
        rows = self.conn.execute(
            "SELECT * FROM paper_summaries ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM paper_summaries").fetchone()
        return row["c"] if row else 0

    def delete(self, paper_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM paper_summaries WHERE paper_id = ?", (paper_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> PaperSummary:
        return PaperSummary(
            paper_id=row["paper_id"],
            zotero_key=row["zotero_key"],
            title=row["title"],
            year=row["year"],
            authors=row["authors"],
            institution=row["institution"],
            field=row["field"],
            keywords=row["keywords"],
            task_type=row["task_type"],
            one_line_summary=row["one_line_summary"],
            research_problem=row["research_problem"],
            method_overview=row["method_overview"],
            technical_route=row["technical_route"],
            innovations=row["innovations"],
            tech_coordination=row["tech_coordination"],
            experiments=row["experiments"],
            limitations=row["limitations"],
            failure_modes=row["failure_modes"],
            review_value=row["review_value"],
            tags=row["tags"],
            robot_task_modeling=row["robot_task_modeling"],
            data_and_platform=row["data_and_platform"],
            perception_decision_control=row["perception_decision_control"],
            generalization_deployment=row["generalization_deployment"],
            research_opportunities=row["research_opportunities"],
            evidence=row["evidence"],
            full_summary_md=row["full_summary_md"],
            locale=row["locale"],
            model=row["model"],
            created_at=row["created_at"],
            source=row["source"],
        )
