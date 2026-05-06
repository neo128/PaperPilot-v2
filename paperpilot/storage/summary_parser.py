"""Extract structured fields from AI-generated paper summary markdown."""

from __future__ import annotations

import re
from typing import Optional


def extract_structured_fields(
    markdown: str,
    *,
    zotero_key: str = "",
    title_hint: str = "",
    locale: str = "zh",
    model: Optional[str] = None,
    source: Optional[str] = None,
) -> dict:
    """Parse v2/v3 AI summary markdown and return a dict of structured fields.

    Designed for the template with sections:
    1.论文基本信息  2.一句话总结  3.研究问题  4.方法概述
    5.技术流程拆解  6.创新点评估  7.技术坐标系定位
    8.实验与结果  9.局限性  10.失败模式  11.综述价值
    12.分类标签  13.具身智能专用分析  14.潜在研究机会  15.高质量证据片段
    """
    sections = _split_sections(markdown)

    basic = _parse_basic_info(sections.get("1", ""), title_hint)
    paper_title = basic.get("title") or title_hint

    one_line = _extract_subsection(sections.get("2", ""), "原文明确内容")
    research_problem = _merge_subsections(sections.get("3", ""))
    method_overview = _merge_subsections(sections.get("4", ""))
    technical_route = _flatten_text(sections.get("5", ""))
    innovations = _merge_subsections(sections.get("6", ""))
    tech_coordination = _flatten_text(sections.get("7", ""))
    experiments = _flatten_text(sections.get("8", ""))
    limitations = _merge_subsections(sections.get("9", ""))
    failure_modes = _flatten_text(sections.get("10", ""))
    review_value = _merge_subsections(sections.get("11", ""))
    tags = _flatten_text(sections.get("12", ""))
    sec13 = sections.get("13", "")
    robot_task_modeling = _extract_subsection(sec13, "13.1") or _extract_subsection(sec13, "机器人任务建模")
    data_and_platform = _extract_subsection(sec13, "13.2") or _extract_subsection(sec13, "数据与本体")
    perception_decision_control = _extract_subsection(sec13, "13.3") or _extract_subsection(sec13, "感知-决策-控制")
    generalization_deployment = _extract_subsection(sec13, "13.4") or _extract_subsection(sec13, "泛化与部署")
    # Fallback: if numbered subsections aren't found, grab all of section 13
    if not any([robot_task_modeling, data_and_platform, perception_decision_control, generalization_deployment]):
        robot_task_modeling = _flatten_text(sec13)
    research_opportunities = _flatten_text(sections.get("14", ""))
    evidence = _flatten_text(sections.get("15", ""))

    return {
        "title": _clean(paper_title),
        "year": _clean(basic.get("year")),
        "authors": _clean(basic.get("authors")),
        "institution": _clean(basic.get("institution")),
        "field": _clean(basic.get("field")),
        "keywords": _clean(basic.get("keywords")),
        "task_type": _clean(basic.get("task_type")),
        "one_line_summary": _clean(one_line),
        "research_problem": _clean(research_problem),
        "method_overview": _clean(method_overview),
        "technical_route": _clean(technical_route),
        "innovations": _clean(innovations),
        "tech_coordination": _clean(tech_coordination),
        "experiments": _clean(experiments),
        "limitations": _clean(limitations),
        "failure_modes": _clean(failure_modes),
        "review_value": _clean(review_value),
        "tags": _clean(tags),
        "robot_task_modeling": _clean(robot_task_modeling),
        "data_and_platform": _clean(data_and_platform),
        "perception_decision_control": _clean(perception_decision_control),
        "generalization_deployment": _clean(generalization_deployment),
        "research_opportunities": _clean(research_opportunities),
        "evidence": _clean(evidence),
        "full_summary_md": markdown,
        "locale": locale,
        "model": model,
        "source": source,
        "zotero_key": zotero_key,
    }


def _split_sections(markdown: str) -> dict[str, str]:
    """Split markdown by `# N.` section headers."""
    pattern = re.compile(r"^#\s+\d+\.\s+", re.M)
    matches = list(pattern.finditer(markdown))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        header_text = m.group(0).strip()
        num = header_text.lstrip("#").strip().split(".")[0].strip()
        sections[num] = markdown[start:end].strip()
    return sections


def _extract_subsection(text: str, subsection_name: str) -> str:
    """Extract content under a specific ## subsection."""
    pattern = re.compile(rf"^##\s*{re.escape(subsection_name)}\s*$", re.M)
    m = pattern.search(text)
    if not m:
        return ""
    start = m.end()
    next_header = re.search(r"^##\s+", text[start:], re.M)
    end = start + next_header.start() if next_header else len(text)
    return text[start:end].strip()


def _merge_subsections(text: str) -> str:
    """Merge all ## subsections content."""
    return re.sub(r"^##\s+.+\s*$", "", text, flags=re.M).strip()


def _flatten_text(text: str) -> str:
    """Remove `###` headers but keep content."""
    return re.sub(r"^#{1,3}\s+.+\s*$", "", text, flags=re.M).strip()


def _parse_basic_info(section: str, title_hint: str) -> dict[str, str]:
    """Parse section 1 论文基本信息 for sub-fields."""
    result: dict[str, str] = {}

    field_patterns = {
        "title": r"标题[：:]\s*(.+?)(?:\n|$)",
        "year": r"年份[：:]\s*(.+?)(?:\n|$)",
        "authors": r"作者[：:]\s*(.+?)(?:\n|$)",
        "institution": r"机构[：:]\s*(.+?)(?:\n|$)",
        "field": r"领域[：:]\s*(.+?)(?:\n|$)",
        "keywords": r"关键词[：:]\s*(.+?)(?:\n|$)",
        "task_type": r"任务类型[：:]\s*(.+?)(?:\n|$)",
    }
    for key, pat in field_patterns.items():
        m = re.search(pat, section)
        if m:
            result[key] = m.group(1).strip()

    return result


def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() or None
