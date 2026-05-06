from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
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
        response = self.client.chat.completions.create(
            model=model or self.settings.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def truncate_text(text: str, max_chars: int) -> str:
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
    ) -> str:
        excerpt = self.truncate_text(text or "", max_chars)
        if (locale or "").lower() == "en":
            out_limit = max(800, min(2000, max_chars // 2))
            system_msg = "You are an AI research assistant specialized in AI/AGI/robotics paper analysis."
            prompt = (
                f"Please summarize the following paper excerpt in English Markdown, strictly based on the excerpt. "
                f"Keep it within about {out_limit} words.\\n\\n"
                f"Include: abstract, problem, method, experiments, limitations, and evidence snippets.\\n\\n"
                f"Title: {title}\\n\\nExcerpt:\\n{excerpt}"
            )
        else:
            system_msg = (
                "你是一名具身智能（Embodied AI）领域的科研论文分析助手，"
                "擅长机器人学习、VLA、世界模型、多模态学习、强化学习、机器人控制与系统架构分析。"
            )
            prompt = (
                "你的任务不是简单摘要论文，而是进行**结构化科研分析 + 技术路线拆解 + 创新点评估 + 具身智能适配分析**。\n\n"
                "## 全局要求\n"
                "1. 所有内容必须标注来源类型：[原文] / [推断] / [启发]\n"
                "2. 禁止编造论文中未出现的信息\n"
                '3. 如果信息缺失，写"原文片段未提供"\n'
                "4. 不允许只做摘要，必须进行机制分析\n"
                "5. 输出要适用于：综述论文 / 技术报告 / 研究设计\n\n"
                "## 1. 论文基本信息\n"
                "标题、年份、作者/机构、研究领域、关键词、任务类型（操控/导航/多任务/长程任务/人机交互等）。\n\n"
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
                "提取：数据集、任务、Baseline、指标、主要结果、消融实验、泛化实验、失败案例。\n\n"
                "## 9. 局限性\n"
                "区分作者承认的局限和你基于原文推断的局限。\n\n"
                "## 10. 失败模式（关键）\n"
                "总结：失败现象、触发条件、根本原因（机制层）、是否可检测、是否可修复。\n\n"
                "## 11. 综述价值\n"
                "适合放入综述哪个章节、可对比的论文类型、所属技术路线。\n\n"
                "## 12. 分类标签（结构化）\n"
                "任务类型、方法类型、数据类型、是否使用真实机器人数据、是否使用仿真、"
                "是否使用语言、是否使用视觉、是否涉及动作序列、是否涉及世界模型、"
                "是否涉及 VLA、是否涉及记忆/语义表示、是否支持长程任务。\n\n"
                "## 13. 具身智能专用分析（重点）\n\n"
                "### 13.1 机器人任务建模：任务类别、任务复杂度（单步/多阶段/长程）、是否涉及闭环控制。\n"
                "### 13.2 数据与本体：数据来源（真机/仿真/视频/遥操作）、机器人类型（单臂/双臂/人形/移动平台等）、动作空间（关节/末端/token/语言）。\n"
                "### 13.3 感知-决策-控制链路：感知输入（视觉/深度/proprioception等）、中间表示（latent/world model/memory等）、决策方式（policy/planner/VLA等）、控制输出（动作/轨迹/技能）。\n"
                "### 13.4 泛化与部署能力：是否跨任务/场景/物体/机器人本体、是否支持真实机器人部署、是否具备安全性或鲁棒性设计。\n\n"
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
                "Use Markdown. Do not invent missing facts; mark uncertain fields as needs_verification.\n\n"
                "Include: problem, method, experiments, main findings, limitations, relation to the review questions, "
                "engineering reusability, and evidence snippets.\n\n"
                f"Title: {title}\nMetadata: {metadata}\n\nContext:\n{excerpt}"
            )
        else:
            system_msg = "你是一名严谨的系统性文献综述助手。"
            prompt = (
                f'请围绕综述主题"{topic}"精读这篇论文，并输出 Markdown。'
                "不得编造缺失事实；不确定处标注 needs_verification。\n\n"
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
            "Use tier values: A 核心池, B 主体池, C 备选池, D 存档池. Mark uncertain fields as needs_verification."
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
