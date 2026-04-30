"""ArXiv API client — used as fallback when DeepXiv search is unavailable."""

from __future__ import annotations

import datetime as dt
import re
import time
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

from paperpilot.utils.http import create_session, request_with_retry

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
ARXIV_QUERY_FIELDS_RE = re.compile(r"\b(?:all|ti|au|abs|cat|id|doi|jr|co|rn):|\b(?:AND|OR|ANDNOT)\b", re.I)
ARXIV_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _parse_arxiv_id(entry: ET.Element) -> Optional[str]:
    id_text = entry.findtext(f"{ATOM_NS}id") or ""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([A-Za-z0-9.\-]+)", id_text)
    if m:
        return m.group(1)
    for link in entry.findall(f"{ATOM_NS}link"):
        href = link.attrib.get("href")
        if not href:
            continue
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([A-Za-z0-9.\-]+)", href)
        if m:
            return m.group(1)
    return None


def _parse_authors(entry: ET.Element) -> List[str]:
    authors: List[str] = []
    for a in entry.findall(f"{ATOM_NS}author"):
        name = a.findtext(f"{ATOM_NS}name")
        if name:
            authors.append(name.strip())
    return authors


def _parse_abstract(entry: ET.Element) -> str:
    summary = entry.findtext(f"{ATOM_NS}summary") or ""
    return summary.strip()


def _parse_title(entry: ET.Element) -> str:
    title = entry.findtext(f"{ATOM_NS}title") or ""
    return re.sub(r"\s+", " ", title).strip()


def _parse_published(entry: ET.Element) -> str:
    pub = entry.findtext(f"{ATOM_NS}published") or ""
    if pub:
        return pub[:10]
    return ""


def _parse_pdf_url(entry: ET.Element) -> str:
    arxiv_id = _parse_arxiv_id(entry)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return ""


def _parse_doi(entry: ET.Element) -> str:
    for doi_elem in entry.findall(f"{ARXIV_NS}doi"):
        val = (doi_elem.text or "").strip()
        if val:
            return val
    return ""


def _entry_to_dict(entry: ET.Element) -> Dict[str, Any]:
    return {
        "arxiv_id": _parse_arxiv_id(entry),
        "title": _parse_title(entry),
        "abstract": _parse_abstract(entry),
        "authors": _parse_authors(entry),
        "published": _parse_published(entry),
        "src_url": _parse_pdf_url(entry),
        "doi": _parse_doi(entry),
    }


def _build_search_query(query: str, *, max_terms: int = 7) -> str:
    """Convert plain-language input to an arXiv API query.

    arXiv treats ``all:"long natural language topic"`` as an exact phrase,
    which is too strict for review topics. For plain text, use a compact
    AND query over meaningful terms while preserving explicit arXiv syntax.
    """
    raw = query.strip()
    if not raw:
        return "all:paper"
    if ARXIV_QUERY_FIELDS_RE.search(raw):
        return raw

    terms: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", raw.lower()):
        if token in ARXIV_STOPWORDS or len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= max_terms:
            break

    if not terms:
        return f'all:"{raw}"'
    return " AND ".join(f"all:{term}" for term in terms)


class ArxivClient:
    """Thin wrapper around the arXiv public API (no auth required)."""

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: int = 12, max_results: int = 30) -> None:
        self.timeout = timeout
        self.max_results = max_results
        self.user_agents = (
            "PaperPilot-v2/0.1 (mailto:admin@example.com)",
            f"python-requests/{requests.__version__}",
        )
        self.session = self._new_session(self.user_agents[0])

    def _new_session(self, user_agent: str) -> requests.Session:
        return create_session(headers={"User-Agent": user_agent})

    def _request(self, params: Dict[str, Any]) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            self.session = self._new_session(self.user_agents[attempt % len(self.user_agents)])
            try:
                return request_with_retry(
                    self.session,
                    "get",
                    self.BASE_URL,
                    params=params,
                    timeout=self.timeout,
                    retries=1,
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(0.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def search(self, query: str, limit: int = 10, sort_by: str = "submittedDate") -> List[Dict[str, Any]]:
        """Search arXiv and return a list of paper dicts compatible with watch_service."""
        params = {
            "search_query": _build_search_query(query),
            "start": 0,
            "max_results": min(limit, self.max_results),
            "sortBy": sort_by,
            "sortOrder": "descending",
        }

        resp = self._request(params)
        root = ET.fromstring(resp.text)
        entries = root.findall(f"{ATOM_NS}entry")

        results: List[Dict[str, Any]] = []
        for entry in entries:
            results.append(_entry_to_dict(entry))

        return results

    def search_recent(self, query: str, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Search arXiv for recent papers (sorted by submission date, no explicit date filter).

        arXiv's date range filter is unreliable (frequent 500 errors), so we rely on
        sortBy=submittedDate which naturally returns the newest papers first.
        """
        params = {
            "search_query": _build_search_query(query),
            "start": 0,
            "max_results": min(limit, self.max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        resp = self._request(params)
        root = ET.fromstring(resp.text)
        entries = root.findall(f"{ATOM_NS}entry")

        results: List[Dict[str, Any]] = []
        for entry in entries:
            results.append(_entry_to_dict(entry))

        return results
