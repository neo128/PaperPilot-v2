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
        out_limit = max(800, min(2000, max_chars // 2))
        if (locale or "").lower() == "en":
            system_msg = "You are an AI research assistant specialized in AI/AGI/robotics paper analysis."
            prompt = (
                f"Please summarize the following paper excerpt in English Markdown, strictly based on the excerpt. "
                f"Keep it within about {out_limit} words.\\n\\n"
                f"Include: abstract, problem, method, experiments, limitations, and evidence snippets.\\n\\n"
                f"Title: {title}\\n\\nExcerpt:\\n{excerpt}"
            )
        else:
            system_msg = "你是一名专注于 AI/AGI/具身智能/机器人领域的科研解读助手。"
            prompt = (
                f"请严格基于下面论文片段，用中文 Markdown 生成摘要，不要编造。整体控制在 {out_limit} 字左右。\\n\\n"
                f"请包含：摘要、研究背景与问题、方法与关键技术、实验与结论、局限性与未来工作、证据摘录。\\n\\n"
                f"论文标题：{title}\\n\\n正文片段：\\n{excerpt}"
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
                f"请围绕综述主题“{topic}”精读这篇论文，并输出 Markdown。"
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
            f"请用{lang}撰写关于“{topic}”的系统性文献综述初稿。"
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
