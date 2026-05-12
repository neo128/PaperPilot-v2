from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


GENERIC_MARKERS = (
    "当前批量总结",
    "题名和元数据表明",
    "中文题名辅助理解",
    "仅依据题名",
    "仅根据题名",
    "从题名看",
    "从标题看",
    "需进一步阅读全文确认",
    "需要进一步阅读全文确认",
    "需要进一步确认",
    "原文片段未提供",
    "片段已截断",
    "仅基于此生成",
    "来源限制",
    "未获得开放全文",
    "metadata only",
    "metadata-only",
)

EXPECTED_SECTIONS = (
    "论文基本信息",
    "一句话总结",
    "研究问题",
    "方法概述",
    "技术流程",
    "创新",
    "技术坐标系",
    "实验与结果",
    "局限",
    "失败模式",
    "通用复用价值",
    "分类标签",
    "高质量证据",
)

SOURCE_PRIORITY = {
    "pdf": "pdf_text",
    "pdf_text": "pdf_text",
    "pdf_excerpt": "pdf_excerpt",
    "truncated_pdf_text": "pdf_excerpt",
    "deepxiv": "structured_fulltext",
    "structured_fulltext": "structured_fulltext",
    "abstract": "abstract_only",
    "abstract_only": "abstract_only",
    "metadata": "metadata_only",
    "metadata_only": "metadata_only",
    "text": "text",
}


@dataclass
class SummaryQualityReport:
    score: int
    label: str
    findings: list[str] = field(default_factory=list)
    source_coverage: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "findings": self.findings,
            "source_coverage": self.source_coverage,
            "stats": self.stats,
        }


def _count_cjk(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def _count_latin_words(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z\-]{2,}\b", text or ""))


def _heading_texts(markdown: str) -> list[str]:
    headings: list[str] = []
    for line in (markdown or "").splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def _has_section(headings: list[str], expected: str) -> bool:
    return any(expected in heading for heading in headings)


def _source_coverage(source: str, markdown: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized in SOURCE_PRIORITY:
        return SOURCE_PRIORITY[normalized]
    lowered = (markdown or "").lower()
    if any(marker in lowered for marker in ("metadata only", "metadata-only")):
        return "metadata_only"
    if "题名和元数据表明" in markdown or "仅依据题名" in markdown:
        return "metadata_only"
    if "片段已截断" in markdown or "仅基于此生成" in markdown:
        return "pdf_excerpt"
    if "来源限制" in markdown or "未获得开放全文" in markdown:
        return "abstract_only"
    return normalized or "unknown"


def assess_summary_quality(
    markdown: str,
    *,
    source: str = "",
    locale: str = "zh",
    min_full_chars: int = 4500,
) -> SummaryQualityReport:
    """Heuristically assess whether an AI paper summary is reusable.

    The goal is not to grade prose style; it is to catch summaries that are
    obviously metadata cards, English-heavy, missing required sections, or too
    generic to support later review coding.
    """
    text = markdown or ""
    findings: list[str] = []
    stats: dict[str, Any] = {}
    score = 100

    char_count = len(text.strip())
    headings = _heading_texts(text)
    missing_sections = [section for section in EXPECTED_SECTIONS if not _has_section(headings, section)]
    generic_hits = {marker: text.count(marker) for marker in GENERIC_MARKERS if marker in text}
    source_coverage = _source_coverage(source, text)
    cjk_count = _count_cjk(text)
    latin_words = _count_latin_words(text)
    chinese_ratio = cjk_count / max(cjk_count + latin_words, 1)
    original_marks = text.count("[原文]") + text.count("【原文】")
    inference_marks = text.count("[推断]") + text.count("【推断】")
    inspiration_marks = text.count("[启发]") + text.count("【启发】")
    evidence_like = len(re.findall(r"(证据|支撑|章节|Figure|Table|图\s*\d+|表\s*\d+)", text, re.I))
    number_hits = len(re.findall(r"(?<!\w)(?:\d+(?:\.\d+)?%?|\d+\s*(?:k|K|M|m|GB|MB|ms|s|Hz|fps))(?!\w)", text))
    inspiration_ratio = inspiration_marks / max(original_marks, 1)

    stats.update(
        {
            "char_count": char_count,
            "heading_count": len(headings),
            "missing_section_count": len(missing_sections),
            "generic_marker_count": sum(generic_hits.values()),
            "chinese_ratio": round(chinese_ratio, 3),
            "original_mark_count": original_marks,
            "inference_mark_count": inference_marks,
            "inspiration_mark_count": inspiration_marks,
            "inspiration_to_original_ratio": round(inspiration_ratio, 3),
            "evidence_signal_count": evidence_like,
            "number_signal_count": number_hits,
        }
    )

    if char_count < 1200:
        score -= 40
        findings.append("总结过短，无法支撑后续精读或综述矩阵。")
    elif char_count < min_full_chars:
        score -= 18
        findings.append("总结偏短，可能只是轻量卡片而不是完整 canonical summary。")

    if generic_hits:
        penalty = min(55, 12 * sum(generic_hits.values()))
        score -= penalty
        findings.append("存在模板化或元数据占位表达：" + "，".join(generic_hits.keys()))

    if missing_sections:
        score -= min(28, len(missing_sections) * 3)
        findings.append("缺少模板关键章节：" + "，".join(missing_sections[:8]))

    if (locale or "").lower().startswith("zh") and chinese_ratio < 0.68:
        score -= 18 if chinese_ratio >= 0.5 else 32
        findings.append("中文占比偏低，正文可能混入过多英文段落。")

    if original_marks == 0:
        score -= 10
        findings.append("缺少 [原文] 标注，事实层证据不可审计。")

    if inspiration_marks >= 8 and inspiration_ratio > 0.5:
        score -= 14
        findings.append("启发/跨域推断占比偏高，可能存在模板填充或主题污染。")

    if inference_marks >= original_marks * 2 and inference_marks >= 12:
        score -= 10
        findings.append("推断内容明显多于原文事实，建议复核是否忠实于论文。")

    if evidence_like < 4:
        score -= 10
        findings.append("证据信号不足，缺少可定位的章节、图表或结果支撑。")

    if source_coverage in {"pdf_text", "structured_fulltext"} and generic_hits:
        score -= 15
        findings.append("已有全文/结构化全文输入时仍出现元数据占位，建议强制重跑。")

    if source_coverage == "metadata_only":
        score = min(score, 45)
        findings.append("来源覆盖为 metadata_only，不能视为真实阅读全文总结。")
    elif source_coverage == "abstract_only":
        score = min(score, 55)
        findings.append("来源覆盖为 abstract_only，只能作为摘要卡，不能视为 canonical 全文总结。")
    elif source_coverage == "pdf_excerpt":
        score = min(score, 60)
        findings.append("来源覆盖为 pdf_excerpt，输入被截断，不能视为完整 canonical 总结。")

    score = max(0, min(100, score))
    if source_coverage == "metadata_only":
        label = "metadata_card"
    elif source_coverage == "abstract_only":
        label = "abstract_card"
    elif source_coverage == "pdf_excerpt":
        label = "excerpt_card"
    elif sum(generic_hits.values()) >= 2:
        label = "metadata_card"
    elif score >= 85:
        label = "good"
    elif score >= 70:
        label = "usable"
    elif score >= 50:
        label = "light"
    else:
        label = "needs_rebuild"

    if not findings:
        findings.append("未发现明显结构性问题。")

    return SummaryQualityReport(
        score=score,
        label=label,
        findings=findings,
        source_coverage=source_coverage,
        stats=stats,
    )
