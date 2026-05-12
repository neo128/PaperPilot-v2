from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from openai import OpenAI


@dataclass
class AISettings:
    provider: str = "openai"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class AIClient:
    def __init__(self, settings: AISettings) -> None:
        self.settings = settings
        http_client = None
        proxy_values = [
            os.environ.get("ALL_PROXY"),
            os.environ.get("all_proxy"),
            os.environ.get("HTTPS_PROXY"),
            os.environ.get("https_proxy"),
            os.environ.get("HTTP_PROXY"),
            os.environ.get("http_proxy"),
        ]
        if any((value or "").lower().startswith("socks") for value in proxy_values):
            # httpx without socks extras rejects socks:// proxies at client init time.
            # Fall back to direct networking so DashScope/OpenAI-compatible calls can still run.
            http_client = httpx.Client(trust_env=False)
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, http_client=http_client)

    def chat(self, messages: list[dict[str, str]], model: Optional[str] = None, **kwargs: Any) -> str:
        messages = [
            {**message, "content": self.clean_text_for_json(message.get("content", ""))}
            for message in messages
        ]
        response = self.client.chat.completions.create(
            model=model or self.settings.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def clean_text_for_json(text: str) -> str:
        if not text:
            return ""
        return text.encode("utf-8", "ignore").decode("utf-8")

    @staticmethod
    def truncate_text(text: str, max_chars: int) -> str:
        text = AIClient.clean_text_for_json(text)
        if max_chars <= 0:
            return text or ""
        if not text or len(text) <= max_chars:
            return text or ""
        cut = text[:max_chars]
        breakpoints = ["\n", "。", "！", "？", "；", ".", "?", "!"]
        last = max((cut.rfind(bp) for bp in breakpoints), default=-1)
        if last >= int(max_chars * 0.6):
            cut = cut[: last + 1]
        return cut.strip() + "\n\n…（片段已截断，仅基于此生成）"

    def summarize_paper_excerpt(
        self,
        *,
        title: str,
        text: str,
        locale: str = "zh",
        max_chars: int = 4000,
        model: Optional[str] = None,
        mode: str = "general",
    ) -> str:
        excerpt = self.truncate_text(text or "", max_chars)
        if mode == "brief":
            if (locale or "").lower().startswith("zh"):
                system_msg = "你是一名严谨的论文预筛助手。"
                prompt = (
                    "请基于提供的摘要/片段生成**非 canonical 的摘要卡**，使用中文 Markdown。"
                    "不要冒充阅读全文；不要写成完整 AI 总结；所有事实只允许来自输入文本。\n\n"
                    "必须包含：来源限制、一句话摘要、关键方法/观点、可确认结果、缺失信息、是否值得获取全文精读。\n"
                    "如果输入只包含摘要或元数据，明确写“来源覆盖：abstract_only”。\n\n"
                    f"论文标题：{title}\n\n输入文本：\n{excerpt}"
                )
            else:
                system_msg = "You are a precise research-paper screening assistant."
                prompt = (
                    f"Summarize this paper briefly in Markdown, strictly based on the supplied text. "
                    "Return: source limitation, one-line summary, key method, evidence-backed result if present, missing information, and whether it deserves full reading.\n\n"
                    f"Title: {title}\n\nText:\n{excerpt}"
                )
            return self.chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                temperature=0.1,
                top_p=0.9,
            ).strip()
        if (locale or "").lower() == "en":
            out_limit = max(800, min(2000, max_chars // 2))
            system_msg = "You are a rigorous research-paper analysis assistant."
            prompt = (
                f"Create a canonical, paper-level summary in English Markdown, strictly based on the supplied text. "
                "Do not optimize it for a specific literature-review topic. Mark author-stated facts, inferences, "
                "and cross-domain inspiration separately. If a non-experimental paper contains no experiments, write "
                "\"the paper does not include experiments of this kind\" instead of claiming the excerpt is missing. "
                f"Keep it within about {out_limit} words.\\n\\n"
                f"Include: paper facts, problem, method, experiments if present, limitations, reusable value, and evidence snippets.\\n\\n"
                f"Title: {title}\\n\\nExcerpt:\\n{excerpt}"
            )
        else:
            system_msg = (
                "你是一名严谨的科研论文结构化分析助手，擅长从论文全文或摘要中提取可复用的事实、方法、证据与局限。"
            )
            template = _load_prompt_template("summary_general_zh.md")
            prompt = _render_prompt_template(template, title=title, excerpt=excerpt) if template else (
                "你的任务是生成**canonical AI summary（论文级通用总结）**："
                "只做论文事实层、方法层、证据层和可复用信息整理，不要默认围绕某个综述主题改写论文价值。\n\n"
                "## 全局要求\n"
                "1. 所有内容必须标注来源类型：[原文] / [推断] / [启发]\n"
                "2. [原文] 只用于论文明确陈述的事实、方法、实验、数值、结论；禁止把跨域适配、研究机会、类比解释标为 [原文]\n"
                "3. [推断] 用于基于原文证据的机制解释、局限判断、创新强度评估；必须能追溯到原文内容\n"
                "4. [启发] 只用于跨领域迁移、综述组织建议、未来研究想法、具身智能适配启发；跨域启发必须统一标 [启发]\n"
                "5. 禁止编造论文中未出现的信息；如果论文没有实验，写“原文未包含该类实验”；如果某类信息全文未出现，写“原文未包含该类信息”\n"
                "6. 只有输入文本明确包含“片段已截断”或抽取失败提示时，才允许写“原文片段未提供”；不要把非实验论文写成片段缺失\n"
                "7. 输出要适用于多次复用：独立论文阅读、Zotero 笔记、后续 review-specific 精读、综述矩阵和技术报告\n\n"
                "## 1. 论文基本信息\n"
                "标题、年份、作者/机构、研究领域、关键词、任务类型或论文类型（方法/系统/理论/综述/观点/基准/数据集等）。\n\n"
                "## 2. 一句话总结\n"
                "用1–2句话说明：解决什么问题、提出什么方法、核心结果。必须包含技术关键词。\n\n"
                "## 3. 研究问题\n"
                "核心问题是什么、为什么重要、现有方法的不足、关键挑战。\n\n"
                "## 4. 方法概述\n"
                "总体思路、输入/输出、核心模块、训练方式、推理流程。\n\n"
                "## 5. 技术流程拆解（Step-by-step）\n"
                "按 Step 1、Step 2... 描述，**每步的输入、处理、输出、解决问题必须以嵌套列表形式呈现**：\n\n"
                "### Step 1：标题\n"
                "- 输入：xxx\n"
                "- 处理：xxx\n"
                "- 输出：xxx\n"
                "- 解决问题：xxx\n\n"
                "## 6. 创新点评估（必须分级）\n"
                "对每个创新点输出：内容、【创新类型】（范式/方法/工程/分析）、【创新强度】（强/中/弱）、"
                "【是否已有类似工作】、【是否容易被替代】（高/中/低）。禁止只复述作者贡献。\n\n"
                "## 7. 技术坐标系定位\n"
                "分析该方法在以下维度的位置：black-box vs mechanistic、行为优化 vs 内部机制解释、"
                "表征学习 vs 控制学习、离线分析 vs 在线干预。说明推动了哪个方向。\n\n"
                "## 8. 实验与结果\n"
                "提取：数据集、任务、Baseline、指标、主要结果、消融实验、泛化实验、失败案例。"
                "如果是理论/观点/综述等非实验论文，明确写“原文未包含该类实验”，不要写“片段未提供”。\n\n"
                "## 9. 局限性\n"
                "区分作者承认的局限和你基于原文推断的局限。\n\n"
                "## 10. 失败模式（关键）\n"
                "总结：失败现象、触发条件、根本原因（机制层）、是否可检测、是否可修复。\n\n"
                "## 11. 通用复用价值\n"
                "说明该论文适合被哪些类型的综述、技术路线图、方法对比或研究设计复用。"
                "这里可以给综述组织建议，但必须标为 [启发]，不要冒充作者原文贡献。\n\n"
                "## 12. 分类标签（结构化）\n"
                "任务类型、方法类型、数据类型、是否使用真实机器人数据、是否使用仿真、"
                "是否使用语言、是否使用视觉、是否涉及动作序列、是否涉及世界模型、"
                "是否涉及 VLA、是否涉及记忆/语义表示、是否支持长程任务。\n\n"
                "## 13. 跨域适配与具身智能启发（可选）\n\n"
                "如果论文不是具身智能/机器人/主动探索论文，先写“非具身智能论文”。"
                "本节所有跨域类比、机器人适配、主动探索/世界模型启发必须标为 [启发]，不能标为 [原文]。\n"
                "### 13.1 任务建模启发：任务类别、复杂度、闭环控制或交互过程的可迁移启发。\n"
                "### 13.2 数据与平台启发：数据来源、平台、传感器/动作空间的可迁移启发；原文没有机器人平台时必须说明。\n"
                "### 13.3 感知-决策-控制启发：感知输入、中间表示、决策方式、控制输出或系统链路的可迁移启发。\n"
                "### 13.4 泛化与部署启发：跨任务/场景/平台、安全性、鲁棒性或部署方式的可迁移启发。\n\n"
                "## 14. 潜在研究机会\n"
                "提出3–5个研究方向，每个包括：背景问题、未解决空白、技术路线、预期价值、难点。\n\n"
                "## 15. 高质量证据片段（强约束）\n"
                "每条必须包含：原文完整句子（>=15词）、支撑的结论、为什么能支撑。禁止只摘关键词。\n\n"
                f"论文标题：{title}\n\n"
                f"用户提供的论文内容：\n{excerpt}"
            )
        return self.chat(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.15,
            top_p=0.9,
        ).strip()

    def summarize_text(self, text: str, model: Optional[str] = None) -> str:
        messages = [
            {"role": "system", "content": "You are a precise research paper assistant."},
            {"role": "user", "content": f"Please summarize the following paper content:\n\n{text}"},
        ]
        return self.chat(messages, model=model)

    def read_paper_structured(
        self,
        *,
        topic: str,
        title: str,
        metadata: dict[str, Any],
        context: str,
        locale: str = "zh",
        max_chars: int = 12000,
        model: Optional[str] = None,
    ) -> str:
        excerpt = self.truncate_text(context, max_chars)
        if (locale or "").lower().startswith("en"):
            system_msg = "You are a rigorous academic literature-review assistant."
            prompt = (
                f"Deep-read this paper for a literature review on: {topic}.\n"
                "Use Markdown. Treat the supplied context as a bounded evidence packet, not as license to infer missing sections. "
                "Do not invent missing facts; mark only truly missing or unsupported fields as needs_verification.\n\n"
                "Evidence rules:\n"
                "- Every concrete claim about datasets, baselines, metrics, results, code, robots, or deployment must cite a short source phrase in parentheses.\n"
                "- Separate author-stated facts from your review-topic interpretation.\n"
                "- If a paper is only indirectly related to the review topic, say so explicitly and do not force-fit it as a world-model or active-exploration paper.\n"
                "- Do not claim that the PDF/text is truncated unless the context explicitly says extraction failed or a required section is absent.\n"
                "- Use needs_verification only for specific missing facts, not as a generic disclaimer.\n\n"
                "Include: problem, method, experiments, main findings, limitations, relation to the review questions, "
                "engineering reusability, and evidence snippets.\n\n"
                f"Title: {title}\nMetadata: {metadata}\n\nContext:\n{excerpt}"
            )
        else:
            system_msg = "你是一名严谨的系统性文献综述助手。"
            prompt = (
                f'请围绕综述主题"{topic}"精读这篇论文，并输出 Markdown。'
                "请把输入上下文视为有边界的证据包，不得把未提供的信息补写成事实；只有具体字段缺失或证据不足时才标注 needs_verification。\n\n"
                "## 证据约束\n"
                "- 关于数据集、baseline、指标、数值结果、代码、机器人平台、真实部署、消融实验的每个具体判断，都必须在句末括号中给出短证据短语。\n"
                "- 明确区分【作者原文事实】和【综述主题解释】；解释性内容必须标注为“综述解读”。\n"
                "- 如果论文与综述主题只是间接相关，必须写“间接相关/弱相关”，不要强行称其为主动探索或世界模型论文。\n"
                "- 只有上下文明确显示抽取失败、相关章节缺失、或证据包不含该信息时，才说“需全文复核”；不要泛泛写“PDF截断”。\n"
                "- needs_verification 必须绑定到具体缺失项，例如“代码开源状态 needs_verification”，不要作为整段免责声明。\n"
                "- 对非具身智能论文，先说明领域不匹配，再给跨域启发；不得把跨域启发写成作者贡献。\n\n"
                "请包含：研究问题、方法、实验、主要发现、局限、与综述问题的关系、工程复用性、证据摘录。\n\n"
                f"论文标题：{title}\n元数据：{metadata}\n\n上下文：\n{excerpt}"
            )
        return self.chat(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.1,
            top_p=0.9,
        ).strip()

    def code_paper_for_review(
        self,
        *,
        topic: str,
        title: str,
        metadata: dict[str, Any],
        context: str,
        reading_note: str,
        locale: str = "zh",
        max_chars: int = 12000,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        excerpt = self.truncate_text(context, max_chars)
        prompt = (
            f"Literature review topic: {topic}\n"
            f"Paper title: {title}\n"
            f"Metadata: {metadata}\n\n"
            f"Context:\n{excerpt}\n\n"
            f"Reading note:\n{reading_note[:4000]}\n\n"
            "Return strict JSON only with these keys: "
            "priority_score, tier, research_direction, task_type, method_type, model_or_system_type, data_type, "
            "benchmark_or_environment, real_world_or_simulation, open_source_status, core_contribution, main_limitation, "
            "evidence_strength, engineering_reusability, relation_to_target_topic, coding_confidence, coding_note. "
            "Use tier values: A 核心池, B 主体池, C 备选池, D 存档池. "
            "priority_score must be an integer from 0 to 100. "
            "coding_confidence must be one of high, medium, low, needs_verification. "
            "A paper should be A only if it directly studies active exploration with world models in embodied AI; "
            "use B for foundational world-model infrastructure, C for indirect baselines/surveys, and D for off-topic papers. "
            "Do not upgrade an indirect paper by speculative relation. Mark uncertain fields as needs_verification."
        )
        text = self.chat(
            [
                {"role": "system", "content": "You output strict JSON for systematic literature-review coding."},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.05,
            top_p=0.9,
        ).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                return {}
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
            return data if isinstance(data, dict) else {}

    def draft_literature_review(
        self,
        *,
        topic: str,
        coded_rows: list[dict[str, Any]],
        reading_notes: list[str],
        locale: str = "zh",
        model: Optional[str] = None,
    ) -> str:
        lang = "English" if (locale or "").lower().startswith("en") else "中文"
        prompt = (
            f'请用{lang}撰写关于"{topic}"的系统性文献综述初稿。'
            "必须基于编码表和精读卡片，不确定处标注 needs_verification。"
            "不要虚构引用；引用使用 citation_key 或 paper_id 占位。\n\n"
            "章节包括：摘要、检索与筛选方法、分类框架、主题主线、横向比较、关键挑战、未来方向、结论、参考文献占位。\n\n"
            f"编码表：\n{json.dumps(coded_rows[:80], ensure_ascii=False, indent=2)}\n\n"
            f"精读卡片摘录：\n\n" + "\n\n".join(reading_notes[:30])
        )
        return self.chat(
            [
                {"role": "system", "content": "You are a rigorous academic literature-review writing assistant."},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.15,
            top_p=0.9,
        ).strip()


def _load_prompt_template(name: str) -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _render_prompt_template(template: str, *, title: str, excerpt: str) -> str:
    return template.replace("{{title}}", title).replace("{{excerpt}}", excerpt)
