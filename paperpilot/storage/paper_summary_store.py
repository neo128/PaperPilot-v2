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
    summary_version: Optional[str] = None
    summary_kind: Optional[str] = None  # e.g. "summary", "review_reading"
    review_slug: Optional[str] = None
    pdf_hash: Optional[str] = None
    canonical_key: Optional[str] = None
    summary_profile: Optional[str] = None
    source_priority: Optional[int] = None
    stale_reason: Optional[str] = None
    zotero_attachment_key: Optional[str] = None
    zotero_attachment_title: Optional[str] = None
    attached_at: Optional[str] = None
    attachment_status: Optional[str] = None
    quality_score: Optional[int] = None
    quality_label: Optional[str] = None
    quality_findings: Optional[str] = None
    source_coverage: Optional[str] = None
    source_completeness: Optional[str] = None
    is_input_truncated: Optional[int] = None
    input_char_count: Optional[int] = None
    used_char_count: Optional[int] = None
    template_profile: Optional[str] = None


@dataclass
class PaperSummaryFact:
    """Searchable atomic fact extracted from an AI-generated summary."""
    paper_id: str
    zotero_key: str
    title: Optional[str] = None
    fact_type: str = ""
    label: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None
    context: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[str] = None
    source_section: Optional[str] = None
    source: Optional[str] = None
    summary_version: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class PaperSummaryFigure:
    """Local figure/table asset extracted from a source PDF."""
    paper_id: str
    zotero_key: str
    title: Optional[str] = None
    figure_index: int = 0
    page: Optional[int] = None
    file_path: str = ""
    caption: Optional[str] = None
    figure_type: Optional[str] = None
    relevance: Optional[str] = None
    summary_version: Optional[str] = None
    created_at: Optional[str] = None


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
                source TEXT,
                summary_version TEXT,
                summary_kind TEXT,
                review_slug TEXT,
                pdf_hash TEXT,
                canonical_key TEXT,
                summary_profile TEXT,
                source_priority INTEGER,
                stale_reason TEXT,
                zotero_attachment_key TEXT,
                zotero_attachment_title TEXT,
                attached_at TEXT,
                attachment_status TEXT,
                quality_score INTEGER,
                quality_label TEXT,
                quality_findings TEXT,
                source_coverage TEXT,
                source_completeness TEXT,
                is_input_truncated INTEGER,
                input_char_count INTEGER,
                used_char_count INTEGER,
                template_profile TEXT
            );
            CREATE TABLE IF NOT EXISTS paper_summary_facts (
                fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                zotero_key TEXT NOT NULL,
                title TEXT,
                fact_type TEXT NOT NULL,
                label TEXT,
                value REAL,
                unit TEXT,
                context TEXT,
                evidence TEXT,
                confidence TEXT,
                source_section TEXT,
                source TEXT,
                summary_version TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(paper_id) REFERENCES paper_summaries(paper_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS paper_summary_figures (
                figure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                zotero_key TEXT NOT NULL,
                title TEXT,
                figure_index INTEGER,
                page INTEGER,
                file_path TEXT NOT NULL,
                caption TEXT,
                figure_type TEXT,
                relevance TEXT,
                summary_version TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(paper_id) REFERENCES paper_summaries(paper_id) ON DELETE CASCADE
            );
            """)
        # Backward-compat: add columns if table existed before migration.
        for col in [
            "tech_coordination",
            "failure_modes",
            "robot_task_modeling",
            "data_and_platform",
            "perception_decision_control",
            "generalization_deployment",
            "summary_version",
            "summary_kind",
            "review_slug",
            "pdf_hash",
            "canonical_key",
            "summary_profile",
            "source_priority",
            "stale_reason",
            "zotero_attachment_key",
            "zotero_attachment_title",
            "attached_at",
            "attachment_status",
        ]:
            try:
                self.conn.execute(f"ALTER TABLE paper_summaries ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        for col, definition in [
            ("quality_score", "INTEGER"),
            ("quality_label", "TEXT DEFAULT ''"),
            ("quality_findings", "TEXT DEFAULT ''"),
            ("source_coverage", "TEXT DEFAULT ''"),
            ("source_completeness", "TEXT DEFAULT ''"),
            ("is_input_truncated", "INTEGER DEFAULT 0"),
            ("input_char_count", "INTEGER DEFAULT 0"),
            ("used_char_count", "INTEGER DEFAULT 0"),
            ("template_profile", "TEXT DEFAULT ''"),
        ]:
            try:
                self.conn.execute(f"ALTER TABLE paper_summaries ADD COLUMN {col} {definition}")
            except Exception:
                pass
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_summaries_zotero ON paper_summaries(zotero_key);
            CREATE INDEX IF NOT EXISTS idx_summaries_title ON paper_summaries(title);
            CREATE INDEX IF NOT EXISTS idx_summaries_field ON paper_summaries(field);
            CREATE INDEX IF NOT EXISTS idx_summaries_task_type ON paper_summaries(task_type);
            CREATE INDEX IF NOT EXISTS idx_summaries_created ON paper_summaries(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_summaries_kind ON paper_summaries(summary_kind);
            CREATE INDEX IF NOT EXISTS idx_summaries_review_slug ON paper_summaries(review_slug);
            CREATE INDEX IF NOT EXISTS idx_summaries_canonical ON paper_summaries(canonical_key);
            CREATE INDEX IF NOT EXISTS idx_summaries_pdf_hash ON paper_summaries(pdf_hash);
            CREATE INDEX IF NOT EXISTS idx_summaries_quality_label ON paper_summaries(quality_label);
            CREATE INDEX IF NOT EXISTS idx_summaries_source_coverage ON paper_summaries(source_coverage);
            CREATE INDEX IF NOT EXISTS idx_summary_facts_paper ON paper_summary_facts(paper_id);
            CREATE INDEX IF NOT EXISTS idx_summary_facts_zotero ON paper_summary_facts(zotero_key);
            CREATE INDEX IF NOT EXISTS idx_summary_facts_type ON paper_summary_facts(fact_type);
            CREATE INDEX IF NOT EXISTS idx_summary_facts_label ON paper_summary_facts(label);
            CREATE INDEX IF NOT EXISTS idx_summary_figures_paper ON paper_summary_figures(paper_id);
            CREATE INDEX IF NOT EXISTS idx_summary_figures_zotero ON paper_summary_figures(zotero_key);
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
        self.conn.commit()

    def save(
        self,
        summary: PaperSummary,
        facts: Optional[list[PaperSummaryFact]] = None,
        figures: Optional[list[PaperSummaryFigure]] = None,
    ) -> None:
        columns = [
            "paper_id",
            "zotero_key",
            "title",
            "year",
            "authors",
            "institution",
            "field",
            "keywords",
            "task_type",
            "one_line_summary",
            "research_problem",
            "method_overview",
            "technical_route",
            "innovations",
            "tech_coordination",
            "experiments",
            "limitations",
            "failure_modes",
            "review_value",
            "tags",
            "robot_task_modeling",
            "data_and_platform",
            "perception_decision_control",
            "generalization_deployment",
            "research_opportunities",
            "evidence",
            "full_summary_md",
            "locale",
            "model",
            "created_at",
            "source",
            "summary_version",
            "summary_kind",
            "review_slug",
            "pdf_hash",
            "canonical_key",
            "summary_profile",
            "source_priority",
            "stale_reason",
            "zotero_attachment_key",
            "zotero_attachment_title",
            "attached_at",
            "attachment_status",
            "quality_score",
            "quality_label",
            "quality_findings",
            "source_coverage",
            "source_completeness",
            "is_input_truncated",
            "input_char_count",
            "used_char_count",
            "template_profile",
        ]
        values = [
            summary.created_at or utc_now() if column == "created_at" else getattr(summary, column)
            for column in columns
        ]
        self.conn.execute(
            f"""
            INSERT INTO paper_summaries ({", ".join(columns)})
            VALUES ({", ".join(["?"] * len(columns))})
            """,
            tuple(values),
        )
        for fact in facts or []:
            self.save_fact(fact)
        for figure in figures or []:
            self.save_figure(figure)
        self.conn.commit()

    def save_fact(self, fact: PaperSummaryFact) -> None:
        self.conn.execute(
            """
            INSERT INTO paper_summary_facts (
                paper_id, zotero_key, title, fact_type, label, value, unit,
                context, evidence, confidence, source_section, source,
                summary_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact.paper_id,
                fact.zotero_key,
                fact.title,
                fact.fact_type,
                fact.label,
                fact.value,
                fact.unit,
                fact.context,
                fact.evidence,
                fact.confidence,
                fact.source_section,
                fact.source,
                fact.summary_version,
                fact.created_at or utc_now(),
            ),
        )

    def save_figure(self, figure: PaperSummaryFigure) -> None:
        self.conn.execute(
            """
            INSERT INTO paper_summary_figures (
                paper_id, zotero_key, title, figure_index, page, file_path,
                caption, figure_type, relevance, summary_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                figure.paper_id,
                figure.zotero_key,
                figure.title,
                figure.figure_index,
                figure.page,
                figure.file_path,
                figure.caption,
                figure.figure_type,
                figure.relevance,
                figure.summary_version,
                figure.created_at or utc_now(),
            ),
        )

    def update_attachment_status(
        self,
        paper_id: str,
        *,
        attachment_key: Optional[str] = None,
        attachment_title: Optional[str] = None,
        status: str = "",
        attached_at: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE paper_summaries
            SET zotero_attachment_key = ?,
                zotero_attachment_title = ?,
                attached_at = ?,
                attachment_status = ?
            WHERE paper_id = ?
            """,
            (attachment_key, attachment_title, attached_at or utc_now(), status, paper_id),
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

    def get_latest_canonical(
        self,
        *,
        zotero_key: str = "",
        canonical_key: str = "",
        summary_version: str = "",
    ) -> Optional[PaperSummary]:
        clauses = ["summary_kind = 'canonical'", "COALESCE(stale_reason, '') = ''"]
        params: list[object] = []
        key_clauses: list[str] = []
        if zotero_key:
            key_clauses.append("zotero_key = ?")
            params.append(zotero_key)
        if canonical_key:
            key_clauses.append("canonical_key = ?")
            params.append(canonical_key)
        if not key_clauses:
            return None
        clauses.append("(" + " OR ".join(key_clauses) + ")")
        if summary_version:
            clauses.append("summary_version = ?")
            params.append(summary_version)
        row = self.conn.execute(
            f"SELECT * FROM paper_summaries WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT 1",
            tuple(params),
        ).fetchone()
        return self._row_to_summary(row) if row else None

    def get_valid_canonical(
        self,
        *,
        zotero_key: str = "",
        canonical_key: str = "",
        summary_version: str,
        pdf_hash: Optional[str] = None,
    ) -> Optional[PaperSummary]:
        summary = self.get_latest_canonical(
            zotero_key=zotero_key,
            canonical_key=canonical_key,
            summary_version=summary_version,
        )
        if summary is None:
            return None
        if pdf_hash and summary.pdf_hash and summary.pdf_hash != pdf_hash:
            return None
        return summary

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

    def list_facts(self, paper_id: Optional[str] = None, fact_type: Optional[str] = None, limit: int = 100) -> list[PaperSummaryFact]:
        clauses: list[str] = []
        params: list[object] = []
        if paper_id:
            clauses.append("paper_id = ?")
            params.append(paper_id)
        if fact_type:
            clauses.append("fact_type = ?")
            params.append(fact_type)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM paper_summary_facts{where} ORDER BY created_at DESC, fact_id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def list_figures(self, paper_id: Optional[str] = None, limit: int = 100) -> list[PaperSummaryFigure]:
        clauses: list[str] = []
        params: list[object] = []
        if paper_id:
            clauses.append("paper_id = ?")
            params.append(paper_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM paper_summary_figures{where} ORDER BY paper_id, figure_index LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self._row_to_figure(row) for row in rows]

    def delete(self, paper_id: str) -> bool:
        self.conn.execute("DELETE FROM paper_summary_facts WHERE paper_id = ?", (paper_id,))
        self.conn.execute("DELETE FROM paper_summary_figures WHERE paper_id = ?", (paper_id,))
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
            summary_version=row["summary_version"],
            summary_kind=row["summary_kind"],
            review_slug=row["review_slug"],
            pdf_hash=row["pdf_hash"],
            canonical_key=row["canonical_key"],
            summary_profile=row["summary_profile"],
            source_priority=row["source_priority"],
            stale_reason=row["stale_reason"],
            zotero_attachment_key=row["zotero_attachment_key"],
            zotero_attachment_title=row["zotero_attachment_title"],
            attached_at=row["attached_at"],
            attachment_status=row["attachment_status"],
            quality_score=row["quality_score"] if row["quality_score"] not in ("", None) else None,
            quality_label=row["quality_label"],
            quality_findings=row["quality_findings"],
            source_coverage=row["source_coverage"],
            source_completeness=row["source_completeness"],
            is_input_truncated=row["is_input_truncated"],
            input_char_count=row["input_char_count"],
            used_char_count=row["used_char_count"],
            template_profile=row["template_profile"],
        )

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> PaperSummaryFact:
        return PaperSummaryFact(
            paper_id=row["paper_id"],
            zotero_key=row["zotero_key"],
            title=row["title"],
            fact_type=row["fact_type"],
            label=row["label"],
            value=row["value"],
            unit=row["unit"],
            context=row["context"],
            evidence=row["evidence"],
            confidence=row["confidence"],
            source_section=row["source_section"],
            source=row["source"],
            summary_version=row["summary_version"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_figure(row: sqlite3.Row) -> PaperSummaryFigure:
        return PaperSummaryFigure(
            paper_id=row["paper_id"],
            zotero_key=row["zotero_key"],
            title=row["title"],
            figure_index=row["figure_index"],
            page=row["page"],
            file_path=row["file_path"],
            caption=row["caption"],
            figure_type=row["figure_type"],
            relevance=row["relevance"],
            summary_version=row["summary_version"],
            created_at=row["created_at"],
        )
