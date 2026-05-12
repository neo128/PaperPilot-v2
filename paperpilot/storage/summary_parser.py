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
    12.分类标签  13.跨域适配与具身智能启发  14.潜在研究机会  15.高质量证据片段
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


def extract_summary_facts(
    markdown: str,
    *,
    zotero_key: str = "",
    title_hint: str = "",
    source: Optional[str] = None,
    summary_version: Optional[str] = None,
) -> list[dict]:
    """Extract searchable facts, metrics, datasets, baselines, and evidence lines."""
    facts: list[dict] = []
    sections = _split_sections(markdown)
    paper_title = _parse_basic_info(sections.get("1", ""), title_hint).get("title") or title_hint

    for section_no, section_text in sections.items():
        section_name = _section_label(section_no)
        for line in _content_lines(section_text):
            fact_type = _infer_fact_type(line, section_no)
            if not fact_type:
                continue
            value, unit = _extract_numeric_value(line)
            facts.append(
                {
                    "zotero_key": zotero_key,
                    "title": paper_title,
                    "fact_type": fact_type,
                    "label": _fact_label(line),
                    "value": value,
                    "unit": unit,
                    "context": line,
                    "evidence": _extract_evidence_phrase(line),
                    "confidence": _extract_confidence(line),
                    "source_section": section_name,
                    "source": source,
                    "summary_version": summary_version,
                }
            )

    # Fallback for shorter review cards that do not follow the numbered summary template.
    if not facts:
        for line in _content_lines(markdown):
            fact_type = _infer_fact_type(line, "")
            if not fact_type:
                continue
            value, unit = _extract_numeric_value(line)
            facts.append(
                {
                    "zotero_key": zotero_key,
                    "title": title_hint,
                    "fact_type": fact_type,
                    "label": _fact_label(line),
                    "value": value,
                    "unit": unit,
                    "context": line,
                    "evidence": _extract_evidence_phrase(line),
                    "confidence": _extract_confidence(line),
                    "source_section": "",
                    "source": source,
                    "summary_version": summary_version,
                }
            )
    return facts


def _split_sections(markdown: str) -> dict[str, str]:
    """Split markdown by numbered Markdown section headers."""
    pattern = re.compile(r"^#{1,3}\s+\d+\.\s+", re.M)
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


def _section_label(section_no: str) -> str:
    labels = {
        "1": "basic_info",
        "2": "one_line_summary",
        "3": "research_problem",
        "4": "method_overview",
        "5": "technical_route",
        "6": "innovations",
        "7": "technical_position",
        "8": "experiments",
        "9": "limitations",
        "10": "failure_modes",
        "11": "review_value",
        "12": "tags",
        "13": "embodied_ai_analysis",
        "14": "research_opportunities",
        "15": "evidence",
    }
    return labels.get(str(section_no), str(section_no))


def _content_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        line = re.sub(r"^[-*]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if line:
            lines.append(line)
    return lines


def _infer_fact_type(line: str, section_no: str) -> str:
    lowered = line.lower()
    if "[启发]" in line:
        return ""
    if section_no in {"13", "14"}:
        return ""
    if any(token in line for token in ["原文未包含", "未包含该类实验", "无实证数据集", "无量化指标", "无算法训练"]):
        return ""
    author_fact = "[原文]" in line or "【原文】" in line or "原文" in line
    if section_no == "15" or "证据" in line or "evidence" in lowered:
        return "evidence" if author_fact else ""
    if not author_fact and section_no in {"8", "12"}:
        return ""

    experiment_sections = {"8", "15"}
    concrete_sections = experiment_sections | {"12"}
    numeric = re.search(
        r"\d+(?:\.\d+)?\s*(?:%|percent|分|x|×|倍|fps|hz|ms|s|sec|seconds|hours|episodes|steps|trials|tasks|scenes|objects|environments|datasets)?",
        lowered,
    )
    metric_tokens = [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "auc",
        "success rate",
        "error",
        "latency",
        "throughput",
        "energy",
        "performance",
        "result",
        "score",
        "top-1",
        "top 1",
        "baseline",
        "improvement",
        "指标",
        "准确率",
        "精确率",
        "召回率",
        "成功率",
        "错误率",
        "延迟",
        "耗时",
        "能耗",
        "性能",
        "结果",
        "提升",
        "优于",
    ]

    dataset_tokens = ["dataset", "corpus", "数据集", "语料库"]
    dataset_label = re.search(r"(数据集|dataset|benchmark|基准)\s*(?:\*\*)?\s*[：:]", line, re.I)
    if dataset_label or (section_no in experiment_sections and any(token in lowered for token in dataset_tokens)):
        return "dataset"
    if any(token in lowered for token in ["baseline", "baselines", "对比方法", "基线"]) and (
        section_no in experiment_sections or re.search(r"(baseline|baselines|对比方法|基线)\s*[：:]", line, re.I)
    ):
        return "baseline"
    if any(token in lowered for token in ["code", "github", "open-source", "开源", "代码"]):
        return "code"
    if numeric and (section_no in experiment_sections or any(token in lowered for token in metric_tokens)):
        return "metric"

    platform_tokens = [
        "robot",
        "robotic",
        "机器人",
        "simulator",
        "simulation",
        "habitat",
        "hm3d",
        "mujoco",
        "isaac",
        "unity",
        "ros",
        "loihi",
        "gpu",
        "cpu",
        "edge device",
        "real-world",
        "real robot",
        "physical deployment",
        "仿真",
        "真机",
        "真实部署",
        "移动平台",
        "机械臂",
        "人形",
    ]
    if section_no in concrete_sections and any(token in lowered for token in platform_tokens):
        if re.search(r"(?:[：:]\s*(?:否|无|不涉及)|not used|not applicable|no real|no robot)", line, re.I):
            return ""
        return "platform"
    return ""


def _extract_numeric_value(line: str) -> tuple[Optional[float], Optional[str]]:
    match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|分|x|×|倍|fps|hz|ms|s|sec|seconds|hours|episodes|steps|trials|tasks|scenes|objects|environments|datasets)?", line, re.I)
    if not match:
        return None, None
    value = float(match.group("value"))
    unit = match.group("unit") or None
    return value, unit


def _extract_evidence_phrase(line: str) -> str:
    bracket = re.search(r"[（(]([^()（）]{4,160})[）)]\s*$", line)
    if bracket:
        return bracket.group(1).strip()
    quote = re.search(r"[“\"]([^”\"]{4,180})[”\"]", line)
    if quote:
        return quote.group(1).strip()
    return ""


def _extract_confidence(line: str) -> str:
    lowered = line.lower()
    if "needs_verification" in lowered or "需全文复核" in line:
        return "needs_verification"
    if "[原文]" in line or "原文" in line:
        return "high"
    if "[推断]" in line or "综述解读" in line:
        return "medium"
    if "[启发]" in line or "启发" in line:
        return "low"
    return ""


def _fact_label(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    cleaned = re.sub(r"[：:].*$", "", cleaned) if len(cleaned) > 80 else cleaned
    return cleaned[:180]


def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() or None
