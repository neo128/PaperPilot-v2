from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from paperpilot.models.results import StageResult


PAPER_POOL_FIELDS = [
    "paper_id",
    "zotero_key",
    "title",
    "year",
    "authors",
    "venue",
    "venue_type",
    "paper_url",
    "official_url",
    "arxiv_url",
    "project_url",
    "code_url",
    "dataset_url",
    "doi",
    "arxiv_id",
    "source_quality",
    "verification_status",
    "topic_relevance",
    "reason_to_include",
    "reason_to_exclude_or_downgrade",
    "notes",
    "citation_key",
    "abstract",
]


CODED_POOL_FIELDS = [
    "paper_id",
    "zotero_key",
    "title",
    "year",
    "venue",
    "citation_key",
    "priority_score",
    "tier",
    "research_direction",
    "task_type",
    "method_type",
    "model_or_system_type",
    "data_type",
    "benchmark_or_environment",
    "real_world_or_simulation",
    "open_source_status",
    "core_contribution",
    "main_limitation",
    "evidence_strength",
    "engineering_reusability",
    "relation_to_target_topic",
    "coding_confidence",
    "coding_note",
    "reading_card",
    "status",
]


@dataclass
class ReviewProject:
    slug: str
    topic: str
    root: Path = Path(".review_projects")

    @property
    def path(self) -> Path:
        return self.root / self.slug


@dataclass
class ReviewReadOptions:
    limit: int = 25
    force: bool = False
    locale: str = "zh"
    max_chars: int = 12000
    use_deepxiv: bool = True
    insert_zotero_notes: bool = False


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "literature-review"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return text[:120].strip("_") or "paper"


def _normalize_title(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)


