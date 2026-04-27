from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from paperpilot.clients.arxiv import ArxivClient
from paperpilot.clients.deepxiv import DeepXivClient
from paperpilot.clients.journals import search_journals
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.models.results import StageResult

logger = logging.getLogger(__name__)


@dataclass
class WatchOptions:
    query: str
    limit: int = 10
    create_collections: bool = False
    collection_name: Optional[str] = None
    dry_run: bool = False
    journals: bool = False  # also search curated journals/conferences


def _extract_authors(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name") or item.get("author") or item.get("full_name")
                if name:
                    out.append(str(name))
            elif item:
                out.append(str(item))
        return out
    return []


def build_zotero_item(candidate: Dict[str, Any], collection_key: Optional[str] = None) -> Dict[str, Any]:
    title = candidate.get("title") or "Untitled"
    authors = _extract_authors(candidate.get("authors"))
    creators = []
    for name in authors:
        creators.append({"creatorType": "author", "name": name})
    arxiv_id = candidate.get("arxiv_id") or candidate.get("archiveLocation") or ""
    url = candidate.get("src_url") or candidate.get("url")
    if not url and arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    data = {
        "itemType": "journalArticle",
        "title": title,
        "creators": creators,
        "abstractNote": candidate.get("abstract") or candidate.get("tldr") or "",
        "url": url,
        "date": candidate.get("publish_at") or candidate.get("published") or candidate.get("date") or "",
        "archive": "arXiv" if arxiv_id else "",
        "archiveLocation": arxiv_id,
        "tags": [{"tag": "PaperPilot-v2"}],
    }
    if collection_key:
        data["collections"] = [collection_key]
    return data


class WatchService:
    def __init__(
        self,
        zotero: ZoteroClient,
        deepxiv: Optional[DeepXivClient] = None,
        arxiv: Optional[ArxivClient] = None,
    ) -> None:
        self.zotero = zotero
        self.deepxiv = deepxiv
        self.arxiv = arxiv or ArxivClient()

    def search_and_import(self, options: WatchOptions) -> StageResult:
        """Search papers using DeepXiv (preferred) with arXiv fallback.

        Strategy:
        1. Try DeepXiv search first.
        2. If DeepXiv fails (server error, auth error, empty results), fall back to arXiv API.
        3. Deduplicate results (arXiv IDs).
        4. Import into Zotero.
        """
        result = StageResult(stage="watch")
        candidates: List[Dict[str, Any]] = []
        source = "unknown"

        # Step 1: Try DeepXiv
        if self.deepxiv:
            try:
                response = self.deepxiv.search(options.query, limit=options.limit)
                if isinstance(response, dict):
                    items = response.get("items") or response.get("results") or []
                else:
                    items = response
                if items:
                    candidates = list(items)
                    source = "deepxiv"
                    logger.info("watch: DeepXiv returned %d results", len(candidates))
                else:
                    logger.info("watch: DeepXiv returned empty results, falling back to arXiv")
            except Exception as exc:
                logger.warning("watch: DeepXiv failed (%s), falling back to arXiv", exc)

        # Step 2: Fallback to arXiv if DeepXiv produced nothing
        if not candidates:
            try:
                arxiv_results = self.arxiv.search_recent(options.query, limit=options.limit)
                candidates = arxiv_results
                source = "arxiv"
                logger.info("watch: arXiv returned %d results", len(candidates))
            except Exception as exc:
                logger.error("watch: arXiv fallback also failed (%s)", exc)

        # Step 2b: Also search journals/conferences when --journals is set
        if options.journals:
            try:
                journal_results = search_journals(options.query, limit=options.limit)
                if journal_results:
                    logger.info("watch: journals returned %d results", len(journal_results))
                    candidates.extend(journal_results)
                    if source == "unknown" or source == "none":
                        source = "journals"
                    else:
                        source = f"{source}+journals"
            except Exception as exc:
                logger.warning("watch: journal search failed (%s), continuing", exc)

        if not candidates:
            result.artifacts["source"] = "none"
            result.artifacts["error"] = "Both DeepXiv and arXiv returned no results"
            return result

        # Step 3: Deduplicate by arXiv ID + DOI + title
        seen_ids: set[str] = set()
        seen_titles: set[str] = set()
        unique: List[Dict[str, Any]] = []
        for c in candidates:
            aid = c.get("arxiv_id") or c.get("archiveLocation") or ""
            doi = (c.get("doi") or "").lower()
            title = (c.get("title") or "").lower().strip()

            doi_key = f"doi:{doi}" if doi else None
            title_key = f"t:{title}" if title else None

            is_dup = False
            if aid and aid in seen_ids:
                is_dup = True
            if doi_key and doi_key in seen_ids:
                is_dup = True
            if title_key and title_key in seen_titles:
                is_dup = True

            if is_dup:
                continue

            if aid:
                seen_ids.add(aid)
            if doi_key:
                seen_ids.add(doi_key)
            if title_key:
                seen_titles.add(title_key)
            unique.append(c)
        candidates = unique

        collection_key = None
        if options.collection_name and options.create_collections and not options.dry_run:
            collection_key = self.zotero.create_collection_if_missing(options.collection_name)

        payloads: List[Dict[str, Any]] = []
        for candidate in candidates[: options.limit]:
            result.processed += 1
            payloads.append(build_zotero_item(candidate, collection_key=collection_key))

        if options.dry_run:
            result.created = len(payloads)
            result.artifacts["dry_run_count"] = len(payloads)
            result.artifacts["source"] = source
            return result

        created_keys = self.zotero.create_items(payloads)
        result.created = len(created_keys)
        result.artifacts["created_keys"] = created_keys
        result.artifacts["source"] = source
        return result
