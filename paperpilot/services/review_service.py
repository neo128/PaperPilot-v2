from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from paperpilot.models.results import StageResult
from paperpilot.services.summary_service import extract_pdf_text


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
    "source",
    "dedupe_key",
    "source_quality",
    "verification_status",
    "fulltext_status",
    "relevance_score",
    "topic_relevance",
    "screening_decision",
    "screening_reason",
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

CODED_REQUIRED_AI_FIELDS = [
    "research_direction",
    "task_type",
    "method_type",
    "core_contribution",
    "evidence_strength",
    "relation_to_target_topic",
    "coding_confidence",
]

CANONICAL_TIERS = {
    "A": "A 核心池",
    "B": "B 主体池",
    "C": "C 备选池",
    "D": "D 存档池",
}


CURATED_POOL_FIELDS = CODED_POOL_FIELDS + [
    "curation_action",
    "curation_reason",
    "original_tier",
    "original_priority_score",
]


MATRIX_FIELDS = [
    "paper_id",
    "citation_key",
    "title",
    "year",
    "venue",
    "tier",
    "priority_score",
    "taxonomy_branch",
    "task_type",
    "method_type",
    "model_or_system_type",
    "data_type",
    "benchmark_or_environment",
    "real_world_or_simulation",
    "open_source_status",
    "evidence_strength",
    "engineering_reusability",
    "relation_to_target_topic",
    "verification_flags",
    "reading_card",
]


FULLTEXT_VERIFICATION_FIELDS = [
    "paper_id",
    "citation_key",
    "title",
    "tier",
    "priority_score",
    "doi",
    "arxiv_id",
    "paper_url",
    "zotero_key",
    "zotero_pdf_count",
    "local_pdf_count",
    "local_pdf_paths",
    "verification_status",
    "verification_flags",
    "recommended_action",
    "zotero_error",
]


FULLTEXT_FETCH_FIELDS = [
    "paper_id",
    "citation_key",
    "title",
    "tier",
    "doi",
    "arxiv_id",
    "zotero_key",
    "oa_status",
    "oa_source",
    "pdf_url",
    "landing_url",
    "local_pdf_path",
    "attached_to_zotero",
    "fetch_error",
]


DEFAULT_CURATE_INCLUDE_KEYWORDS = [
    "world model",
    "world models",
    "embodied ai",
    "embodied intelligence",
    "physical ai",
    "robot",
    "robotics",
    "manipulation",
    "navigation",
    "locomotion",
    "vla",
    "vision language action",
    "vision-language-action",
    "spatial",
    "3d",
    "scene",
    "latent",
    "dynamics",
    "temporal",
    "simulation",
    "prediction",
    "action-conditioned",
    "policy",
    "planning",
]


