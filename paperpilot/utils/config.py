from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .env import load_dotenv_if_present, optional_env, require_env


@dataclass
class ZoteroSettings:
    user_id: str
    api_key: str
    storage_dir: Optional[Path] = None


@dataclass
class NotionSettings:
    api_key: str
    database_id: str


@dataclass
class AISettings:
    provider: str = "openai"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


@dataclass
class AppSettings:
    zotero: ZoteroSettings
    notion: Optional[NotionSettings]
    ai: AISettings


def load_app_settings(env_file: str | Path = ".env") -> AppSettings:
    load_dotenv_if_present(env_file)

    zotero = ZoteroSettings(
        user_id=require_env("ZOTERO_USER_ID"),
        api_key=require_env("ZOTERO_API_KEY"),
        storage_dir=Path(optional_env("ZOTERO_STORAGE_DIR")) if optional_env("ZOTERO_STORAGE_DIR") else None,
    )

    notion = None
    notion_key = optional_env("NOTION_API_KEY")
    notion_db = optional_env("NOTION_DATABASE_ID")
    if notion_key and notion_db:
        notion = NotionSettings(api_key=notion_key, database_id=notion_db)

    ai = AISettings(
        provider=optional_env("AI_PROVIDER", "openai") or "openai",
        base_url=optional_env("AI_BASE_URL"),
        api_key=optional_env("AI_API_KEY"),
        model=optional_env("AI_MODEL"),
    )

    return AppSettings(zotero=zotero, notion=notion, ai=ai)
