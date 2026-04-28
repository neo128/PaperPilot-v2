from __future__ import annotations

import html
import logging
import re
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
    prompt: Optional[str] = None
    expand_queries: bool = False
    reuse_existing: bool = True


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


def _normalize_title(title: Any) -> str:
    return " ".join(str(title or "").lower().split())


def _clean_zotero_field(value: Any, max_chars: int) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    suffix = " ... [truncated]"
    return text[: max(0, max_chars - len(suffix))].rstrip() + suffix


def build_literature_search_queries(topic: str, prompt: Optional[str] = None) -> List[str]:
    """Build Phase-1 style query groups from a review topic or user prompt."""
    core = topic.strip()
    queries = [
        core,
        f"{core} benchmark",
        f"{core} dataset",
        f"{core} survey",
        f"{core} method",
        f"{core} system",
    ]
    if prompt and prompt.strip() and prompt.strip() != core:
        prompt_text = prompt.strip()
        queries.extend([prompt_text, f"{core} {prompt_text}"])

    seen: set[str] = set()
    out: List[str] = []
    for query in queries:
        normalized = " ".join(query.split())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _candidate_key(candidate: Dict[str, Any]) -> tuple[str, str]:
    doi = str(candidate.get("doi") or candidate.get("DOI") or "").strip().lower()
    if doi:
        return ("doi", doi)
    arxiv_id = str(candidate.get("arxiv_id") or candidate.get("archiveLocation") or "").strip().lower()
    if arxiv_id:
        return ("arxiv", arxiv_id)
    return ("title", _normalize_title(candidate.get("title")))