DEFAULT_CURATE_EXCLUDE_KEYWORDS = [
    "alien",
    "space mission",
    "space missions",
    "solar system",
    "clinical",
    "racial bias",
    "medical",
    "medical needle",
    "medical needles",
    "surgery",
    "surgical",
    "surgeon",
    "epidemic",
    "rna",
    "molecular biology",
    "interactome",
    "ecologist",
    "slime mold",
    "plant taxonomy",
    "microbial",
    "neanderthal",
    "primate",
    "old world higher primates",
    "embodied energy",
    "economic valuation",
    "electricity consumption",
    "sustainable ai",
    "socio-legal",
    "governance",
    "global south",
    "whale",
    "companion robot",
    "humanitarian",
    "ai-ai bias",
    "model cards",
    "clever hans",
    "unsupervised learning",
    "human-like",
    "communications generated",
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
    use_local_pdfs: bool = True
    pdf_max_pages: int = 12
    paper_ids: tuple[str, ...] = ()


@dataclass
class ReviewCurateOptions:
    apply: bool = False
    include_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    min_positive_hits: int = 1


@dataclass
class ReviewQCOptions:
    draft_path: str = "reports/review_draft.md"


@dataclass
class ReviewMatrixOptions:
    include_tiers: tuple[str, ...] = ("A", "B", "C")


@dataclass
class ReviewVerifyOptions:
    include_tiers: tuple[str, ...] = ("A", "B")
    check_zotero: bool = True
    storage_dir: Optional[Path] = None


@dataclass
class ReviewFetchPdfOptions:
    include_tiers: tuple[str, ...] = ("A", "B")
    email: Optional[str] = None
    output_dir: Optional[Path] = None
    attach_zotero: bool = False
    dry_run: bool = False
    force: bool = False
    limit: int = 0


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


def _normalize_priority_score(value: Any, default_score: int) -> tuple[int, list[str]]:
    issues: list[str] = []
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        issues.append("invalid_priority_score")
        return default_score, issues
    if score < 0 or score > 100:
        issues.append("priority_score_out_of_range")
        score = max(0, min(100, score))
    return score, issues


def _normalize_tier(value: Any, score: int) -> tuple[str, list[str]]:
    issues: list[str] = []
    text = str(value or "").strip()
    rank = text[:1].upper()
    if rank in CANONICAL_TIERS:
        return CANONICAL_TIERS[rank], issues
    if text:
        issues.append("invalid_tier")
    else:
        issues.append("missing_tier")
    return _tier_from_score(score), issues


def _normalize_coding_confidence(value: Any) -> tuple[str, list[str]]:
    issues: list[str] = []
    text = str(value or "").strip().lower()
    if not text:
        return "needs_verification", ["missing_coding_confidence"]
    if text in {"high", "medium", "low", "needs_verification"}:
        return text, issues
    if text in {"高", "高置信", "high confidence"}:
        return "high", issues
    if text in {"中", "中等", "medium confidence"}:
        return "medium", issues
    if text in {"低", "低置信", "low confidence"}:
        return "low", issues
    issues.append("invalid_coding_confidence")
    return "needs_verification", issues


def _coding_validation_issues(code_data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in CODED_REQUIRED_AI_FIELDS:
        value = code_data.get(field)
        if value is None or str(value).strip() == "":
            issues.append(f"missing_{field}")
    return issues


def _topic_keywords(topic: str) -> list[str]:
    phrases: list[str] = []
    topic_lower = topic.lower()
    for phrase in ("world model", "world models", "embodied ai", "physical ai"):
        if phrase in topic_lower:
            phrases.append(phrase)
    return phrases


def _contains_keyword(text: str, keyword: str) -> bool:
    key = keyword.strip().lower()
    if not key:
        return False
    if re.search(r"[^a-z0-9]", key):
        return key in text
    return re.search(rf"\b{re.escape(key)}\b", text) is not None


def _keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for keyword in keywords:
        key = keyword.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if _contains_keyword(text, key):
            out.append(key)
    return out


def _topic_terms(topic: str) -> list[str]:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", " ", topic or "").lower()
    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "review",
        "survey",
        "systematic",
        "literature",
        "taxonomy",
    }
    terms: list[str] = []
    phrase = " ".join(text.split())
    if phrase:
        terms.append(phrase)
    for token in phrase.split():
        if len(token) >= 3 and token not in stopwords:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _dedupe_key_for_pool_row(row: dict[str, Any]) -> str:
    doi = row.get("doi") or ""
    arxiv_id = row.get("arxiv_id") or ""
    title = _normalize_title(row.get("title"))
    if doi:
        return f"doi:{doi}"
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if title:
        return f"title:{title}"
    return ""


def _infer_pool_source(data: dict[str, Any], doi: str, arxiv_id: str) -> str:
    tags = {str(tag.get("tag") or "").lower() for tag in data.get("tags") or [] if isinstance(tag, dict)}
    archive = str(data.get("archive") or "").lower()
    url = str(data.get("url") or "").lower()
    if "paperpilot-v2" in tags:
        if arxiv_id:
            return "zotero:paperpilot:arxiv"
        if doi:
            return "zotero:paperpilot:doi"
        return "zotero:paperpilot"
    if arxiv_id or archive == "arxiv" or "arxiv.org" in url:
        return "zotero:arxiv"
    if doi:
        return "zotero:doi"
    return "zotero:manual"


def _infer_fulltext_status(row: dict[str, Any]) -> str:
    if row.get("arxiv_id") or row.get("arxiv_url"):
        return "open_access_candidate"
    if row.get("doi"):
        return "needs_oa_lookup"
    if row.get("paper_url") or row.get("official_url"):
        return "needs_url_check"
    return "metadata_only"


def _screen_pool_row(project: ReviewProject, row: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(row.get(field, ""))
        for field in [
            "title",
            "abstract",
            "venue",
            "authors",
            "paper_url",
            "official_url",
            "project_url",
            "code_url",
            "dataset_url",
        ]
    ).lower()
    title_text = str(row.get("title") or "").lower()
    topic_terms = _topic_terms(project.topic)
    topic_hits = _keyword_hits(text, topic_terms)
    title_hits = _keyword_hits(title_text, topic_terms)
    negative_hits = _keyword_hits(text, DEFAULT_CURATE_EXCLUDE_KEYWORDS)

    score = 25
    if row.get("source_quality") == "primary":
        score += 15
    if row.get("abstract"):
        score += 10
    if row.get("year"):
        score += 5
    if row.get("venue"):
        score += 5
    if topic_hits:
        score += min(30, 10 * len(topic_hits))
    if title_hits:
        score += 15
    if negative_hits:
        score -= min(35, 15 * len(negative_hits))
    score = max(0, min(100, score))

    if negative_hits and not topic_hits:
        decision = "exclude_candidate"
        relevance = "low"
    elif score >= 65:
        decision = "include_for_reading"
        relevance = "likely_relevant"
    elif score >= 40:
        decision = "needs_manual_screening"
        relevance = "uncertain"
    else:
        decision = "needs_manual_screening"
        relevance = "low"

    reasons: list[str] = []
    if topic_hits:
        reasons.append("topic_hits=" + ",".join(topic_hits[:8]))
    if title_hits:
        reasons.append("title_hits=" + ",".join(title_hits[:8]))
    if negative_hits:
        reasons.append("negative_hits=" + ",".join(negative_hits[:8]))
    if row.get("source_quality") == "primary":
        reasons.append("primary_identifier")
    if row.get("abstract"):
        reasons.append("has_abstract")
    if not reasons:
        reasons.append("metadata_only_initial_screen")

    out = dict(row)
    out["relevance_score"] = score
    out["topic_relevance"] = relevance
    out["screening_decision"] = decision
    out["screening_reason"] = "; ".join(reasons)
    if decision == "include_for_reading":
        out["reason_to_include"] = out.get("reason_to_include") or out["screening_reason"]
    if decision == "exclude_candidate":
        out["reason_to_exclude_or_downgrade"] = out.get("reason_to_exclude_or_downgrade") or out["screening_reason"]
    return out


def _extract_paper_ids(text: str) -> set[str]:
    return set(re.findall(r"\bP\d{3}\b", text or ""))


def _extract_citation_keys(text: str) -> set[str]:
    return set(re.findall(r"citation_key:\s*([A-Za-z0-9_:-]+)", text or ""))


def _extract_bib_keys(text: str) -> set[str]:
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", text or ""))


def _placeholder_count(text: str) -> int:
    lowered = (text or "").lower()
    return lowered.count("needs_verification") + lowered.count("待复核")


def _draft_evidence_text(text: str) -> str:
    included: list[str] = []
    excluded = False
    for line in (text or "").splitlines():
        if line.startswith("## "):
            title = line.strip("# ").strip().lower()
            excluded = any(marker in title for marker in ("检索", "筛选", "参考文献", "references"))
        if not excluded:
            included.append(line)
    return "\n".join(included)


def _has_verification_marker(value: Any) -> bool:
    text = str(value or "").lower()
    return "needs_verification" in text or "待复核" in text or "missing" in text or "unavailable" in text


def _tier_rank(tier: str) -> str:
    value = str(tier or "")
    return value[:1] if value[:1] in {"A", "B", "C", "D"} else "?"


def _find_pdf_attachment_data(children: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    pdfs: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data", child)
        if data.get("itemType") != "attachment":
            continue
        filename = (data.get("filename") or "").lower()
        content_type = (data.get("contentType") or "").lower()
        if content_type != "application/pdf" and not filename.endswith(".pdf"):
            continue
        if data.get("linkMode") not in {"imported_file", "linked_file", "imported_url"}:
            continue
        pdfs.append(data)
    return pdfs


def _resolve_attachment_path(storage_root: Path, attachment: dict[str, Any]) -> Path:
    path_hint = attachment.get("path")
    if path_hint:
        if str(path_hint).startswith("storage:"):
            rel = str(path_hint).split("storage:", 1)[1].lstrip("/")
            return storage_root / rel
        return Path(str(path_hint)).expanduser()
    key = attachment.get("key") or ""
    filename = attachment.get("filename") or "document.pdf"
    return storage_root / key / filename


def _project_pdf_paths(project: ReviewProject, paper_id: str) -> list[Path]:
    pdf_dir = project.path / "data/interim/pdfs"
    if not paper_id or not pdf_dir.exists():
        return []
    return sorted(path for path in pdf_dir.glob(f"{paper_id}_*.pdf") if path.exists())


def _fulltext_target_rows(project: ReviewProject) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str, bool]:
    """Return rows for PDF fetch/verify.

    Once coding exists, tiers come from paper_pool_coded.csv and can be filtered.
    Before AI reading, fall back to paper_pool_verified.csv so review run can fetch
    full text first and feed local PDFs into the initial reading pass.
    """
    coded_path = project.path / "data/processed/paper_pool_coded.csv"
    verified_path = project.path / "data/processed/paper_pool_verified.csv"
    coded_rows = _read_csv(coded_path)
    verified_rows = _read_csv(verified_path)
    verified_by_id = {
        row.get("paper_id"): row
        for row in verified_rows
        if row.get("paper_id")
    }
    if coded_rows:
        return coded_rows, verified_by_id, "data/processed/paper_pool_coded.csv", True

    pre_coding_rows: list[dict[str, Any]] = []
    for row in verified_rows:
        target = dict(row)
        target.setdefault("tier", "unranked")
        target.setdefault("priority_score", "")
        target["_pre_coding_target"] = True
        pre_coding_rows.append(target)
    return pre_coding_rows, verified_by_id, "data/processed/paper_pool_verified.csv", False


class LiteratureReviewService:
    def __init__(
        self,
        *,
        ai: Optional[Any] = None,
        zotero: Optional[Any] = None,
        deepxiv: Optional[Any] = None,
        open_access: Optional[Any] = None,
    ) -> None:
        self.ai = ai
        self.zotero = zotero
        self.deepxiv = deepxiv
        self.open_access = open_access

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
            row["dedupe_key"] = row.get("dedupe_key") or _dedupe_key_for_pool_row(row)
            row["fulltext_status"] = _infer_fulltext_status(row)
        verified_rows = [_screen_pool_row(project, row) for row in verified_rows]

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

        selected_rows = rows
        if options.paper_ids:
            wanted = set(options.paper_ids)
            selected_rows = [row for row in selected_rows if row.get("paper_id") in wanted]
        selected_rows = selected_rows[: options.limit if options.limit else len(selected_rows)]

        for row in selected_rows:
            result.processed += 1
            paper_id = row.get("paper_id") or f"P{result.processed:03d}"
            card_path = project.path / "notes/core" / f"{paper_id}_{_safe_filename(row.get('title', 'paper'))}.md"
            if card_path.exists() and not options.force:
                coded_rows.append(existing_coded.get(paper_id, self._default_coded_row(row, card_path, "skipped_existing")))
                result.skipped += 1
                continue

            context = self._build_reading_context(project, row, options)
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

    def curate_coded_pool(self, project: ReviewProject, options: ReviewCurateOptions) -> StageResult:
        result = StageResult(stage="review:curate")
        coded_path = project.path / "data/processed/paper_pool_coded.csv"
        rows = _read_csv(coded_path)
        if not rows:
            result.failed += 1
            result.errors.append(f"Missing or empty coded pool: {coded_path}")
            return result

        include_keywords = (
            _topic_keywords(project.topic)
            + DEFAULT_CURATE_INCLUDE_KEYWORDS
            + list(options.include_keywords)
        )
        exclude_keywords = DEFAULT_CURATE_EXCLUDE_KEYWORDS + list(options.exclude_keywords)

        curated_rows: list[dict[str, Any]] = []
        reason_counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()

        for row in rows:
            result.processed += 1
            curated, action, reasons = self._curate_row(
                row,
                include_keywords=include_keywords,
                exclude_keywords=exclude_keywords,
                min_positive_hits=options.min_positive_hits,
            )
            curated_rows.append(curated)
            action_counts[action] += 1
            for reason in reasons:
                reason_counts[reason] += 1
            if action == "downgrade_to_d":
                result.updated += 1
            else:
                result.skipped += 1

        curated_path = project.path / "data/processed/paper_pool_curated.csv"
        _write_csv(curated_path, CURATED_POOL_FIELDS, curated_rows)
        if options.apply:
            _write_csv(coded_path, CODED_POOL_FIELDS, curated_rows)

        report_path = project.path / "reports/curation_report.md"
        self._write_curation_report(
            project,
            curated_rows,
            action_counts=action_counts,
            reason_counts=reason_counts,
            report_path=report_path,
            applied=options.apply,
        )
        if options.apply:
            self._write_deep_reading_status(project, curated_rows)

        result.artifacts["curated_csv"] = str(curated_path)
        result.artifacts["curation_report"] = str(report_path)
        result.artifacts["applied_to_coded_pool"] = options.apply
        return result

    def qc_review(self, project: ReviewProject, options: ReviewQCOptions) -> StageResult:
        result = StageResult(stage="review:qc")
        coded_path = project.path / "data/processed/paper_pool_coded.csv"
        coded_rows = _read_csv(coded_path)
        if not coded_rows:
            result.failed += 1
            result.errors.append(f"Missing or empty coded pool: {coded_path}")

        draft_path = Path(options.draft_path)
        if not draft_path.is_absolute():
            draft_path = project.path / draft_path
        if not draft_path.exists():
            result.failed += 1
            result.errors.append(f"Missing review draft: {draft_path}")

        if result.failed:
            return result

        draft_text = draft_path.read_text(encoding="utf-8")
        evidence_text = _draft_evidence_text(draft_text)
        citation_rows = _read_csv(project.path / "bib/citation_keys.csv")
        bib_path = project.path / "bib/references.bib"
        bib_text = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""
        curated_rows = _read_csv(project.path / "data/processed/paper_pool_curated.csv")

        paper_by_id = {row.get("paper_id", ""): row for row in coded_rows if row.get("paper_id")}
        known_ids = set(paper_by_id)
        known_citation_keys = {
            str(row.get("citation_key") or "")
            for row in coded_rows + citation_rows
            if row.get("citation_key")
        }
        bib_keys = _extract_bib_keys(bib_text)
        draft_ids = _extract_paper_ids(draft_text)
        evidence_ids = _extract_paper_ids(evidence_text)
        screening_ids = draft_ids - evidence_ids
        draft_citation_keys = _extract_citation_keys(draft_text)
        draft_citation_keys.update(key for key in known_citation_keys if key and key in draft_text)

        tier_counts = Counter(str(row.get("tier") or "unknown") for row in coded_rows)
        evidence_tier_counts = Counter(
            str(paper_by_id[paper_id].get("tier") or "unknown")
            for paper_id in evidence_ids
            if paper_id in paper_by_id
        )
        core_rows = [row for row in coded_rows if _tier_rank(row.get("tier", "")) in {"A", "B"}]
        cited_core_ids = {
            row.get("paper_id")
            for row in core_rows
            if row.get("paper_id") in draft_ids or (row.get("citation_key") and row.get("citation_key") in draft_citation_keys)
        }
        unused_core = [row for row in core_rows if row.get("paper_id") not in cited_core_ids]
        unknown_draft_ids = sorted(draft_ids - known_ids)
        unknown_citation_keys = sorted(draft_citation_keys - known_citation_keys)
        missing_bib_keys = sorted(key for key in draft_citation_keys if key and key not in bib_keys)
        d_evidence_ids = sorted(
            paper_id
            for paper_id in evidence_ids
            if paper_id in paper_by_id and _tier_rank(paper_by_id[paper_id].get("tier", "")) == "D"
        )
        d_screening_ids = sorted(
            paper_id
            for paper_id in screening_ids
            if paper_id in paper_by_id and _tier_rank(paper_by_id[paper_id].get("tier", "")) == "D"
        )
        missing_cards = [row for row in core_rows if self._reading_card_flags(project, row, include_markers=False)]
        verification_rows = [
            row
            for row in core_rows
            if any(_has_verification_marker(row.get(field, "")) for field in CODED_POOL_FIELDS)
            or self._reading_card_flags(project, row, include_markers=True)
        ]
        duplicate_keys = [
            key
            for key, count in Counter(row.get("citation_key") for row in coded_rows if row.get("citation_key")).items()
            if count > 1
        ]
        curated_mismatches = self._curated_tier_mismatches(coded_rows, curated_rows)

        findings: list[dict[str, str]] = []
        if unknown_draft_ids:
            findings.append({
                "severity": "error",
                "title": "Unknown paper IDs in draft",
                "detail": ", ".join(unknown_draft_ids),
            })
        if unknown_citation_keys:
            findings.append({
                "severity": "error",
                "title": "Citation keys used in draft but absent from citation_keys.csv",
                "detail": ", ".join(unknown_citation_keys),
            })
        if missing_bib_keys:
            findings.append({
                "severity": "warning",
                "title": "Citation keys used in draft but absent from references.bib",
                "detail": ", ".join(missing_bib_keys),
            })
        if d_evidence_ids:
            findings.append({
                "severity": "warning",
                "title": "D-tier papers appear in evidence sections",
                "detail": ", ".join(d_evidence_ids),
            })
        if unused_core:
            findings.append({
                "severity": "warning",
                "title": "A/B papers not cited in draft",
                "detail": ", ".join(row.get("paper_id", "") for row in unused_core),
            })
        if missing_cards:
            findings.append({
                "severity": "warning",
                "title": "A/B papers missing readable cards",
                "detail": ", ".join(row.get("paper_id", "") for row in missing_cards),
            })
        if verification_rows:
            findings.append({
                "severity": "warning",
                "title": "A/B papers still carry needs_verification or metadata-only markers",
                "detail": ", ".join(row.get("paper_id", "") for row in verification_rows),
            })
        if duplicate_keys:
            findings.append({
                "severity": "warning",
                "title": "Duplicate citation keys in coded pool",
                "detail": ", ".join(sorted(duplicate_keys)),
            })
        if curated_mismatches:
            findings.append({
                "severity": "warning",
                "title": "paper_pool_coded.csv and paper_pool_curated.csv tiers differ",
                "detail": ", ".join(curated_mismatches[:20]),
            })

        report_path = project.path / "reports/qc_report.md"
        self._write_qc_report(
            project,
            report_path=report_path,
            coded_rows=coded_rows,
            draft_path=draft_path,
            citation_rows=citation_rows,
            bib_keys=bib_keys,
            tier_counts=tier_counts,
            evidence_tier_counts=evidence_tier_counts,
            draft_ids=sorted(draft_ids),
            evidence_ids=sorted(evidence_ids),
            draft_citation_keys=sorted(draft_citation_keys),
            d_screening_ids=d_screening_ids,
            d_evidence_ids=d_evidence_ids,
            core_rows=core_rows,
            cited_core_ids=cited_core_ids,
            unused_core=unused_core,
            verification_rows=verification_rows,
            findings=findings,
            placeholder_count=_placeholder_count(draft_text),
        )

        result.processed = len(coded_rows)
        result.created = 1
        result.updated = len(findings)
        result.artifacts["qc_report"] = str(report_path)
        result.artifacts["draft_paper_ids"] = sorted(draft_ids)
        result.artifacts["evidence_paper_ids"] = sorted(evidence_ids)
        result.artifacts["findings"] = findings
        return result

    def build_matrices(self, project: ReviewProject, options: ReviewMatrixOptions) -> StageResult:
        result = StageResult(stage="review:matrix")
        coded_path = project.path / "data/processed/paper_pool_coded.csv"
        rows = _read_csv(coded_path)
        if not rows:
            result.failed += 1
            result.errors.append(f"Missing or empty coded pool: {coded_path}")
            return result

        include_tiers = {tier.upper() for tier in options.include_tiers}
        matrix_rows: list[dict[str, Any]] = []
        for row in rows:
            result.processed += 1
            if _tier_rank(row.get("tier", "")).upper() not in include_tiers:
                result.skipped += 1
                continue
            matrix_rows.append(self._matrix_row(project, row))

        branch_counts = Counter(row["taxonomy_branch"] for row in matrix_rows)
        tier_counts = Counter(row["tier"] for row in matrix_rows)
        matrix_csv = project.path / "data/processed/comparison_matrix.csv"
        matrix_md = project.path / "reports/comparison_matrix.md"
        taxonomy_mmd = project.path / "figs/taxonomy_overview.mmd"

        _write_csv(matrix_csv, MATRIX_FIELDS, matrix_rows)
        self._write_matrix_report(
            project,
            report_path=matrix_md,
            matrix_rows=matrix_rows,
            branch_counts=branch_counts,
            tier_counts=tier_counts,
            include_tiers=tuple(sorted(include_tiers)),
        )
        self._write_taxonomy_mermaid(taxonomy_mmd, matrix_rows, branch_counts)

        result.created = 3
        result.artifacts["comparison_matrix_csv"] = str(matrix_csv)
        result.artifacts["comparison_matrix_md"] = str(matrix_md)
        result.artifacts["taxonomy_mermaid"] = str(taxonomy_mmd)
        result.artifacts["included_papers"] = len(matrix_rows)
        result.artifacts["taxonomy_branches"] = dict(branch_counts)
        return result

    def verify_fulltext(self, project: ReviewProject, options: ReviewVerifyOptions) -> StageResult:
        result = StageResult(stage="review:verify")
        target_rows, verified_by_id, source_csv, filter_by_tier = _fulltext_target_rows(project)
        if not target_rows:
            result.failed += 1
            result.errors.append(
                "Missing or empty review pool: expected data/processed/paper_pool_coded.csv "
                "or data/processed/paper_pool_verified.csv"
            )
            return result

        include_tiers = {tier.upper() for tier in options.include_tiers}
        queue_rows: list[dict[str, Any]] = []
        for row in target_rows:
            result.processed += 1
            if filter_by_tier and _tier_rank(row.get("tier", "")).upper() not in include_tiers:
                result.skipped += 1
                continue
            pool_row = verified_by_id.get(row.get("paper_id"), {})
            queue_rows.append(self._fulltext_queue_row(project, row, pool_row, options))

        status_counts = Counter(row["verification_status"] for row in queue_rows)
        queue_path = project.path / "data/processed/fulltext_verification_queue.csv"
        report_path = project.path / "reports/fulltext_verification_status.md"
        _write_csv(queue_path, FULLTEXT_VERIFICATION_FIELDS, queue_rows)
        self._write_fulltext_verification_report(
            project,
            report_path=report_path,
            queue_rows=queue_rows,
            status_counts=status_counts,
            include_tiers=tuple(sorted(include_tiers)),
            source_csv=source_csv,
            storage_dir=options.storage_dir,
            checked_zotero=options.check_zotero and self.zotero is not None,
        )

        result.created = 2
        result.artifacts["verification_queue_csv"] = str(queue_path)
        result.artifacts["verification_report"] = str(report_path)
        result.artifacts["source_csv"] = source_csv
        result.artifacts["target_papers"] = len(queue_rows)
        result.artifacts["status_counts"] = dict(status_counts)
        return result

    def fetch_open_access_pdfs(self, project: ReviewProject, options: ReviewFetchPdfOptions) -> StageResult:
        result = StageResult(stage="review:fetch-pdfs")
        target_rows, verified_by_id, source_csv, filter_by_tier = _fulltext_target_rows(project)
        if not target_rows:
            result.failed += 1
            result.errors.append(
                "Missing or empty review pool: expected data/processed/paper_pool_coded.csv "
                "or data/processed/paper_pool_verified.csv"
            )
            return result

        include_tiers = {tier.upper() for tier in options.include_tiers}
        output_dir = options.output_dir or (project.path / "data/interim/pdfs")
        fetch_rows: list[dict[str, Any]] = []
        targets_seen = 0

        oa_client = self.open_access
        if oa_client is None:
            from paperpilot.clients.open_access import OpenAccessClient

            oa_client = OpenAccessClient(email=options.email)

        for row in target_rows:
            result.processed += 1
            if filter_by_tier and _tier_rank(row.get("tier", "")).upper() not in include_tiers:
                result.skipped += 1
                continue
            if options.limit and targets_seen >= options.limit:
                result.skipped += 1
                continue
            targets_seen += 1
            pool_row = verified_by_id.get(row.get("paper_id"), {})
            fetch_row = self._fetch_pdf_for_row(project, row, pool_row, options, output_dir, oa_client)
            fetch_rows.append(fetch_row)
            if fetch_row["oa_status"] in {"downloaded", "attached_to_zotero", "found_dry_run"}:
                result.created += 1
            elif fetch_row["oa_status"] == "existing_local_pdf":
                result.skipped += 1
            else:
                result.updated += 1

        status_counts = Counter(row["oa_status"] for row in fetch_rows)
        csv_path = project.path / "data/processed/fulltext_fetch_report.csv"
        report_path = project.path / "reports/fulltext_fetch_status.md"
        _write_csv(csv_path, FULLTEXT_FETCH_FIELDS, fetch_rows)
        self._write_fulltext_fetch_report(
            project,
            report_path=report_path,
            fetch_rows=fetch_rows,
            status_counts=status_counts,
            include_tiers=tuple(sorted(include_tiers)),
            source_csv=source_csv,
            output_dir=output_dir,
            dry_run=options.dry_run,
            attach_zotero=options.attach_zotero,
        )
        result.artifacts["fetch_report_csv"] = str(csv_path)
        result.artifacts["fetch_report"] = str(report_path)
        result.artifacts["source_csv"] = source_csv
        result.artifacts["status_counts"] = dict(status_counts)
        result.artifacts["output_dir"] = str(output_dir)
        return result

    def _write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _curate_row(
        self,
        row: dict[str, str],
        *,
        include_keywords: list[str],
        exclude_keywords: list[str],
        min_positive_hits: int,
    ) -> tuple[dict[str, Any], str, list[str]]:
        text = " ".join(
            str(row.get(field, ""))
            for field in [
                "title",
                "venue",
                "research_direction",
                "task_type",
                "method_type",
                "model_or_system_type",
                "data_type",
                "benchmark_or_environment",
                "core_contribution",
                "main_limitation",
                "evidence_strength",
                "engineering_reusability",
            ]
        ).lower()
        text = re.sub(r"\s+", " ", text)
        title_text = re.sub(r"\s+", " ", str(row.get("title") or "").lower())
        ai_explanation_text = " ".join(
            str(row.get(field, ""))
            for field in [
                "relation_to_target_topic",
                "coding_confidence",
                "coding_note",
            ]
        ).lower()
        ai_explanation_text = re.sub(r"\s+", " ", ai_explanation_text)
        positive_hits = _keyword_hits(text, include_keywords)
        title_positive_hits = _keyword_hits(title_text, include_keywords)
        negative_hits = _keyword_hits(text + " " + ai_explanation_text, exclude_keywords)
        relation = (row.get("relation_to_target_topic") or "").lower()
        coding_note = row.get("coding_note") or ""
        confidence = (row.get("coding_confidence") or "").lower()
        existing_tier = row.get("tier") or ""

        reasons: list[str] = []
        if negative_hits:
            reasons.append("negative_keywords:" + ",".join(negative_hits[:5]))
        if len(positive_hits) < min_positive_hits:
            reasons.append(f"insufficient_positive_keywords:{len(positive_hits)}")
        if (
            relation in {"low", "none", "not related", "irrelevant"}
            or relation.startswith("low")
            or "low direct" in relation
            or "not related" in relation
            or "irrelevant" in relation
            or "无关" in relation
            or "不相关" in relation
        ):
            reasons.append("ai_relation_low")
        if "needs_verification" in relation and len(positive_hits) < 2:
            reasons.append("ai_relation_needs_verification")
        if confidence in {"low", "needs_verification", ""} and len(positive_hits) == 0:
            reasons.append("low_confidence_without_domain_signal")

        should_downgrade = False
        if negative_hits and (len(positive_hits) <= 1 or not title_positive_hits or "ai_relation_low" in reasons):
            should_downgrade = True
        if len(positive_hits) < min_positive_hits and (
            "ai_relation_low" in reasons
            or "ai_relation_needs_verification" in reasons
            or "low_confidence_without_domain_signal" in reasons
        ):
            should_downgrade = True
        if existing_tier.startswith("D"):
            should_downgrade = True
            if not reasons:
                reasons.append("already_d_tier")

        curated = dict(row)
        curated["original_tier"] = row.get("tier", "")
        curated["original_priority_score"] = row.get("priority_score", "")
        if should_downgrade:
            curated["tier"] = "D 存档池"
            curated["priority_score"] = self._downgraded_score(row.get("priority_score"))
            curated["relation_to_target_topic"] = "low"
            reason_text = "; ".join(reasons) if reasons else "curation_rule_downgrade"
            if existing_tier.startswith("D"):
                action = "confirm_d"
                note_prefix = "Curated as confirmed D"
            else:
                action = "downgrade_to_d"
                note_prefix = "Curated as D"
            curated["curation_action"] = action
            curated["curation_reason"] = reason_text
            curated["coding_note"] = self._append_coding_note(coding_note, f"{note_prefix}: {reason_text}")
            return curated, action, reasons or ["curation_rule_downgrade"]

        curated["curation_action"] = "keep"
        if positive_hits:
            curated["curation_reason"] = "positive_keywords:" + ",".join(positive_hits[:5])
        else:
            curated["curation_reason"] = "kept_by_existing_ai_code"
        return curated, "keep", ["keep"]

    def _downgraded_score(self, value: Any) -> int:
        try:
            score = int(float(value))
        except (TypeError, ValueError):
            score = 40
        return min(score, 40)

    def _append_coding_note(self, old_note: str, new_note: str) -> str:
        if not old_note:
            return new_note
        if new_note in old_note:
            return old_note
        return f"{old_note}\n{new_note}"

    def _write_curation_report(
        self,
        project: ReviewProject,
        rows: list[dict[str, Any]],
        *,
        action_counts: Counter[str],
        reason_counts: Counter[str],
        report_path: Path,
        applied: bool,
    ) -> None:
        tier_counts = Counter(str(row.get("tier") or "unknown") for row in rows)
        downgraded = [row for row in rows if row.get("curation_action") == "downgrade_to_d"]
        confirmed = [row for row in rows if row.get("curation_action") == "confirm_d"]
        kept = [row for row in rows if row.get("curation_action") == "keep"]
        lines = [
            "# Curation Report",
            "",
            f"- topic: {project.topic}",
            f"- updated_at: {_utc_now()}",
            f"- source: `data/processed/paper_pool_coded.csv`",
            f"- output: `data/processed/paper_pool_curated.csv`",
            f"- applied_to_coded_pool: {applied}",
            "",
            "## Action Counts",
        ]
        for action, count in sorted(action_counts.items()):
            lines.append(f"- {action}: {count}")
        lines.extend(["", "## Tier Counts After Curation"])
        for tier, count in sorted(tier_counts.items()):
            lines.append(f"- {tier}: {count}")
        lines.extend(["", "## Top Curation Reasons"])
        for reason, count in reason_counts.most_common(20):
            lines.append(f"- {reason}: {count}")
        lines.extend(["", "## Downgraded Papers"])
        for row in downgraded:
            lines.append(
                f"- {row.get('paper_id')}: {row.get('title')} "
                f"({row.get('original_tier')} -> {row.get('tier')}) - {row.get('curation_reason')}"
            )
        lines.extend(["", "## Confirmed D Papers"])
        for row in confirmed[:80]:
            lines.append(f"- {row.get('paper_id')}: {row.get('title')} - {row.get('curation_reason')}")
        lines.extend(["", "## Kept Papers"])
        for row in kept[:80]:
            lines.append(f"- {row.get('paper_id')}: {row.get('title')} - {row.get('curation_reason')}")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _reading_card_flags(self, project: ReviewProject, row: dict[str, Any], *, include_markers: bool) -> list[str]:
        card = str(row.get("reading_card") or "").strip()
        if not card:
            return ["missing_reading_card_path"]
        card_path = project.path / card
        if not card_path.exists():
            return ["missing_reading_card_file"]
        if not include_markers:
            return []
        text = card_path.read_text(encoding="utf-8").lower()
        flags: list[str] = []
        if "full text missing" in text or "abstract and full text missing" in text or "metadata-only" in text:
            flags.append("metadata_or_full_text_missing")
        if "strictly inferred" in text or "strictly based on title" in text:
            flags.append("inferred_without_full_text")
        if "needs_verification" in text or "待复核" in text:
            flags.append("needs_verification_markers")
        return flags

    def _curated_tier_mismatches(self, coded_rows: list[dict[str, Any]], curated_rows: list[dict[str, Any]]) -> list[str]:
        if not curated_rows:
            return []
        curated_by_id = {row.get("paper_id"): row for row in curated_rows if row.get("paper_id")}
        mismatches: list[str] = []
        for row in coded_rows:
            paper_id = row.get("paper_id")
            if not paper_id or paper_id not in curated_by_id:
                continue
            coded_tier = row.get("tier") or ""
            curated_tier = curated_by_id[paper_id].get("tier") or ""
            if coded_tier != curated_tier:
                mismatches.append(f"{paper_id}: coded={coded_tier}, curated={curated_tier}")
        return mismatches

    def _write_qc_report(
        self,
        project: ReviewProject,
        *,
        report_path: Path,
        coded_rows: list[dict[str, Any]],
        draft_path: Path,
        citation_rows: list[dict[str, str]],
        bib_keys: set[str],
        tier_counts: Counter[str],
        evidence_tier_counts: Counter[str],
        draft_ids: list[str],
        evidence_ids: list[str],
        draft_citation_keys: list[str],
        d_screening_ids: list[str],
        d_evidence_ids: list[str],
        core_rows: list[dict[str, Any]],
        cited_core_ids: set[str],
        unused_core: list[dict[str, Any]],
        verification_rows: list[dict[str, Any]],
        findings: list[dict[str, str]],
        placeholder_count: int,
    ) -> None:
        severity_counts = Counter(item["severity"] for item in findings)
        lines = [
            "# Review QC Report",
            "",
            f"- topic: {project.topic}",
            f"- updated_at: {_utc_now()}",
            f"- coded_pool: `data/processed/paper_pool_coded.csv`",
            f"- draft: `{draft_path.relative_to(project.path) if draft_path.is_relative_to(project.path) else draft_path}`",
            f"- total_coded_papers: {len(coded_rows)}",
            f"- draft_paper_mentions: {len(draft_ids)}",
            f"- evidence_section_paper_mentions: {len(evidence_ids)}",
            f"- draft_citation_keys: {len(draft_citation_keys)}",
            f"- citation_key_rows: {len(citation_rows)}",
            f"- bib_entries: {len(bib_keys)}",
            f"- draft_placeholder_markers: {placeholder_count}",
            "",
            "## Verdict",
        ]
        if findings:
            lines.append(f"- QC found {len(findings)} issue groups: {dict(sorted(severity_counts.items()))}")
        else:
            lines.append("- No blocking QC issues detected by automated checks.")

        lines.extend(["", "## Layer Counts"])
        for tier, count in sorted(tier_counts.items()):
            lines.append(f"- {tier}: {count}")
        lines.extend(["", "## Evidence Mention Counts"])
        if evidence_tier_counts:
            for tier, count in sorted(evidence_tier_counts.items()):
                lines.append(f"- {tier}: {count}")
        else:
            lines.append("- No `[Pxxx]` paper IDs found in evidence sections.")

        lines.extend(["", "## Findings"])
        if not findings:
            lines.append("- None.")
        for item in findings:
            lines.append(f"- [{item['severity']}] {item['title']}: {item['detail']}")

        lines.extend(["", "## Draft Citation Coverage"])
        lines.append(f"- all_paper_ids_in_draft: {', '.join(draft_ids) if draft_ids else 'none'}")
        lines.append(f"- evidence_paper_ids: {', '.join(evidence_ids) if evidence_ids else 'none'}")
        lines.append(f"- citation_keys_in_draft: {', '.join(draft_citation_keys) if draft_citation_keys else 'none'}")
        if d_screening_ids:
            lines.append(f"- D-tier IDs mentioned only in screening/reference sections: {', '.join(d_screening_ids)}")
        if d_evidence_ids:
            lines.append(f"- D-tier IDs in evidence sections: {', '.join(d_evidence_ids)}")

        lines.extend(["", "## A/B Core Pool Readiness"])
        lines.append("| paper_id | tier | score | cited | citation_key | reading_card | qc_notes |")
        lines.append("|---|---|---:|---|---|---|---|")
        verification_ids = {row.get("paper_id") for row in verification_rows}
        unused_ids = {row.get("paper_id") for row in unused_core}
        for row in core_rows:
            paper_id = row.get("paper_id", "")
            notes: list[str] = []
            if paper_id in unused_ids:
                notes.append("not_cited")
            if paper_id in verification_ids:
                notes.extend(self._reading_card_flags(project, row, include_markers=True) or ["needs_verification"])
            if not notes:
                notes.append("ok")
            card = "yes" if row.get("reading_card") and (project.path / str(row.get("reading_card"))).exists() else "missing"
            lines.append(
                "| {paper_id} | {tier} | {score} | {cited} | {key} | {card} | {notes} |".format(
                    paper_id=paper_id,
                    tier=row.get("tier", ""),
                    score=row.get("priority_score", ""),
                    cited="yes" if paper_id in cited_core_ids else "no",
                    key=row.get("citation_key", ""),
                    card=card,
                    notes=", ".join(dict.fromkeys(notes)),
                )
            )

        lines.extend(["", "## Needs Full-Text / Manual Verification"])
        if verification_rows:
            for row in verification_rows:
                flags = self._reading_card_flags(project, row, include_markers=True) or ["coded_fields_need_verification"]
                lines.append(f"- {row.get('paper_id')}: {row.get('title')} - {', '.join(dict.fromkeys(flags))}")
        else:
            lines.append("- No A/B paper has automated full-text or verification warnings.")

        lines.extend(["", "## Next Actions"])
        next_actions: list[str] = []
        if d_evidence_ids:
            next_actions.append("Remove or rewrite draft evidence that relies on D-tier papers.")
        if unused_core:
            next_actions.append("Decide whether uncited A/B papers should be cited, moved to C/D, or excluded from the draft narrative.")
        if verification_rows:
            next_actions.append("Retrieve or inspect full text for A/B papers with needs_verification markers before final claims.")
        if placeholder_count:
            next_actions.append("Resolve high-impact `needs_verification` placeholders in the draft.")
        next_actions.append("Generate comparison/taxonomy matrices after the remaining QC warnings are reviewed.")
        for action in next_actions:
            lines.append(f"- {action}")

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _matrix_row(self, project: ReviewProject, row: dict[str, Any]) -> dict[str, Any]:
        flags = self._verification_flags(project, row)
        return {
            "paper_id": row.get("paper_id", ""),
            "citation_key": row.get("citation_key", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "tier": row.get("tier", ""),
            "priority_score": row.get("priority_score", ""),
            "taxonomy_branch": self._taxonomy_branch(row),
            "task_type": row.get("task_type", ""),
            "method_type": row.get("method_type", ""),
            "model_or_system_type": row.get("model_or_system_type", ""),
            "data_type": row.get("data_type", ""),
            "benchmark_or_environment": row.get("benchmark_or_environment", ""),
            "real_world_or_simulation": row.get("real_world_or_simulation", ""),
            "open_source_status": row.get("open_source_status", ""),
            "evidence_strength": row.get("evidence_strength", ""),
            "engineering_reusability": row.get("engineering_reusability", ""),
            "relation_to_target_topic": row.get("relation_to_target_topic", ""),
            "verification_flags": "; ".join(flags) if flags else "ok",
            "reading_card": row.get("reading_card", ""),
        }

    def _taxonomy_branch(self, row: dict[str, Any]) -> str:
        primary_text = " ".join(
            str(row.get(field, ""))
            for field in [
                "title",
                "research_direction",
                "task_type",
                "method_type",
                "model_or_system_type",
            ]
        ).lower()
        full_text = " ".join(
            str(row.get(field, ""))
            for field in [
                "title",
                "research_direction",
                "task_type",
                "method_type",
                "model_or_system_type",
                "benchmark_or_environment",
                "core_contribution",
                "relation_to_target_topic",
            ]
        ).lower()
        if any(term in primary_text for term in ("llm", "large language", "rag", "semantic", "knowledge", "语言模型", "语义", "知识")):
            return "Semantic / Knowledge-Augmented Models"
        if any(term in primary_text for term in ("trust", "unreliable", "uncertainty-quantified", "信任", "不确定")):
            return "Trust-Aware / Uncertainty-Quantified Models"
        if any(term in primary_text for term in ("benchmark", "benchmarking", "evaluation infrastructure", "测试床", "基准")):
            return "Validation / Evaluation Infrastructure"
        if any(term in full_text for term in ("neuromechanical", "neuromorphic", "visuomotor", "bio-inspired", "simzfish", "zbot", "神经力学", "神经", "生物启发")):
            return "Neuromechanical / Bio-inspired Models"
        if any(term in primary_text for term in ("morpholog", "physical intelligence", "microrobot", "touch", "tactile", "implicit", "形态", "触觉", "物理本体", "隐式")):
            return "Implicit / Morphological / Physical Models"
        if any(term in primary_text for term in ("contact-state", "support pose", "multi-contact", "接触态", "支撑位姿")):
            return "Structured Contact / Interaction State Models"
        if any(term in full_text for term in ("testbed", "benchmark", "benchmarking", "evaluation infrastructure", "测试床", "基准")):
            return "Validation / Evaluation Infrastructure"
        if any(term in full_text for term in ("causal", "intervention", "因果", "干预")):
            return "Causal / Structural World Models"
        if any(term in primary_text for term in ("dynamics", "predictive", "world model", "model-based", "动力学", "预测")):
            return "Explicit Predictive / Dynamics Models"
        return "Application / Contextual Supporting Papers"

    def _verification_flags(self, project: ReviewProject, row: dict[str, Any]) -> list[str]:
        if row.get("_pre_coding_target"):
            return ["pre_coding_fulltext_check"]
        flags: list[str] = []
        if any(_has_verification_marker(row.get(field, "")) for field in CODED_POOL_FIELDS):
            flags.append("coded_fields_need_verification")
        card_flags = self._reading_card_flags(project, row, include_markers=True)
        flags.extend(card_flags)
        return list(dict.fromkeys(flags))

    def _short_cell(self, value: Any, limit: int = 90) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _write_matrix_report(
        self,
        project: ReviewProject,
        *,
        report_path: Path,
        matrix_rows: list[dict[str, Any]],
        branch_counts: Counter[str],
        tier_counts: Counter[str],
        include_tiers: tuple[str, ...],
    ) -> None:
        lines = [
            "# Comparison Matrix",
            "",
            f"- topic: {project.topic}",
            f"- updated_at: {_utc_now()}",
            f"- source: `data/processed/paper_pool_coded.csv`",
            f"- included_tiers: {', '.join(include_tiers)}",
            f"- included_papers: {len(matrix_rows)}",
            "",
            "## Tier Counts",
        ]
        for tier, count in sorted(tier_counts.items()):
            lines.append(f"- {tier}: {count}")
        lines.extend(["", "## Taxonomy Branch Counts"])
        for branch, count in branch_counts.most_common():
            lines.append(f"- {branch}: {count}")

        lines.extend(["", "## Taxonomy Matrix"])
        lines.append("| branch | paper_id | tier | title | method/system | task/environment | verification |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in sorted(matrix_rows, key=lambda item: (item["taxonomy_branch"], item["paper_id"])):
            task_env = self._short_cell(
                "; ".join(
                    part
                    for part in [row.get("task_type"), row.get("benchmark_or_environment")]
                    if part
                )
            )
            lines.append(
                "| {branch} | {paper_id} | {tier} | {title} | {method} | {task_env} | {flags} |".format(
                    branch=row.get("taxonomy_branch", ""),
                    paper_id=row.get("paper_id", ""),
                    tier=row.get("tier", ""),
                    title=self._short_cell(row.get("title"), 70),
                    method=self._short_cell(row.get("model_or_system_type") or row.get("method_type"), 80),
                    task_env=task_env,
                    flags=self._short_cell(row.get("verification_flags"), 80),
                )
            )

        lines.extend(["", "## Evidence Matrix"])
        lines.append("| paper_id | citation_key | contribution | limitation | evidence | reuse |")
        lines.append("|---|---|---|---|---|---|")
        for row in sorted(matrix_rows, key=lambda item: (item["tier"], item["paper_id"])):
            lines.append(
                "| {paper_id} | {key} | {contribution} | {limitation} | {evidence} | {reuse} |".format(
                    paper_id=row.get("paper_id", ""),
                    key=row.get("citation_key", ""),
                    contribution=self._short_cell(row.get("relation_to_target_topic"), 110),
                    limitation=self._short_cell(row.get("verification_flags"), 80),
                    evidence=self._short_cell(row.get("evidence_strength"), 70),
                    reuse=self._short_cell(row.get("engineering_reusability"), 80),
                )
            )

        lines.extend(["", "## Matrix Notes"])
        lines.append("- `verification_flags=ok` means the automated checks did not find explicit verification markers; it is not a guarantee of full-text validation.")
        lines.append("- Rows with `needs_verification` should be treated as draft-level evidence until the PDF/full text is inspected.")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_taxonomy_mermaid(self, path: Path, matrix_rows: list[dict[str, Any]], branch_counts: Counter[str]) -> None:
        by_branch: dict[str, list[dict[str, Any]]] = {}
        for row in matrix_rows:
            by_branch.setdefault(row["taxonomy_branch"], []).append(row)
        lines = ["flowchart TD", '  root["Embodied AI World Models"]']
        for index, (branch, _) in enumerate(branch_counts.most_common(), start=1):
            branch_id = f"B{index}"
            branch_label = f"{branch} ({branch_counts[branch]})".replace('"', "'")
            lines.append(f'  root --> {branch_id}["{branch_label}"]')
            for row in sorted(by_branch.get(branch, []), key=lambda item: item["paper_id"])[:8]:
                paper_id = row.get("paper_id") or "Paper"
                node_id = re.sub(r"[^A-Za-z0-9_]+", "_", str(paper_id))
                title = self._short_cell(row.get("title"), 45).replace('"', "'")
                lines.append(f'  {branch_id} --> {node_id}["{paper_id}: {title}"]')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _fulltext_queue_row(
        self,
        project: ReviewProject,
        row: dict[str, Any],
        pool_row: dict[str, Any],
        options: ReviewVerifyOptions,
    ) -> dict[str, Any]:
        zotero_error = ""
        pdf_count = 0
        local_paths: list[str] = []
        local_pdf_count = 0
        zotero_key = row.get("zotero_key") or pool_row.get("zotero_key") or ""
        for pdf_path in _project_pdf_paths(project, str(row.get("paper_id") or "")):
            local_paths.append(str(pdf_path))
            local_pdf_count += 1
        if options.check_zotero and self.zotero is not None and zotero_key:
            try:
                children = self.zotero.fetch_children(zotero_key)
                pdfs = _find_pdf_attachment_data(children)
                pdf_count = len(pdfs)
                if options.storage_dir is not None:
                    for attachment in pdfs:
                        pdf_path = _resolve_attachment_path(options.storage_dir, attachment)
                        local_paths.append(str(pdf_path))
                        if pdf_path.exists():
                            local_pdf_count += 1
            except Exception as exc:
                zotero_error = f"{type(exc).__name__}: {exc}"

        doi = pool_row.get("doi", "")
        arxiv_id = pool_row.get("arxiv_id", "")
        paper_url = pool_row.get("paper_url") or pool_row.get("official_url") or pool_row.get("arxiv_url") or ""
        flags = self._verification_flags(project, row)
        if local_pdf_count > 0:
            status = "ready_local_pdf"
            action = "Extract PDF text and rerun AI reading with full text."
        elif pdf_count > 0:
            status = "zotero_pdf_missing_local_file"
            action = "Check ZOTERO_STORAGE_DIR or sync Zotero storage files locally."
        elif arxiv_id:
            status = "arxiv_or_deepxiv_candidate"
            action = "Use arXiv/DeepXiv full text route, then rerun AI reading."
        elif doi or paper_url:
            status = "needs_publisher_pdf"
            action = "Open DOI/publisher page or Zotero PDF retrieval, then attach/sync PDF."
        else:
            status = "metadata_only"
            action = "Search by title and attach a primary-source PDF before using as core evidence."

        if zotero_error and status == "needs_publisher_pdf":
            status = "zotero_check_failed"
            action = "Retry Zotero child-item lookup, then inspect DOI/publisher page."

        return {
            "paper_id": row.get("paper_id", ""),
            "citation_key": row.get("citation_key", ""),
            "title": row.get("title", ""),
            "tier": row.get("tier", ""),
            "priority_score": row.get("priority_score", ""),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "paper_url": paper_url,
            "zotero_key": zotero_key,
            "zotero_pdf_count": pdf_count,
            "local_pdf_count": local_pdf_count,
            "local_pdf_paths": "; ".join(local_paths),
            "verification_status": status,
            "verification_flags": "; ".join(flags) if flags else "ok",
            "recommended_action": action,
            "zotero_error": zotero_error,
        }

    def _write_fulltext_verification_report(
        self,
        project: ReviewProject,
        *,
        report_path: Path,
        queue_rows: list[dict[str, Any]],
        status_counts: Counter[str],
        include_tiers: tuple[str, ...],
        source_csv: str,
        storage_dir: Optional[Path],
        checked_zotero: bool,
    ) -> None:
        lines = [
            "# Full-Text Verification Status",
            "",
            f"- topic: {project.topic}",
            f"- updated_at: {_utc_now()}",
            f"- source: `{source_csv}`",
            f"- output: `data/processed/fulltext_verification_queue.csv`",
            f"- included_tiers: {', '.join(include_tiers)}",
            f"- target_papers: {len(queue_rows)}",
            f"- checked_zotero: {checked_zotero}",
            f"- storage_dir: `{storage_dir}`" if storage_dir else "- storage_dir: not configured",
            "",
            "## Status Counts",
        ]
        for status, count in status_counts.most_common():
            lines.append(f"- {status}: {count}")

        lines.extend(["", "## Verification Queue"])
        lines.append("| paper_id | tier | title | status | zotero_pdf | local_pdf | action |")
        lines.append("|---|---|---|---|---:|---:|---|")
        for row in queue_rows:
            lines.append(
                "| {paper_id} | {tier} | {title} | {status} | {pdfs} | {local} | {action} |".format(
                    paper_id=row.get("paper_id", ""),
                    tier=row.get("tier", ""),
                    title=self._short_cell(row.get("title"), 70),
                    status=row.get("verification_status", ""),
                    pdfs=row.get("zotero_pdf_count", ""),
                    local=row.get("local_pdf_count", ""),
                    action=self._short_cell(row.get("recommended_action"), 90),
                )
            )

        ready = [row for row in queue_rows if row.get("verification_status") == "ready_local_pdf"]
        needs_pdf = [row for row in queue_rows if row.get("verification_status") != "ready_local_pdf"]
        lines.extend(["", "## Ready For Full-Text Rereading"])
        if ready:
            for row in ready:
                lines.append(f"- {row.get('paper_id')}: {row.get('local_pdf_paths')}")
        else:
            lines.append("- None yet.")
        lines.extend(["", "## Needs PDF Or Storage Fix"])
        if needs_pdf:
            for row in needs_pdf:
                extra = f" DOI: {row.get('doi')}" if row.get("doi") else ""
                lines.append(f"- {row.get('paper_id')}: {row.get('verification_status')} - {row.get('recommended_action')}{extra}")
        else:
            lines.append("- None.")

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _fetch_pdf_for_row(
        self,
        project: ReviewProject,
        row: dict[str, Any],
        pool_row: dict[str, Any],
        options: ReviewFetchPdfOptions,
        output_dir: Path,
        oa_client: Any,
    ) -> dict[str, Any]:
        paper_id = str(row.get("paper_id") or "")
        doi = pool_row.get("doi", "")
        arxiv_id = pool_row.get("arxiv_id", "")
        title = row.get("title", "")
        zotero_key = row.get("zotero_key") or pool_row.get("zotero_key") or ""
        destination = output_dir / f"{paper_id}_{_safe_filename(title)}.pdf"
        attached_to_zotero = False
        error = ""

        if destination.exists() and not options.force:
            return {
                "paper_id": paper_id,
                "citation_key": row.get("citation_key", ""),
                "title": title,
                "tier": row.get("tier", ""),
                "doi": doi,
                "arxiv_id": arxiv_id,
                "zotero_key": zotero_key,
                "oa_status": "existing_local_pdf",
                "oa_source": "local",
                "pdf_url": "",
                "landing_url": "",
                "local_pdf_path": str(destination),
                "attached_to_zotero": False,
                "fetch_error": "",
            }

        lookup = oa_client.find_pdf(doi=doi, arxiv_id=arxiv_id)
        local_pdf_path = ""
        status = lookup.status
        if lookup.status == "found" and lookup.pdf_url:
            if options.dry_run:
                status = "found_dry_run"
            else:
                try:
                    downloaded = oa_client.download_pdf(lookup.pdf_url, destination, force=options.force)
                    local_pdf_path = str(downloaded)
                    status = "downloaded"
                    if options.attach_zotero and self.zotero is not None and zotero_key:
                        self.zotero.create_attachment_url(
                            zotero_key,
                            f"Open-access PDF - {paper_id}",
                            lookup.pdf_url,
                        )
                        attached_to_zotero = True
                        status = "attached_to_zotero"
                except Exception as exc:
                    status = "download_failed"
                    error = f"{type(exc).__name__}: {exc}"

        return {
            "paper_id": paper_id,
            "citation_key": row.get("citation_key", ""),
            "title": title,
            "tier": row.get("tier", ""),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "zotero_key": zotero_key,
            "oa_status": status,
            "oa_source": lookup.source,
            "pdf_url": lookup.pdf_url,
            "landing_url": lookup.landing_url,
            "local_pdf_path": local_pdf_path,
            "attached_to_zotero": attached_to_zotero,
            "fetch_error": error or lookup.error,
        }

    def _write_fulltext_fetch_report(
        self,
        project: ReviewProject,
        *,
        report_path: Path,
        fetch_rows: list[dict[str, Any]],
        status_counts: Counter[str],
        include_tiers: tuple[str, ...],
        source_csv: str,
        output_dir: Path,
        dry_run: bool,
        attach_zotero: bool,
    ) -> None:
        lines = [
            "# Full-Text Fetch Status",
            "",
            f"- topic: {project.topic}",
            f"- updated_at: {_utc_now()}",
            f"- source: `{source_csv}`",
            f"- output_csv: `data/processed/fulltext_fetch_report.csv`",
            f"- output_dir: `{output_dir}`",
            f"- included_tiers: {', '.join(include_tiers)}",
            f"- target_papers: {len(fetch_rows)}",
            f"- dry_run: {dry_run}",
            f"- attach_zotero: {attach_zotero}",
            "",
            "## Status Counts",
        ]
        for status, count in status_counts.most_common():
            lines.append(f"- {status}: {count}")

        lines.extend(["", "## Fetch Results"])
        lines.append("| paper_id | tier | status | source | title | pdf_url | local_pdf |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in fetch_rows:
            lines.append(
                "| {paper_id} | {tier} | {status} | {source} | {title} | {pdf_url} | {local_pdf} |".format(
                    paper_id=row.get("paper_id", ""),
                    tier=row.get("tier", ""),
                    status=row.get("oa_status", ""),
                    source=row.get("oa_source", ""),
                    title=self._short_cell(row.get("title"), 65),
                    pdf_url=self._short_cell(row.get("pdf_url"), 55),
                    local_pdf=self._short_cell(row.get("local_pdf_path"), 55),
                )
            )

        lines.extend(["", "## Next Actions"])
        if any(row.get("oa_status") in {"downloaded", "attached_to_zotero", "existing_local_pdf"} for row in fetch_rows):
            lines.append("- Rerun `review verify`; rows with downloaded PDFs should become `ready_local_pdf`.")
            lines.append("- Then rerun `review read --force` for ready papers to replace metadata-only notes with full-text readings.")
        if any(row.get("oa_status") == "missing_unpaywall_email" for row in fetch_rows):
            lines.append("- Set `UNPAYWALL_EMAIL` in `.env` or pass `--unpaywall-email` to enable DOI-based OA lookup.")
        if any(row.get("oa_status") in {"not_open_access", "oa_landing_only", "lookup_failed", "download_failed"} for row in fetch_rows):
            lines.append("- For unresolved papers, use Zotero's PDF retrieval or attach publisher PDFs manually, then rerun `review verify`.")

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
        row = {
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
            "source": _infer_pool_source(data, doi, arxiv_id),
            "dedupe_key": "",
            "source_quality": "primary" if doi or arxiv_id else "secondary",
            "verification_status": "partially_verified",
            "fulltext_status": "",
            "relevance_score": "",
            "topic_relevance": "needs_review",
            "screening_decision": "needs_manual_screening",
            "screening_reason": "",
            "reason_to_include": "",
            "reason_to_exclude_or_downgrade": "",
            "notes": "",
            "citation_key": citation_key,
            "abstract": data.get("abstractNote") or data.get("abstract") or "",
        }
        row["dedupe_key"] = _dedupe_key_for_pool_row(row)
        row["fulltext_status"] = _infer_fulltext_status(row)
        return row

    def _deduplicate_pool_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            dedupe_key = row.get("dedupe_key") or _dedupe_key_for_pool_row(row)
            row["dedupe_key"] = dedupe_key
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(row)
        return out

    def _write_pool_report(self, project: ReviewProject, raw_rows: list[dict[str, Any]], verified_rows: list[dict[str, Any]]) -> None:
        venues = sorted({row.get("venue") for row in verified_rows if row.get("venue")})
        years = sorted({row.get("year") for row in verified_rows if row.get("year")})
        source_counts = Counter(row.get("source") or "unknown" for row in verified_rows)
        decision_counts = Counter(row.get("screening_decision") or "unknown" for row in verified_rows)
        relevance_counts = Counter(row.get("topic_relevance") or "unknown" for row in verified_rows)
        fulltext_counts = Counter(row.get("fulltext_status") or "unknown" for row in verified_rows)
        dedupe_counts = Counter(row.get("dedupe_key") or _dedupe_key_for_pool_row(row) for row in raw_rows)
        duplicate_keys = [(key, count) for key, count in dedupe_counts.items() if key and count > 1]
        scored_rows = [
            row
            for row in verified_rows
            if str(row.get("relevance_score") or "").isdigit()
        ]
        score_values = [int(row.get("relevance_score")) for row in scored_rows]
        avg_score = round(sum(score_values) / len(score_values), 1) if score_values else "n/a"
        included = [row for row in verified_rows if row.get("screening_decision") == "include_for_reading"]
        manual = [row for row in verified_rows if row.get("screening_decision") == "needs_manual_screening"]
        excluded = [row for row in verified_rows if row.get("screening_decision") == "exclude_candidate"]

        def count_lines(counter: Counter[str]) -> str:
            if not counter:
                return "- none"
            return "\n".join(f"- {key}: {count}" for key, count in counter.most_common())

        def row_lines(rows: list[dict[str, Any]], limit: int = 20) -> str:
            if not rows:
                return "- none"
            lines = []
            for row in rows[:limit]:
                lines.append(
                    "- {paper_id}: {title} (score={score}, reason={reason})".format(
                        paper_id=row.get("paper_id", ""),
                        title=row.get("title", ""),
                        score=row.get("relevance_score", ""),
                        reason=row.get("screening_reason", ""),
                    )
                )
            if len(rows) > limit:
                lines.append(f"- ... {len(rows) - limit} more")
            return "\n".join(lines)

        content = f"""# Paper Pool Verification Report

## Topic
{project.topic}

## Input Sources
- Zotero

## Total Papers
- raw: {len(raw_rows)}
- verified: {len(verified_rows)}
- duplicates_removed: {max(0, len(raw_rows) - len(verified_rows))}

## Source Counts
{count_lines(source_counts)}

## Screening Decision Counts
{count_lines(decision_counts)}

## Topic Relevance Counts
{count_lines(relevance_counts)}

## Fulltext Status Counts
{count_lines(fulltext_counts)}

## Relevance Score
- average: {avg_score}
- scored_rows: {len(scored_rows)}

## Duplicate Keys Removed
{row_lines([{"paper_id": key, "title": f"count={count}", "relevance_score": "", "screening_reason": ""} for key, count in duplicate_keys], limit=20)}

## Venue Coverage
{", ".join(venues) if venues else "待复核"}

## Year Coverage
{", ".join(years) if years else "待复核"}

## Include For Reading
{row_lines(included)}

## Manual Screening Queue
{row_lines(manual)}

## Exclude Candidates
{row_lines(excluded)}

## Remaining Unverified Items
- `screening_decision=needs_manual_screening` 的条目需要人工确认纳入/排除。
- `fulltext_status` 不是 `open_access_candidate` 的条目需要后续全文获取或人工复核。

## Next Step
- 运行 `review fetch-pdfs` 和 `review verify` 补全文状态。
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

    def _build_reading_context(self, project: ReviewProject, row: dict[str, str], options: ReviewReadOptions) -> str:
        parts = [
            f"Title: {row.get('title', '')}",
            f"Year: {row.get('year', '')}",
            f"Venue: {row.get('venue', '')}",
            f"Authors: {row.get('authors', '')}",
            f"DOI: {row.get('doi', '')}",
            f"arXiv: {row.get('arxiv_id', '')}",
            f"Abstract:\n{row.get('abstract', '')}",
        ]
        if options.use_local_pdfs:
            for pdf_path in _project_pdf_paths(project, row.get("paper_id", "")):
                try:
                    pdf_text = extract_pdf_text(pdf_path, options.pdf_max_pages)
                except Exception as exc:
                    parts.append(f"Local PDF extraction failed for {pdf_path}: {type(exc).__name__}: {exc}")
                    continue
                if pdf_text.strip():
                    parts.append(f"Local PDF excerpt ({pdf_path}):\n{pdf_text[: options.max_chars]}")
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
        score, validation_issues = _normalize_priority_score(score_raw, int(default["priority_score"]))
        tier, tier_issues = _normalize_tier(code_data.get("tier"), score)
        confidence, confidence_issues = _normalize_coding_confidence(code_data.get("coding_confidence"))
        validation_issues.extend(tier_issues)
        validation_issues.extend(confidence_issues)
        validation_issues.extend(_coding_validation_issues(code_data))
        validation_issues = list(dict.fromkeys(validation_issues))

        out_status = "needs_review" if validation_issues else status
        out = {
            **default,
            "priority_score": score,
            "tier": tier,
            "coding_confidence": confidence,
            "status": out_status,
        }
        for field in CODED_POOL_FIELDS:
            if field in {"paper_id", "zotero_key", "title", "year", "venue", "citation_key", "priority_score", "tier", "coding_confidence", "reading_card", "status"}:
                continue
            if field in code_data:
                out[field] = code_data.get(field, "")
        if validation_issues:
            note = str(out.get("coding_note") or "").strip()
            validation_note = "validation_issues=" + ",".join(validation_issues)
            out["coding_note"] = f"{note}; {validation_note}" if note else validation_note
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
