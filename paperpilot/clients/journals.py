"""Journal & Conference paper search via Semantic Scholar + CrossRef.

Queries a curated list of top venues in embodied AI, robotics, and AI,
then returns candidates in the same dict shape expected by build_zotero_item.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curated venue list  (journals + conferences)
# ---------------------------------------------------------------------------

VENUES: List[Dict[str, str]] = [
    # --- Top journals (general science / AI / robotics) ---
    {"name": "Nature", "type": "journal", "container": "Nature"},
    {"name": "Nature Machine Intelligence", "type": "journal", "container": "Nature Machine Intelligence"},
    {"name": "Science", "type": "journal", "container": "Science"},
    {"name": "Science Robotics", "type": "journal", "container": "Science Robotics"},
    {"name": "PNAS", "type": "journal", "container": "Proceedings of the National Academy of Sciences"},
    # --- AI / ML venues ---
    {"name": "NeurIPS", "type": "conference", "container": "NeurIPS"},
    {"name": "ICML", "type": "conference", "container": "ICML"},
    {"name": "ICLR", "type": "conference", "container": "ICLR"},
    # --- Vision venues ---
    {"name": "CVPR", "type": "conference", "container": "CVPR"},
    {"name": "ICCV", "type": "conference", "container": "ICCV"},
    {"name": "ECCV", "type": "conference", "container": "ECCV"},
    # --- Robotics venues ---
    {"name": "ICRA", "type": "conference", "container": "ICRA"},
    {"name": "IROS", "type": "conference", "container": "IROS"},
    {"name": "RSS", "type": "conference", "container": "RSS"},
    {"name": "CoRL", "type": "conference", "container": "CoRL"},
    {"name": "T-RO", "type": "journal", "container": "IEEE Transactions on Robotics"},
    {"name": "RA-L", "type": "journal", "container": "IEEE Robotics and Automation Letters"},
    {"name": "IJRR", "type": "journal", "container": "The International Journal of Robotics Research"},
]

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,abstract,authors,year,externalIds,url,venue,publicationTypes"
S2_RATE_DELAY = 0.25  # seconds between S2 requests to stay well under 100 req/5min
S2_RATE_LIMIT_COOLDOWN = 300  # seconds to skip S2 after a rate-limit response
_S2_RATE_LIMITED_UNTIL = 0.0
_S2_RATE_LIMIT_NOTICE_EMITTED = False

CR_BASE = "https://api.crossref.org/works"
CR_RATE_DELAY = 0.15  # polite pool rate

USER_AGENT = "PaperPilot-v2/0.1 (paper retrieval; mailto:admin@example.com)"


# ---------------------------------------------------------------------------
# Semantic Scholar search
# ---------------------------------------------------------------------------

def _s2_search(query: str, venue_names: List[str], limit: int) -> List[Dict[str, Any]]:
    """Search S2 with venue name(s) AND query keyword, then post-filter by venue string."""
    global _S2_RATE_LIMIT_NOTICE_EMITTED, _S2_RATE_LIMITED_UNTIL
    if time.time() < _S2_RATE_LIMITED_UNTIL:
        logger.debug("S2 rate-limit cooldown active, skipping S2 for query=%s", query)
        return []
    _S2_RATE_LIMIT_NOTICE_EMITTED = False

    results: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()

    # Group venue names to avoid too many API calls: use broad venue filter
    venue_clause = " OR ".join(f'"{v}"' for v in venue_names)
    # S2 doesn't support venue filter in search well; search with query and filter later
    url = S2_BASE
    params: Dict[str, Any] = {
        "query": query,
        "limit": min(limit * 3, 100),  # fetch more, then filter
        "fields": S2_FIELDS,
        "year": "2023-",
    }

    try:
        resp = requests.get(url, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 429:
            logger.debug("S2 rate limited, waiting and retrying once")
            time.sleep(2)
            resp = requests.get(url, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 429:
                _S2_RATE_LIMITED_UNTIL = time.time() + S2_RATE_LIMIT_COOLDOWN
                if not _S2_RATE_LIMIT_NOTICE_EMITTED:
                    logger.debug(
                        "S2 rate limited; using CrossRef-only journal search for the next %d seconds",
                        S2_RATE_LIMIT_COOLDOWN,
                    )
                    _S2_RATE_LIMIT_NOTICE_EMITTED = True
        if resp.status_code != 200:
            logger.debug("S2 search returned %d for query=%s", resp.status_code, query)
            return []
        data = resp.json() or {}
    except Exception as exc:
        logger.warning("S2 search failed: %s", exc)
        return []

    items = data.get("data") or []
    for item in items:
        venue_raw = (item.get("venue") or "").strip()
        pub_types = item.get("publicationTypes") or []
        year = item.get("year")

        # --- venue match ---
        venue_match = False
        if venue_raw:
            vl = venue_raw.lower()
            for vn in venue_names:
                if vn.lower() in vl:
                    venue_match = True
                    break
        # Also check publicationTypes for known conference names
        if not venue_match:
            for pt in pub_types:
                ptl = (pt or "").lower()
                for vn in venue_names:
                    if vn.lower() in ptl:
                        venue_match = True
                        break

        if not venue_match:
            continue

        title = (item.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        authors = []
        for a in (item.get("authors") or []):
            if isinstance(a, dict):
                name = a.get("name")
                if name:
                    authors.append(name)

        ext = item.get("externalIds") or {}
        doi = ext.get("DOI") or ext.get("doi")

        results.append({
            "title": title,
            "abstract": item.get("abstract") or "",
            "authors": authors,
            "url": item.get("url") or f"https://www.semanticscholar.org/search?q={quote(title)}",
            "date": str(year) if year else "",
            "year": year,
            "venue": venue_raw,
            "doi": doi,
            "source": "semantic_scholar",
        })

        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# CrossRef search (by query + container-title filter)
# ---------------------------------------------------------------------------

def _cr_search(query: str, containers: List[str], limit: int) -> List[Dict[str, Any]]:
    """Search CrossRef for papers whose container-title matches known venue names."""
    results: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()

    for container in containers:
        if len(results) >= limit:
            break

        url = CR_BASE
        params = {
            "query": query,
            "filter": f"container-title:{container}",
            "rows": min(max(limit - len(results), 5), 20),
            "select": "title,abstract,author,issued,URL,DOI,published-print,published-online",
        }
        headers = {"User-Agent": USER_AGENT}

        try:
            resp = requests.get(url, params=params, timeout=20, headers=headers)
            if resp.status_code == 429:
                # Respect Retry-After if present
                retry_after = resp.headers.get("Retry-After", "1")
                time.sleep(int(retry_after))
                resp = requests.get(url, params=params, timeout=20, headers=headers)
            if resp.status_code != 200:
                continue
            msg = (resp.json() or {}).get("message", {})
        except Exception as exc:
            logger.debug("CrossRef search failed for container=%s: %s", container, exc)
            continue

        items = msg.get("items") or []
        for item in items:
            title_list = item.get("title") or []
            title = (title_list[0] if title_list else "").strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            authors = []
            for a in (item.get("author") or []):
                given = a.get("given", "")
                family = a.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)

            # Date
            date_str = ""
            year = None
            for key in ("issued", "published-print", "published-online"):
                parts = (item.get(key) or {}).get("date-parts")
                if parts and parts[0]:
                    year = parts[0][0]
                    date_str = "-".join(str(p) for p in parts[0])
                    break

            results.append({
                "title": title,
                "abstract": (item.get("abstract") or "").strip(),
                "authors": authors,
                "url": item.get("URL") or "",
                "date": date_str,
                "year": year,
                "venue": container,
                "doi": item.get("DOI"),
                "source": "crossref",
            })

            if len(results) >= limit:
                break

        time.sleep(CR_RATE_DELAY)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_journals(
    query: str,
    limit: int = 10,
    venue_subset: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search top journals/conferences for a query.

    Returns list of dicts compatible with ``build_zotero_item`` in watch_service.
    Uses both S2 and CrossRef, then deduplicates by DOI/title similarity.
    """
    if venue_subset:
        venues = [v for v in VENUES if v["name"] in venue_subset]
    else:
        venues = VENUES

    venue_names = [v["name"] for v in venues]
    containers = [v["container"] for v in venues]

    logger.info("journals: searching S2 for query=%s limit=%d venues=%s", query, limit, venue_subset or "all")
    s2_results = _s2_search(query, venue_names, limit)

    logger.info("journals: searching CrossRef for query=%s limit=%d", query, limit)
    cr_results = _cr_search(query, containers, limit)

    # Merge + deduplicate
    merged = _dedup(s2_results + cr_results)
    return merged[:limit]


def _title_key(title: str) -> str:
    """Normalize title for comparison."""
    return " ".join(title.lower().split())


def _dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by DOI first, then normalized title."""
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    out: List[Dict[str, Any]] = []

    for item in items:
        doi = item.get("doi")
        tk = _title_key(item.get("title", ""))

        if doi and doi.lower() in seen_doi:
            continue
        if tk and tk in seen_title:
            continue

        if doi:
            seen_doi.add(doi.lower())
        if tk:
            seen_title.add(tk)
        out.append(item)

    return out
