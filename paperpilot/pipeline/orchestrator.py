from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from paperpilot.clients.ai import AIClient
from paperpilot.clients.arxiv import ArxivClient
from paperpilot.clients.deepxiv import DeepXivClient
from paperpilot.clients.notion import NotionClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.models.results import PipelineResult
from paperpilot.pipeline.config import PipelineConfig
from paperpilot.services.notion_sync_service import NotionSyncOptions, NotionSyncService
from paperpilot.services.summary_service import SummaryOptions, SummaryService
from paperpilot.services.watch_service import WatchOptions, WatchService
from paperpilot.storage.sqlite_state import SQLiteStateStore
from paperpilot.utils.config import AISettings, load_app_settings


class PipelineOrchestrator:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.settings = load_app_settings()
        storage_dir = config.storage_dir or self.settings.zotero.storage_dir or Path.home() / "Zotero" / "storage"
        self.zotero = ZoteroClient(self.settings.zotero.user_id, self.settings.zotero.api_key)
        self.ai = AIClient(
            AISettings(
                provider=self.settings.ai.provider,
                base_url=self.settings.ai.base_url,
                api_key=self.settings.ai.api_key,
                model=self.settings.ai.model,
            )
        )
        self.arxiv = ArxivClient()

        # DeepXiv: try to init, but don't fail if unavailable — arXiv is the fallback
        self.deepxiv: DeepXivClient | None = None
        if config.summary.use_deepxiv or config.watch.enabled:
            try:
                self.deepxiv = DeepXivClient()
            except Exception:
                pass  # arXiv fallback will be used

        self.watch_service = WatchService(
            zotero=self.zotero,
            deepxiv=self.deepxiv,
            arxiv=self.arxiv,
        )
        self.summary_service = SummaryService(self.zotero, self.ai, storage_dir, deepxiv=self.deepxiv)
        self.state_store = SQLiteStateStore(config.state_db_path)
        self.notion_service = None
        if self.settings.notion:
            notion = NotionClient(self.settings.notion.api_key, self.settings.notion.database_id)
            self.notion_service = NotionSyncService(notion)

    def close(self) -> None:
        if getattr(self, "state_store", None) is not None:
            self.state_store.close()

    def __enter__(self) -> "PipelineOrchestrator":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _resolve_collection_key(self, key: str | None, name: str | None) -> str | None:
        if key:
            return key
        if name:
            return self.zotero.resolve_collection_key(name)
        return None

    def _filter_incremental_items(self, items, stage_name: str, incremental: bool, retry_failed: bool):
        if not incremental:
            return items
        filtered = []
        for entry in items:
            data = entry.get('data', entry)
            item_key = data.get('key')
            if not item_key:
                filtered.append(entry)
                continue
            status = self.state_store.get_latest_item_status(item_key, stage_name)
            if status == 'success':
                continue
            if status == 'failed' and not retry_failed:
                continue
            filtered.append(entry)
        return filtered

    def _collect_items(self, collection: str | None, tag: str | None, limit: int, recursive: bool = False):
        if not collection:
            return list(self.zotero.iter_items(collection=None, tag=tag, limit=limit, top_only=True))
        if not recursive:
            return list(self.zotero.iter_items(collection=collection, tag=tag, limit=limit, top_only=True))
        collection_keys = []
        stack = [collection]
        seen = set()
        while stack:
            key = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            collection_keys.append(key)
            for child in self.zotero.list_child_collections(key):
                if child.get("key"):
                    stack.append(child["key"])
        items = []
        for key in collection_keys:
            items.extend(list(self.zotero.iter_items(collection=key, tag=tag, limit=limit, top_only=True)))
        return items

    def run(self) -> PipelineResult:
        result = PipelineResult()
        run_id = self.state_store.create_run(asdict(self.config))
        watch_items = []
        if self.config.watch.enabled:
            watch_result = self.watch_service.search_and_import(
                WatchOptions(
                    query=self.config.watch.query,
                    limit=self.config.watch.limit,
                    create_collections=self.config.watch.create_collections,
                    collection_name=self.config.watch.collection_name,
                    dry_run=self.config.watch.dry_run,
                )
            )
            result.add_stage(watch_result)
            self.state_store.record_stage(run_id, watch_result)

        summary_items = []
        if self.config.summary.enabled:
            collection_key = self._resolve_collection_key(self.config.summary.collection, self.config.summary.collection_name)
            summary_items = self._collect_items(collection_key, self.config.summary.tag, self.config.summary.limit)
            summary_items = self._filter_incremental_items(
                summary_items,
                'summary',
                self.config.summary.incremental,
                self.config.summary.retry_failed,
            )
            summary_result = self.summary_service.summarize_items(
                summary_items,
                SummaryOptions(
                    max_pages=self.config.summary.max_pages,
                    max_chars=self.config.summary.max_chars,
                    note_tag=self.config.summary.note_tag,
                    force=self.config.summary.force,
                    locale=self.config.summary.locale,
                    use_deepxiv=self.config.summary.use_deepxiv,
                ),
                insert_note=self.config.summary.insert_note,
            )
            result.add_stage(summary_result)
            self.state_store.record_stage(run_id, summary_result)
            stage_status = 'failed' if summary_result.failed else 'success'
            for entry in summary_items:
                data = entry.get('data', entry)
                self.state_store.record_item_state(run_id, 'summary', data.get('key'), data.get('title'), stage_status)

        if self.config.notion.enabled:
            if not self.notion_service:
                raise RuntimeError("Notion settings not configured")
            collection_key = self._resolve_collection_key(self.config.notion.collection, self.config.notion.collection_name)
            notion_items = self._collect_items(
                collection_key,
                self.config.notion.tag,
                self.config.notion.limit,
                recursive=self.config.notion.recursive,
            )
            notion_items = self._filter_incremental_items(
                notion_items,
                'notion-sync',
                self.config.notion.incremental,
                self.config.notion.retry_failed,
            )
            notion_result = self.notion_service.sync_items(
                notion_items,
                NotionSyncOptions(
                    limit=self.config.notion.limit,
                    dry_run=self.config.notion.dry_run,
                    skip_untitled=self.config.notion.skip_untitled,
                    recursive=self.config.notion.recursive,
                ),
            )
            result.add_stage(notion_result)
            self.state_store.record_stage(run_id, notion_result)
            stage_status = 'failed' if notion_result.failed else 'success'
            for entry in notion_items:
                data = entry.get('data', entry)
                self.state_store.record_item_state(run_id, 'notion-sync', data.get('key'), data.get('title'), stage_status)

        self.state_store.complete_run(run_id, result)
        return result