def deduplicate_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: List[Dict[str, Any]] = []
    for candidate in candidates:
        key = _candidate_key(candidate)
        if not key[1] or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def build_zotero_item(candidate: Dict[str, Any], collection_key: Optional[str] = None) -> Dict[str, Any]:
    title = _clean_zotero_field(candidate.get("title") or "Untitled", 1000) or "Untitled"
    authors = _extract_authors(candidate.get("authors"))[:20]
    creators = []
    for name in authors:
        clean_name = _clean_zotero_field(name, 300)
        if clean_name:
            creators.append({"creatorType": "author", "name": clean_name})
    arxiv_id = _clean_zotero_field(candidate.get("arxiv_id") or candidate.get("archiveLocation") or "", 120)
    url = _clean_zotero_field(candidate.get("src_url") or candidate.get("url") or "", 2000)
    if not url and arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    data = {
        "itemType": "journalArticle",
        "title": title,
        "creators": creators,
        "abstractNote": _clean_zotero_field(candidate.get("abstract") or candidate.get("tldr") or "", 8000),
        "url": url,
        "date": _clean_zotero_field(candidate.get("publish_at") or candidate.get("published") or candidate.get("date") or "", 100),
        "DOI": _clean_zotero_field(candidate.get("doi") or candidate.get("DOI") or "", 500),
        "publicationTitle": _clean_zotero_field(candidate.get("venue") or "", 1000),
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

    def _search_candidates_for_query(self, query: str, limit: int) -> tuple[List[Dict[str, Any]], str]:
        candidates: List[Dict[str, Any]] = []
        source = "unknown"

        if self.deepxiv:
            try:
                response = self.deepxiv.search(query, limit=limit)
                if isinstance(response, dict):
                    items = response.get("items") or response.get("results") or []
                else:
                    items = response
                if items:
                    candidates = list(items)
                    source = "deepxiv"
                    logger.info("watch: DeepXiv returned %d results for query=%s", len(candidates), query)
                else:
                    logger.info("watch: DeepXiv returned empty results for query=%s, falling back to arXiv", query)
            except Exception as exc:
                logger.warning("watch: DeepXiv failed for query=%s (%s), falling back to arXiv", query, exc)

        if not candidates:
            try:
                candidates = self.arxiv.search_recent(query, limit=limit)
                source = "arxiv"
                logger.info("watch: arXiv returned %d results for query=%s", len(candidates), query)
            except Exception as exc:
                logger.error("watch: arXiv fallback also failed for query=%s (%s)", query, exc)
                source = "none"

        return candidates, source

    def _find_existing_item(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        finder = getattr(self.zotero, "find_existing_item", None)
        if not callable(finder):
            return None
        try:
            existing = finder(candidate)
        except Exception as exc:
            logger.warning("watch: Zotero duplicate lookup failed for title=%s (%s)", candidate.get("title"), exc)
            return None
        return existing if isinstance(existing, dict) else None

    def _add_existing_to_collection(self, item_key: str, collection_key: Optional[str]) -> bool:
        if not item_key or not collection_key:
            return False
        add_to_collection = getattr(self.zotero, "add_item_to_collection", None)
        if not callable(add_to_collection):
            return False
        try:
            return bool(add_to_collection(item_key, collection_key))
        except Exception as exc:
            logger.warning("watch: failed to add existing Zotero item %s to collection %s (%s)", item_key, collection_key, exc)
            return False

    def search_and_import(self, options: WatchOptions) -> StageResult:
        """Search papers using DeepXiv (preferred) with arXiv fallback.

        Strategy:
        1. Build one or more Phase-1 search queries from the topic/prompt.
        2. Try DeepXiv search first, then fall back to arXiv.
        3. Optionally add curated journal/conference results.
        4. Deduplicate results by DOI, arXiv id, and title.
        5. Reuse existing Zotero items when possible; create only missing items.
        """
        result = StageResult(stage="watch")
        candidates: List[Dict[str, Any]] = []
        sources: List[str] = []
        queries = (
            build_literature_search_queries(options.query, options.prompt)
            if options.expand_queries
            else [options.query.strip()]
        )

        for query in queries:
            query_candidates, source = self._search_candidates_for_query(query, options.limit)
            candidates.extend(query_candidates)
            if query_candidates and source != "none":
                sources.append(source)

        if options.journals:
            try:
                for query in queries:
                    journal_results = search_journals(query, limit=options.limit)
                    if journal_results:
                        logger.info("watch: journals returned %d results for query=%s", len(journal_results), query)
                        candidates.extend(journal_results)
                        sources.append("journals")
            except Exception as exc:
                logger.warning("watch: journal search failed (%s), continuing", exc)

        if not candidates:
            result.artifacts["source"] = "none"
            result.artifacts["error"] = "Both DeepXiv and arXiv returned no results"
            result.artifacts["queries"] = queries
            return result

        source = "+".join(dict.fromkeys(sources)) if sources else "unknown"
        candidates = deduplicate_candidates(candidates)[: options.limit]

        collection_key = None
        if options.collection_name and options.create_collections and not options.dry_run:
            collection_key = self.zotero.create_collection_if_missing(options.collection_name)

        payloads: List[Dict[str, Any]] = []
        existing_keys: List[str] = []
        managed_keys: List[str] = []
        for candidate in candidates[: options.limit]:
            result.processed += 1

            existing = self._find_existing_item(candidate) if options.reuse_existing else None
            if existing:
                existing_data = existing.get("data", existing)
                existing_key = existing.get("key") or existing_data.get("key")
                if existing_key:
                    existing_keys.append(existing_key)
                    managed_keys.append(existing_key)
                    if not options.dry_run and self._add_existing_to_collection(existing_key, collection_key):
                        result.updated += 1
                    result.skipped += 1
                    continue

            payloads.append(build_zotero_item(candidate, collection_key=collection_key))

        if options.dry_run:
            result.created = len(payloads)
            result.artifacts["dry_run_count"] = len(payloads)
            result.artifacts["source"] = source
            result.artifacts["queries"] = queries
            result.artifacts["existing_keys"] = existing_keys
            result.artifacts["managed_keys"] = managed_keys
            return result

        created_keys = self.zotero.create_items(payloads) if payloads else []
        result.created = len(created_keys)
        managed_keys.extend(created_keys)
        result.artifacts["created_keys"] = created_keys
        result.artifacts["existing_keys"] = existing_keys
        result.artifacts["managed_keys"] = managed_keys
        result.artifacts["source"] = source
        result.artifacts["queries"] = queries
        return result