def _normalize_arxiv_id(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(
        r"(?P<id>(?:[a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?(?:\.pdf)?",
        text,
        re.I,
    )
    return match.group("id") if match else ""


def _entry_data(entry: dict[str, Any]) -> dict[str, Any]:
    data = entry.get("data")
    return data if isinstance(data, dict) else entry


def _authors_from_creators(creators: Iterable[dict[str, Any]]) -> list[str]:
    authors: list[str] = []
    for creator in creators or []:
        if creator.get("name"):
            authors.append(str(creator["name"]))
            continue
        first = creator.get("firstName") or creator.get("given") or ""
        last = creator.get("lastName") or creator.get("family") or ""
        name = f"{first} {last}".strip()
        if name:
            authors.append(name)
    return authors


def _extract_year(value: Any) -> str:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else ""


def _infer_venue_type(data: dict[str, Any]) -> str:
    item_type = data.get("itemType") or ""
    venue = (data.get("publicationTitle") or data.get("conferenceName") or data.get("proceedingsTitle") or "").lower()
    if "arxiv" in venue or data.get("archive") == "arXiv":
        return "preprint"
    if item_type == "conferencePaper" or "conference" in item_type.lower():
        return "conference"
    if item_type == "journalArticle":
        return "journal"
    return "unknown"


def _citation_key(authors: list[str], year: str, title: str) -> str:
    first_author = "Unknown"
    if authors:
        first_author = re.sub(r"[^a-zA-Z0-9]", "", authors[0].split()[-1]) or "Unknown"
    title_words = [re.sub(r"[^a-zA-Z0-9]", "", word).title() for word in title.split()[:4]]
    title_part = "".join(filter(None, title_words)) or "Paper"
    return f"{first_author}{year or 'ND'}{title_part}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _extract_json_object(value: str) -> dict[str, Any]:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _tier_from_score(score: int) -> str:
    if score >= 80:
        return "A 核心池"
    if score >= 65:
        return "B 主体池"
    if score >= 50:
        return "C 备选池"
    return "D 存档池"


class LiteratureReviewService:
    def __init__(
        self,
        *,
        ai: Optional[Any] = None,
        zotero: Optional[Any] = None,
        deepxiv: Optional[Any] = None,
    ) -> None:
        self.ai = ai
        self.zotero = zotero
        self.deepxiv = deepxiv

    def init_project(self, project: ReviewProject) -> StageResult:
        result = StageResult(stage="review:init")
        project.path.mkdir(parents=True, exist_ok=True)
        for rel in [
            "data/raw",
            "data/interim/paper_texts",
            "data/processed",
            "notes/templates",
            "notes/core",
            "notes/extended",
            "bib",
            "reports",
            "figs",
            "docs",
        ]:
            (project.path / rel).mkdir(parents=True, exist_ok=True)

        self._write_if_missing(
            project.path / "research_plan.md",
            f"""# Research Plan: {project.topic}

## Topic
{project.topic}

## Research Scope
待补充。

## Core Research Questions
- RQ1:
- RQ2:
- RQ3:

## Search Strategy
- 使用多组关键词检索，而不是单一 query。
- 优先复用 Zotero 已有条目；不存在时新增。

## Deliverables
- `paper_pool_raw.csv`
- `paper_pool_verified.csv`
- `paper_pool_coded.csv`
- `notes/core/*.md`
- `reports/review_draft.md`

## Risk Notes
- 未复核项应保留 `needs_verification` 标记。
""",
        )
        self._write_if_missing(
            project.path / "docs/field_schema.md",
            "# Field Schema\n\n核心 CSV 字段来自 `literature_review_auto_skill` 的 Phase 1/2 schema，并增加 Zotero key、DOI、arXiv ID、citation key 与 abstract。\n",
        )
        self._write_if_missing(
            project.path / "docs/tag_taxonomy.md",
            "# Tag Taxonomy\n\n- research_direction\n- task_type\n- method_type\n- benchmark_or_environment\n- engineering_reusability\n",
        )
        self._write_if_missing(
            project.path / "docs/scoring_rubric.md",
            "# Scoring Rubric\n\n- 80-100: A 核心池\n- 65-79: B 主体池\n- 50-64: C 备选池\n- <50: D 存档池\n",
        )
        self._write_if_missing(
            project.path / "docs/search_tasks.md",
            f"# Search Tasks\n\nTopic: {project.topic}\n\n| ID | Query | Source | Status | Notes |\n|---|---|---|---|---|\n",
        )
        self._write_if_missing(
            project.path / "notes/templates/reading_note_template.md",
            """# {title}

## 基本信息
- 引用键：
- 年份：
- 会议/期刊：
- DOI：
- ArXiv：
- Zotero：

## 研究问题
## 方法概览
## 实验与结果
## 局限与启发
## 与本综述的关系
## 证据摘录
""",
        )
        _write_csv(project.path / "data/raw/paper_pool_raw.csv", PAPER_POOL_FIELDS, [])
        _write_csv(project.path / "data/processed/paper_pool_verified.csv", PAPER_POOL_FIELDS, [])
        _write_csv(project.path / "data/processed/paper_pool_coded.csv", CODED_POOL_FIELDS, [])
        self._write_if_missing(project.path / "reports/writing_stage_status.md", "# Writing Stage Status\n\n- created_at: " + _utc_now() + "\n")
        result.created = 1
        result.artifacts["project_dir"] = str(project.path)
        return result

    def build_pool_from_zotero_items(self, project: ReviewProject, items: list[dict[str, Any]]) -> StageResult:
        self.init_project(project)
        result = StageResult(stage="review:build-pool")
        rows: list[dict[str, Any]] = []
        for index, entry in enumerate(items, start=1):
            rows.append(self._zotero_entry_to_pool_row(entry, index))
        raw_rows = rows
        verified_rows = self._deduplicate_pool_rows(raw_rows)
        for index, row in enumerate(verified_rows, start=1):
            row["paper_id"] = f"P{index:03d}"

        _write_csv(project.path / "data/raw/paper_pool_raw.csv", PAPER_POOL_FIELDS, raw_rows)
        _write_csv(project.path / "data/processed/paper_pool_verified.csv", PAPER_POOL_FIELDS, verified_rows)
        self._write_pool_report(project, raw_rows, verified_rows)
        self._write_citation_keys(project, verified_rows)

        result.processed = len(raw_rows)
        result.created = len(verified_rows)
        result.skipped = max(0, len(raw_rows) - len(verified_rows))
        result.artifacts["raw_csv"] = str(project.path / "data/raw/paper_pool_raw.csv")
        result.artifacts["verified_csv"] = str(project.path / "data/processed/paper_pool_verified.csv")
        return result

    def read_and_code(self, project: ReviewProject, options: ReviewReadOptions) -> StageResult:
        result = StageResult(stage="review:read")
        if self.ai is None:
            result.failed += 1
            result.errors.append("AI client is required for review reading.")
            return result

        pool_path = project.path / "data/processed/paper_pool_verified.csv"
        rows = _read_csv(pool_path)
        coded_rows: list[dict[str, Any]] = []
        existing_coded = {row.get("paper_id"): row for row in _read_csv(project.path / "data/processed/paper_pool_coded.csv")}

        for row in rows[: options.limit if options.limit else len(rows)]:
            result.processed += 1
            paper_id = row.get("paper_id") or f"P{result.processed:03d}"
            card_path = project.path / "notes/core" / f"{paper_id}_{_safe_filename(row.get('title', 'paper'))}.md"
            if card_path.exists() and not options.force:
                coded_rows.append(existing_coded.get(paper_id, self._default_coded_row(row, card_path, "skipped_existing")))
                result.skipped += 1
                continue

            context = self._build_reading_context(row, options)
            reading_md = self._ai_read_paper(project.topic, row, context, options)
            code_data = self._ai_code_paper(project.topic, row, context, reading_md, options)
            card_md = self._format_reading_card(project.topic, row, reading_md, code_data)
            card_path.write_text(card_md, encoding="utf-8")

            coded_rows.append(self._coded_row_from_ai(row, code_data, card_path, "success"))
            if options.insert_zotero_notes:
                self._write_zotero_note(row, card_md, project.slug)
            result.created += 1

        untouched = [row for row in _read_csv(project.path / "data/processed/paper_pool_coded.csv") if row.get("paper_id") not in {r.get("paper_id") for r in coded_rows}]
        final_rows = coded_rows + untouched
        _write_csv(project.path / "data/processed/paper_pool_coded.csv", CODED_POOL_FIELDS, final_rows)
        self._write_deep_reading_status(project, final_rows)
        result.artifacts["coded_csv"] = str(project.path / "data/processed/paper_pool_coded.csv")
        result.artifacts["notes_dir"] = str(project.path / "notes/core")
        return result

    def draft_review(self, project: ReviewProject, locale: str = "zh") -> StageResult:
        result = StageResult(stage="review:draft")
        if self.ai is None:
            result.failed += 1
            result.errors.append("AI client is required for review drafting.")
            return result
        coded_rows = _read_csv(project.path / "data/processed/paper_pool_coded.csv")
        note_snippets = self._load_note_snippets(project)
        if hasattr(self.ai, "draft_literature_review"):
            draft = self.ai.draft_literature_review(
                topic=project.topic,
                coded_rows=coded_rows,
                reading_notes=note_snippets,
                locale=locale,
            )
        else:
            prompt = self._draft_prompt(project.topic, coded_rows, note_snippets, locale)
            draft = self.ai.chat(
                [
                    {"role": "system", "content": "You are a rigorous academic literature review assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                top_p=0.9,
            )
        out = project.path / "reports/review_draft.md"
        out.write_text(str(draft).strip() + "\n", encoding="utf-8")
        (project.path / "review_v1.md").write_text(str(draft).strip() + "\n", encoding="utf-8")
        result.created = 1
        result.artifacts["review_draft"] = str(out)
        return result

    def sync_reading_notes_to_zotero(self, project: ReviewProject) -> StageResult:
        result = StageResult(stage="review:zotero-sync")
        if self.zotero is None:
            result.failed += 1
            result.errors.append("Zotero client is required for note sync.")
            return result
        rows = _read_csv(project.path / "data/processed/paper_pool_coded.csv")
        for row in rows:
            result.processed += 1
            key = row.get("zotero_key")
            card = row.get("reading_card")
            if not key or not card:
                result.skipped += 1
                continue
            path = project.path / card
            if not path.exists():
                result.skipped += 1
                continue
            self.zotero.create_note(key, self._note_html(path.read_text(encoding="utf-8")), tags=[f"review:{project.slug}", "AI精读"])
            result.created += 1
        return result

    def _write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _zotero_entry_to_pool_row(self, entry: dict[str, Any], index: int) -> dict[str, Any]:
        data = _entry_data(entry)
        title = data.get("title") or data.get("shortTitle") or "Untitled"
        authors = _authors_from_creators(data.get("creators") or [])
        doi = _normalize_doi(data.get("DOI") or data.get("doi"))
        arxiv_id = _normalize_arxiv_id(data.get("archiveLocation") or data.get("url") or data.get("extra"))
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        venue = data.get("publicationTitle") or data.get("conferenceName") or data.get("proceedingsTitle") or data.get("archive") or ""
        year = _extract_year(data.get("date") or data.get("publicationDate") or data.get("issueDate"))
        paper_url = data.get("url") or arxiv_url or (f"https://doi.org/{doi}" if doi else "")
        citation_key = _citation_key(authors, year, str(title))
        return {
            "paper_id": f"P{index:03d}",
            "zotero_key": entry.get("key") or data.get("key") or "",
            "title": title,
            "year": year,
            "authors": "; ".join(authors),
            "venue": venue,
            "venue_type": _infer_venue_type(data),
            "paper_url": paper_url,
            "official_url": "" if arxiv_url and paper_url == arxiv_url else paper_url,
            "arxiv_url": arxiv_url,
            "project_url": "",
            "code_url": "",
            "dataset_url": "",
            "doi": doi,
            "arxiv_id": arxiv_id,
            "source_quality": "primary" if doi or arxiv_id else "secondary",
            "verification_status": "partially_verified",
            "topic_relevance": "needs_review",
            "reason_to_include": "",
            "reason_to_exclude_or_downgrade": "",
            "notes": "",
            "citation_key": citation_key,
            "abstract": data.get("abstractNote") or data.get("abstract") or "",
        }

    def _deduplicate_pool_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            doi = row.get("doi") or ""
            arxiv_id = row.get("arxiv_id") or ""
            title = _normalize_title(row.get("title"))
            if doi:
                key = ("doi", doi)
            elif arxiv_id:
                key = ("arxiv", arxiv_id)
            else:
                key = ("title", title)
            if not key[1] or key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    def _write_pool_report(self, project: ReviewProject, raw_rows: list[dict[str, Any]], verified_rows: list[dict[str, Any]]) -> None:
        venues = sorted({row.get("venue") for row in verified_rows if row.get("venue")})
        years = sorted({row.get("year") for row in verified_rows if row.get("year")})
        content = f"""# Paper Pool Verification Report

## Topic
{project.topic}

## Input Sources
- Zotero

## Total Papers
- raw: {len(raw_rows)}
- verified: {len(verified_rows)}
- duplicates_removed: {max(0, len(raw_rows) - len(verified_rows))}

## Venue Coverage
{", ".join(venues) if venues else "待复核"}

## Year Coverage
{", ".join(years) if years else "待复核"}

## Remaining Unverified Items
- `verification_status=partially_verified` 的条目需要后续人工或自动复核。

## Next Step
- 运行 `review read` 生成 AI 精读卡片和编码表。
"""
        (project.path / "reports/paper_pool_verification_report.md").write_text(content, encoding="utf-8")

    def _write_citation_keys(self, project: ReviewProject, rows: list[dict[str, Any]]) -> None:
        citation_rows = [
            {
                "paper_id": row.get("paper_id", ""),
                "citation_key": row.get("citation_key", ""),
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "zotero_key": row.get("zotero_key", ""),
            }
            for row in rows
        ]
        _write_csv(project.path / "bib/citation_keys.csv", ["paper_id", "citation_key", "title", "year", "zotero_key"], citation_rows)
        bib_entries = []
        for row in rows:
            key = row.get("citation_key") or row.get("paper_id")
            bib_entries.append(
                "@article{"
                + str(key)
                + ",\n"
                + f"  title = {{{row.get('title', '')}}},\n"
                + f"  author = {{{row.get('authors', '')}}},\n"
                + f"  year = {{{row.get('year', '')}}},\n"
                + f"  url = {{{row.get('paper_url', '')}}},\n"
                + "}\n"
            )
        (project.path / "bib/references.bib").write_text("\n".join(bib_entries), encoding="utf-8")

    def _build_reading_context(self, row: dict[str, str], options: ReviewReadOptions) -> str:
        parts = [
            f"Title: {row.get('title', '')}",
            f"Year: {row.get('year', '')}",
            f"Venue: {row.get('venue', '')}",
            f"Authors: {row.get('authors', '')}",
            f"DOI: {row.get('doi', '')}",
            f"arXiv: {row.get('arxiv_id', '')}",
            f"Abstract:\n{row.get('abstract', '')}",
        ]
        arxiv_id = row.get("arxiv_id")
        if options.use_deepxiv and self.deepxiv is not None and arxiv_id:
            for label, call in [
                ("DeepXiv brief", lambda: self.deepxiv.brief(arxiv_id)),
                ("DeepXiv head", lambda: self.deepxiv.head(arxiv_id)),
            ]:
                try:
                    parts.append(f"{label}:\n{call()}")
                except Exception:
                    continue
            for section in ("Introduction", "Method", "Experiments", "Conclusion"):
                try:
                    parts.append(f"DeepXiv section {section}:\n{self.deepxiv.section(arxiv_id, section)}")
                except Exception:
                    continue
        return "\n\n".join(part for part in parts if part.strip())

    def _ai_read_paper(self, topic: str, row: dict[str, str], context: str, options: ReviewReadOptions) -> str:
        if hasattr(self.ai, "read_paper_structured"):
            return str(
                self.ai.read_paper_structured(
                    topic=topic,
                    title=row.get("title", ""),
                    metadata=row,
                    context=context,
                    locale=options.locale,
                    max_chars=options.max_chars,
                )
            ).strip()
        prompt = (
            f"请围绕综述主题“{topic}”阅读下面论文信息，生成中文 Markdown 精读卡片。"
            "必须严格基于输入，不确定处标注 needs_verification。\n\n"
            f"{context[: options.max_chars]}"
        )
        return str(
            self.ai.chat(
                [
                    {"role": "system", "content": "你是一名严谨的科研文献精读助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                top_p=0.9,
            )
        ).strip()

    def _ai_code_paper(
        self,
        topic: str,
        row: dict[str, str],
        context: str,
        reading_md: str,
        options: ReviewReadOptions,
    ) -> dict[str, Any]:
        if hasattr(self.ai, "code_paper_for_review"):
            data = self.ai.code_paper_for_review(
                topic=topic,
                title=row.get("title", ""),
                metadata=row,
                context=context,
                reading_note=reading_md,
                locale=options.locale,
                max_chars=options.max_chars,
            )
            if isinstance(data, dict):
                return data
            return _extract_json_object(str(data))
        prompt = (
            f"请围绕综述主题“{topic}”对论文进行结构化编码，只输出 JSON。"
            "字段包括 priority_score,tier,research_direction,task_type,method_type,"
            "model_or_system_type,data_type,benchmark_or_environment,real_world_or_simulation,"
            "open_source_status,core_contribution,main_limitation,evidence_strength,"
            "engineering_reusability,relation_to_target_topic,coding_confidence,coding_note。\n\n"
            f"论文信息：\n{context[: options.max_chars]}\n\n精读笔记：\n{reading_md[:4000]}"
        )
        text = self.ai.chat(
            [
                {"role": "system", "content": "You return strict JSON for literature-review coding."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.05,
            top_p=0.9,
        )
        return _extract_json_object(str(text))

    def _default_coded_row(self, row: dict[str, str], card_path: Path, status: str) -> dict[str, Any]:
        score = 45
        if row.get("abstract"):
            score += 10
        if row.get("doi") or row.get("arxiv_id"):
            score += 10
        if row.get("venue") and (row.get("venue") or "").lower() != "arxiv":
            score += 5
        return {
            **{field: "" for field in CODED_POOL_FIELDS},
            "paper_id": row.get("paper_id", ""),
            "zotero_key": row.get("zotero_key", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "citation_key": row.get("citation_key", ""),
            "priority_score": score,
            "tier": _tier_from_score(score),
            "coding_confidence": "low",
            "coding_note": "Default heuristic; needs AI or manual review.",
            "reading_card": str(card_path.relative_to(card_path.parents[2])),
            "status": status,
        }

    def _coded_row_from_ai(self, row: dict[str, str], code_data: dict[str, Any], card_path: Path, status: str) -> dict[str, Any]:
        default = self._default_coded_row(row, card_path, status)
        score_raw = code_data.get("priority_score") or code_data.get("score") or default["priority_score"]
        try:
            score = int(float(score_raw))
        except (TypeError, ValueError):
            score = int(default["priority_score"])
        out = {**default, "priority_score": score, "tier": code_data.get("tier") or _tier_from_score(score)}
        for field in CODED_POOL_FIELDS:
            if field in {"paper_id", "zotero_key", "title", "year", "venue", "citation_key", "priority_score", "tier", "reading_card", "status"}:
                continue
            if field in code_data:
                out[field] = code_data.get(field, "")
        return out

    def _format_reading_card(self, topic: str, row: dict[str, str], reading_md: str, code_data: dict[str, Any]) -> str:
        return f"""# {row.get('title', '')}

## 基本信息

- Paper ID: {row.get('paper_id', '')}
- Citation Key: {row.get('citation_key', '')}
- Year / Venue: {row.get('year', '')} / {row.get('venue', '')}
- Authors: {row.get('authors', '')}
- DOI: {row.get('doi', '')}
- arXiv: {row.get('arxiv_id', '')}
- Zotero Key: {row.get('zotero_key', '')}
- Review Topic: {topic}

## AI 精读

{reading_md}

## 结构化编码

```json
{json.dumps(code_data, ensure_ascii=False, indent=2)}
```
"""

    def _write_zotero_note(self, row: dict[str, str], card_md: str, slug: str) -> None:
        if self.zotero is None or not row.get("zotero_key"):
            return
        self.zotero.create_note(row["zotero_key"], self._note_html(card_md), tags=[f"review:{slug}", "AI精读"])

    def _note_html(self, markdown_text: str) -> str:
        safe_text = html.escape(markdown_text or "")
        return f'<div data-markdown="true" data-mime-type="text/markdown" style="white-space:pre-wrap">{safe_text}</div>'

    def _write_deep_reading_status(self, project: ReviewProject, coded_rows: list[dict[str, Any]]) -> None:
        layer_counts: dict[str, int] = {}
        for row in coded_rows:
            layer = str(row.get("tier") or "unknown")
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
        lines = ["# Deep Reading Status", "", f"- updated_at: {_utc_now()}", f"- coded_papers: {len(coded_rows)}", ""]
        lines.append("## Layer Counts")
        for layer, count in sorted(layer_counts.items()):
            lines.append(f"- {layer}: {count}")
        lines.extend(["", "## Reading Cards"])
        for row in coded_rows:
            lines.append(f"- {row.get('paper_id')}: {row.get('title')} -> `{row.get('reading_card')}`")
        (project.path / "reports/deep_reading_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _load_note_snippets(self, project: ReviewProject, limit: int = 30) -> list[str]:
        snippets: list[str] = []
        for path in sorted((project.path / "notes/core").glob("*.md"))[:limit]:
            text = path.read_text(encoding="utf-8")
            snippets.append(f"[{path.name}]\n{text[:3000]}")
        return snippets

    def _draft_prompt(self, topic: str, coded_rows: list[dict[str, str]], note_snippets: list[str], locale: str) -> str:
        lang = "中文" if locale.lower().startswith("zh") else "English"
        return (
            f"请用{lang}撰写关于“{topic}”的系统性文献综述初稿。"
            "必须基于编码表和精读卡片，不确定处标注 needs_verification。"
            "章节包括：摘要、检索与筛选方法、分类框架、主题主线、横向比较、挑战、未来方向、结论、参考文献占位。\n\n"
            f"编码表：\n{json.dumps(coded_rows[:80], ensure_ascii=False, indent=2)}\n\n"
            f"精读卡片摘录：\n\n" + "\n\n".join(note_snippets)
        )
