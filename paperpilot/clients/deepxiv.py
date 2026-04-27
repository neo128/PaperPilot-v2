from __future__ import annotations

import os
from typing import Any, Optional

from deepxiv_sdk import Reader


class DeepXivClient:
    """Thin adapter over the official deepxiv-sdk Reader.

    We keep this wrapper so PaperPilot can depend on a stable local interface
    while retaining the flexibility to change the underlying integration later.
    """

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 30) -> None:
        token = token or os.environ.get("DEEPXIV_TOKEN")
        base_url = base_url or os.environ.get("DEEPXIV_BASE_URL")
        kwargs = {"timeout": timeout}
        if token is not None:
            kwargs["token"] = token
        if base_url is not None:
            kwargs["base_url"] = base_url
        self.reader = Reader(**kwargs)

    def search(self, query: str, limit: int = 10, search_mode: str = "hybrid") -> Any:
        return self.reader.search(query, size=limit, search_mode=search_mode)

    def trending(self, days: int = 7, limit: int = 20) -> Any:
        return self.reader.trending(days=days, limit=limit)

    def brief(self, arxiv_id: str) -> Any:
        return self.reader.brief(arxiv_id)

    def head(self, arxiv_id: str) -> Any:
        return self.reader.head(arxiv_id)

    def section(self, arxiv_id: str, section: str) -> Any:
        return self.reader.section(arxiv_id, section)

    def paper_json(self, arxiv_id: str) -> Any:
        return self.reader.json(arxiv_id)

    def preview(self, arxiv_id: str) -> Any:
        return self.reader.preview(arxiv_id)

    def markdown(self, arxiv_id: str) -> Any:
        return self.reader.markdown(arxiv_id)

    def semantic_scholar(self, sc_id: str) -> Any:
        return self.reader.semantic_scholar(sc_id)

    def websearch(self, query: str) -> Any:
        return self.reader.websearch(query)
