from __future__ import annotations

import os
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
