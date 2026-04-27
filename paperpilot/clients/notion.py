from __future__ import annotations

import time
from typing import Any, Dict, Optional

from paperpilot.utils.http import create_session, request_with_retry


class NotionClient:
    def __init__(self, api_key: str, database_id: str, timeout: int = 30) -> None:
        self.database_id = database_id
        self.timeout = timeout
        self.session = create_session(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
                "User-Agent": "PaperPilot-v2/0.1",
            }
        )

    def get_database(self) -> Dict[str, Any]:
        url = f"https://api.notion.com/v1/databases/{self.database_id}"
        return request_with_retry(self.session, "get", url, timeout=self.timeout).json()

    def query_by_title(self, title_prop: str, title: str) -> Optional[str]:
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {"filter": {"property": title_prop, "title": {"equals": title}}}
        result = request_with_retry(self.session, "post", url, json=payload, timeout=self.timeout).json()
        if result.get("results"):
            return result["results"][0]["id"]
        return None

    def query_by_text(self, prop_name: str, text: str) -> Optional[str]:
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {"filter": {"property": prop_name, "rich_text": {"equals": text}}}
        result = request_with_retry(self.session, "post", url, json=payload, timeout=self.timeout).json()
        if result.get("results"):
            return result["results"][0]["id"]
        return None

    def create_page(self, props: Dict[str, Any]) -> str:
        url = "https://api.notion.com/v1/pages"
        payload = {"parent": {"database_id": self.database_id}, "properties": props}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code == 429:
            time.sleep(1.0)
            resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["id"]

    def update_page(self, page_id: str, props: Dict[str, Any]) -> None:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"properties": props}
        resp = self.session.patch(url, json=payload, timeout=self.timeout)
        if resp.status_code == 429:
            time.sleep(1.0)
            resp = self.session.patch(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
