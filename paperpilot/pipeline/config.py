from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class WatchStageConfig:
    enabled: bool = False
    query: str = "agent memory"
    limit: int = 10
    create_collections: bool = False
    collection_name: Optional[str] = None
    dry_run: bool = False


@dataclass
class SummaryStageConfig:
    enabled: bool = False
    collection: Optional[str] = None
    collection_name: Optional[str] = None
    tag: Optional[str] = None
    limit: int = 20
    max_pages: int = 12
    max_chars: int = 12000
    note_tag: str = "AI总结"
    force: bool = False
    locale: str = "zh"
    use_deepxiv: bool = False
    insert_note: bool = True
    incremental: bool = True
    retry_failed: bool = True


@dataclass
class NotionStageConfig:
    enabled: bool = True
    collection: Optional[str] = None
    collection_name: Optional[str] = None
    tag: Optional[str] = None
    limit: int = 200
    dry_run: bool = False
    skip_untitled: bool = True
    recursive: bool = False
    incremental: bool = True
    retry_failed: bool = True


@dataclass
class PipelineConfig:
    storage_dir: Optional[Path] = None
    state_db_path: Path = Path('.paperpilot/state.sqlite3')
    watch: WatchStageConfig = field(default_factory=WatchStageConfig)
    summary: SummaryStageConfig = field(default_factory=SummaryStageConfig)
    notion: NotionStageConfig = field(default_factory=NotionStageConfig)
