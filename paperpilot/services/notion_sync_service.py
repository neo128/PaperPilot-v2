from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from paperpilot.clients.notion import NotionClient
from paperpilot.models.results import StageResult


@dataclass
class NotionSyncOptions:
    limit: int = 200
    skip_untitled: bool = True
    dry_run: bool = False
    recursive: bool = False


def build_property_mapping(db: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    props = db.get("properties", {})
    mapping: Dict[str, Dict[str, str]] = {}

    for name, definition in props.items():
        if definition.get("type") == "title" and "title" not in mapping:
            mapping["title"] = {"name": name, "type": "title"}

    preferred = {
        "authors": ["Authors", "作者"],
        "year": ["Year", "年份"],
        "abstract": ["Abstract", "摘要"],
        "tags": ["Tags", "标签"],
        "url": ["URL", "Project Page", "Link"],
        "doi": ["DOI"],
        "zotero_key": ["Zotero Key"],
    }
    for field, candidates in preferred.items():
        for candidate in candidates:
            if candidate in props:
                mapping[field] = {"name": candidate, "type": props[candidate].get("type")}
                break
    return mapping


def extract_item_data(entry: Dict[str, Any]) -> Dict[str, Any]:
    return entry.get("data", entry)


def extract_authors(creators: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for creator in creators or []:
        if creator.get("name"):
            names.append(creator["name"])
            continue
        first = creator.get("firstName") or ""
        last = creator.get("lastName") or ""
        full = f"{first} {last}".strip()
        if full:
            names.append(full)
    return names


def build_notion_properties(item: Dict[str, Any], mapping: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    data = extract_item_data(item)
    props: Dict[str, Any] = {}

    title = data.get("title") or data.get("shortTitle") or data.get("key") or "Untitled"
    if "title" in mapping:
        props[mapping["title"]["name"]] = {"title": [{"text": {"content": title[:2000]}}]}

    if "authors" in mapping:
        authors = extract_authors(data.get("creators") or [])
        field_type = mapping["authors"].get("type", "rich_text")
        if field_type == "multi_select":
            props[mapping["authors"]["name"]] = {"multi_select": [{"name": name[:100]} for name in authors[:50]]}
        else:
            props[mapping["authors"]["name"]] = {"rich_text": [{"text": {"content": ", ".join(authors)[:2000]}}]}

    if "year" in mapping:
        date_value = data.get("date") or ""
        year = None
        for token in str(date_value).split("-"):
            if token.isdigit() and len(token) == 4:
                year = int(token)
                break
        if year:
            props[mapping["year"]["name"]] = {"number": year}

    if "abstract" in mapping and data.get("abstractNote"):
        props[mapping["abstract"]["name"]] = {
            "rich_text": [{"text": {"content": str(data.get("abstractNote"))[:2000]}}]
        }

    if "tags" in mapping:
        item_tags = [t.get("tag") for t in (data.get("tags") or []) if t.get("tag")]
        props[mapping["tags"]["name"]] = {"multi_select": [{"name": tag[:100]} for tag in item_tags[:50]]}

    if "url" in mapping and data.get("url"):
        props[mapping["url"]["name"]] = {"url": data.get("url")}

    if "doi" in mapping and data.get("DOI"):
        field_type = mapping["doi"]["type"]
        if field_type == "url":
            props[mapping["doi"]["name"]] = {"url": f"https://doi.org/{data.get('DOI')}"}
        else:
            props[mapping["doi"]["name"]] = {"rich_text": [{"text": {"content": str(data.get("DOI"))[:2000]}}]}

    if "zotero_key" in mapping and data.get("key"):
        props[mapping["zotero_key"]["name"]] = {"rich_text": [{"text": {"content": data.get("key")}}]}

    return props


class NotionSyncService:
    def __init__(self, notion: NotionClient) -> None:
        self.notion = notion

    def sync_items(self, items: List[Dict[str, Any]], options: NotionSyncOptions) -> StageResult:
        result = StageResult(stage="notion-sync")
        db = self.notion.get_database()
        mapping = build_property_mapping(db)
        title_prop_name = mapping.get("title", {}).get("name")
        zotero_key_prop = mapping.get("zotero_key", {}).get("name")

        for item in items[: options.limit or None]:
            result.processed += 1
            data = extract_item_data(item)
            title = data.get("title") or data.get("shortTitle") or ""
            if options.skip_untitled and not title:
                result.skipped += 1
                continue

            props = build_notion_properties(item, mapping)
            page_id: Optional[str] = None
            if zotero_key_prop and data.get("key"):
                page_id = self.notion.query_by_text(zotero_key_prop, data.get("key"))
            if not page_id and title_prop_name and title:
                page_id = self.notion.query_by_title(title_prop_name, title)

            if options.dry_run:
                if page_id:
                    result.updated += 1
                else:
                    result.created += 1
                continue

            if page_id:
                self.notion.update_page(page_id, props)
                result.updated += 1
            else:
                self.notion.create_page(props)
                result.created += 1

        return result
