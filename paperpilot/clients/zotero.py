from __future__ import annotations

import hashlib
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from paperpilot.utils.http import create_session, request_with_retry


def parse_next_link(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None
    for chunk in link_header.split(","):
        parts = chunk.split(";")
        if len(parts) < 2:
            continue
        url_part = parts[0].strip()
        rel_part = parts[1].strip()
        if rel_part == 'rel="next"':
            return url_part.strip("<>")
    return None


def _entry_data(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = entry.get("data")
    return data if isinstance(data, dict) else entry


def _normalize_title(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    return text.strip()


def _normalize_arxiv_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(
        r"(?P<id>(?:[a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?(?:\.pdf)?",
        text,
        re.I,
    )
    return match.group("id") if match else text


def _entry_matches_candidate(entry: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    data = _entry_data(entry)

    candidate_doi = _normalize_doi(candidate.get("doi") or candidate.get("DOI"))
    entry_doi = _normalize_doi(data.get("DOI") or data.get("doi"))
    if candidate_doi and entry_doi and candidate_doi == entry_doi:
        return True

    candidate_arxiv = _normalize_arxiv_id(
        candidate.get("arxiv_id") or candidate.get("archiveLocation") or candidate.get("src_url") or candidate.get("url")
    )
    entry_arxiv = _normalize_arxiv_id(
        data.get("archiveLocation") or data.get("url") or data.get("DOI") or data.get("extra")
    )
    if candidate_arxiv and entry_arxiv and candidate_arxiv == entry_arxiv:
        return True

    candidate_title = _normalize_title(candidate.get("title"))
    entry_title = _normalize_title(data.get("title"))
    return bool(candidate_title and entry_title and candidate_title == entry_title)


class ZoteroClient:
    def __init__(
        self,
        user_id: str,
        api_key: str,
        use_env_proxy: bool = True,
        user_agent: str = "PaperPilot-v2/0.1",
        timeout: int = 8,
    ) -> None:
        self.base = f"https://api.zotero.org/users/{user_id}"
        self.timeout = timeout
        self._search_unavailable_until = 0.0
        self._proxy_disabled = not use_env_proxy
        self.session = create_session(
            headers={"Zotero-API-Key": api_key, "User-Agent": user_agent},
            use_env_proxy=use_env_proxy,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            return request_with_retry(self.session, method, url, timeout=self.timeout, **kwargs)
        except requests.exceptions.ProxyError:
            if self._proxy_disabled:
                raise
            self._proxy_disabled = True
            self.session.trust_env = False
            self.session.proxies = {}
            return request_with_retry(self.session, method, url, timeout=self.timeout, **kwargs)

    def list_collections(self) -> Dict[str, Dict[str, Optional[str]]]:
        resp = self._request(
            "get",
            f"{self.base}/collections",
            params={"limit": 200, "format": "json", "include": "data"},
        )
        out: Dict[str, Dict[str, Optional[str]]] = {}
        for entry in resp.json():
            data = entry.get("data", {})
            out[data.get("name")] = {
                "key": entry.get("key"),
                "parent": data.get("parentCollection"),
            }
        return out

    def list_child_collections(self, parent_key: str) -> List[Dict[str, Optional[str]]]:
        resp = self._request(
            "get",
            f"{self.base}/collections/{parent_key}/collections",
            params={"limit": 200, "format": "json", "include": "data"},
        )
        out: List[Dict[str, Optional[str]]] = []
        for entry in resp.json():
            data = entry.get("data", {})
            out.append({"key": entry.get("key"), "name": data.get("name"), "parent": data.get("parentCollection")})
        return out

    def resolve_collection_key(self, collection_name: str) -> Optional[str]:
        collections = self.list_collections()
        for name, info in collections.items():
            if name == collection_name or (name and name.lower() == collection_name.lower()):
                return info["key"]
        return None

    def create_collection_if_missing(self, name: str) -> str:
        existing = self.resolve_collection_key(name)
        if existing:
            return existing
        self._request("post", f"{self.base}/collections", json=[{"name": name}])
        created = self.resolve_collection_key(name)
        if not created:
            raise RuntimeError(f"Collection created but could not be resolved: {name}")
        return created

    def iter_items(
        self,
        collection: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
        top_only: bool = True,
    ) -> Iterable[Dict[str, Any]]:
        if collection:
            url = f"{self.base}/collections/{collection}/items/top" if top_only else f"{self.base}/collections/{collection}/items"
        else:
            url = f"{self.base}/items/top" if top_only else f"{self.base}/items"

        params = {"format": "json", "include": "data", "limit": 100}
        if tag:
            params["tag"] = tag
        remaining = limit if (limit and limit > 0) else None

        while url:
            resp = self._request("get", url, params=params)
            for entry in resp.json():
                yield entry
                if remaining is not None:
                    remaining -= 1
                    if remaining == 0:
                        return
            url = parse_next_link(resp.headers.get("Link"))
            params = None

    def iter_top_items(self, limit: int = 100) -> Iterable[Dict[str, Any]]:
        yield from self.iter_items(limit=limit, top_only=True)

    def search_items(self, query: str, limit: int = 25, top_only: bool = True) -> List[Dict[str, Any]]:
        url = f"{self.base}/items/top" if top_only else f"{self.base}/items"
        resp = self._request(
            "get",
            url,
            params={
                "format": "json",
                "include": "data",
                "q": query,
                "qmode": "everything",
                "limit": min(max(limit, 1), 100),
            },
        )
        return list(resp.json())

    def find_existing_item(self, candidate: Dict[str, Any], limit: int = 25) -> Optional[Dict[str, Any]]:
        """Find an existing Zotero top-level item by DOI, arXiv id, or exact normalized title."""
        if time.time() < self._search_unavailable_until:
            return None

        terms: List[str] = []
        doi = _normalize_doi(candidate.get("doi") or candidate.get("DOI"))
        if doi:
            terms.append(doi)
        arxiv_id = _normalize_arxiv_id(
            candidate.get("arxiv_id") or candidate.get("archiveLocation") or candidate.get("src_url") or candidate.get("url")
        )
        if arxiv_id:
            terms.append(arxiv_id)
        title = str(candidate.get("title") or "").strip()
        if title:
            terms.append(title)

        seen_queries: set[str] = set()
        for term in terms:
            if not term or term in seen_queries:
                continue
            seen_queries.add(term)
            try:
                matches = self.search_items(term, limit=limit, top_only=True)
            except Exception:
                self._search_unavailable_until = time.time() + 300
                return None
            for entry in matches:
                if _entry_matches_candidate(entry, candidate):
                    return entry
        return None

    def fetch_item(self, item_key: str) -> Dict[str, Any]:
        resp = self._request("get", f"{self.base}/items/{item_key}", params={"format": "json", "include": "data"})
        return resp.json()

    def fetch_children(self, parent_key: str) -> List[Dict[str, Any]]:
        url = f"{self.base}/items/{parent_key}/children"
        params = {"format": "json", "include": "data", "limit": 100}
        out: List[Dict[str, Any]] = []
        while url:
            resp = self._request("get", url, params=params)
            out.extend(resp.json())
            url = parse_next_link(resp.headers.get("Link"))
            params = None
        return out

    def create_items(self, items: List[Dict[str, Any]]) -> List[str]:
        keys: List[str] = []
        for start in range(0, len(items), 25):
            keys.extend(self._create_items_batch(items[start : start + 25]))
        return keys

    def _create_items_batch(self, items: List[Dict[str, Any]]) -> List[str]:
        if not items:
            return []
        try:
            resp = self._request("post", f"{self.base}/items", json=items)
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 413 and len(items) > 1:
                mid = max(1, len(items) // 2)
                return self._create_items_batch(items[:mid]) + self._create_items_batch(items[mid:])
            raise
        data = resp.json()
        successful = data.get("successful") or {}
        keys: List[str] = []
        for _, info in successful.items():
            if isinstance(info, dict) and info.get("key"):
                keys.append(info["key"])
        return keys

    def create_file_attachment(
        self,
        parent_key: str,
        file_path: str | Path,
        *,
        title: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        path = Path(file_path)
        data = path.read_bytes()
        filename = path.name
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        attachment_keys = self.create_items([
            {
                "itemType": "attachment",
                "parentItem": parent_key,
                "linkMode": "imported_file",
                "title": title or filename,
                "note": "",
                "tags": [{"tag": t} for t in (tags or [])],
                "relations": {},
                "contentType": mime,
                "charset": "utf-8" if mime.startswith("text/") else "",
                "filename": filename,
                "md5": None,
                "mtime": None,
            }
        ])
        if not attachment_keys:
            return None
        attachment_key = attachment_keys[0]
        md5 = hashlib.md5(data).hexdigest()
        mtime_ms = int(path.stat().st_mtime * 1000)
        auth = self._request(
            "post",
            f"{self.base}/items/{attachment_key}/file",
            data={
                "md5": md5,
                "filename": filename,
                "filesize": str(len(data)),
                "mtime": str(mtime_ms),
            },
            headers={"If-None-Match": "*"},
        ).json()
        if auth.get("exists"):
            return attachment_key

        upload_body = auth.get("prefix", "").encode("utf-8") + data + auth.get("suffix", "").encode("utf-8")
        upload_response = self._upload_file_with_retry(
            auth["url"],
            upload_body,
            content_type=auth["contentType"],
        )
        upload_response.raise_for_status()
        self._request(
            "post",
            f"{self.base}/items/{attachment_key}/file",
            data={"upload": auth["uploadKey"]},
            headers={"If-None-Match": "*"},
        )
        return attachment_key

    def _upload_file_with_retry(self, url: str, body: bytes, *, content_type: str) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                return requests.post(
                    url,
                    data=body,
                    headers={"Content-Type": content_type},
                    timeout=max(self.timeout, 60),
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def update_item(self, item_key: str, version: int, new_data: Dict[str, Any]) -> None:
        self._request(
            "put",
            f"{self.base}/items/{item_key}",
            json=new_data,
            headers={"If-Unmodified-Since-Version": str(version)},
        )

    def add_item_to_collection(self, item_key: str, collection_key: str) -> bool:
        entry = self.fetch_item(item_key)
        data = dict(_entry_data(entry))
        collections = list(data.get("collections") or [])
        if collection_key in collections:
            return False
        collections.append(collection_key)
        data["collections"] = collections
        version = entry.get("version") or data.get("version")
        if version is None:
            raise RuntimeError(f"Cannot update Zotero item without version: {item_key}")
        self.update_item(item_key, int(version), data)
        return True

    def create_note(self, parent_key: str, note_html: str, tags: Optional[List[str]] = None) -> None:
        payload = [{"itemType": "note", "parentItem": parent_key, "note": note_html, "tags": [{"tag": t} for t in (tags or [])]}]
        self._request("post", f"{self.base}/items", json=payload)

    def update_note(self, note_key: str, version: int, note_html: str, tags: Optional[List[str]] = None) -> None:
        entry = self.fetch_item(note_key)
        data = dict(_entry_data(entry))
        data["note"] = note_html
        data["tags"] = [{"tag": t} for t in (tags or [])]
        item_version = int(entry.get("version") or data.get("version") or version)
        self.update_item(note_key, item_version, data)

    def create_attachment_url(
        self,
        parent_key: str,
        title: str,
        url: str,
        content_type: str = "application/pdf",
    ) -> None:
        payload = [{
            "itemType": "attachment",
            "parentItem": parent_key,
            "title": title,
            "linkMode": "linked_url",
            "contentType": content_type,
            "url": url,
        }]
        self._request("post", f"{self.base}/items", json=payload)
