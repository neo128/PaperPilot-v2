from __future__ import annotations

import argparse
import sys

from paperpilot.clients.notion import NotionClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.notion_sync_service import NotionSyncOptions, NotionSyncService
from paperpilot.utils.config import load_app_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Zotero items to Notion database")
    parser.add_argument("--collection", help="Zotero collection key")
    parser.add_argument("--collection-name", help="Zotero collection name")
    parser.add_argument("--tag", help="Only sync items with this tag")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-untitled", action="store_true")
    parser.add_argument("--recursive", action="store_true")
    args = list(sys.argv[1:])
    while args and not args[0].startswith("-"):
        args = args[1:]
    return parser.parse_args(args)


def main() -> None:
    args = parse_args()
    settings = load_app_settings()
    if not settings.notion:
        raise SystemExit("Notion settings not configured")

    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)
    notion = NotionClient(settings.notion.api_key, settings.notion.database_id)
    service = NotionSyncService(notion)

    collection_key = args.collection
    if args.collection_name:
        collection_key = zotero.resolve_collection_key(args.collection_name)
        if not collection_key:
            raise SystemExit(f"Collection not found: {args.collection_name}")

    items = []
    if collection_key:
        collection_keys = [collection_key]
        if args.recursive:
            stack = [collection_key]
            seen = set()
            collection_keys = []
            while stack:
                key = stack.pop()
                if key in seen:
                    continue
                seen.add(key)
                collection_keys.append(key)
                for child in zotero.list_child_collections(key):
                    if child.get("key"):
                        stack.append(child["key"])
        for key in collection_keys:
            items.extend(list(zotero.iter_items(collection=key, tag=args.tag, limit=args.limit, top_only=True)))
    else:
        items = list(zotero.iter_items(collection=None, tag=args.tag, limit=args.limit, top_only=True))

    result = service.sync_items(
        items,
        NotionSyncOptions(
            limit=args.limit,
            skip_untitled=args.skip_untitled,
            dry_run=args.dry_run,
            recursive=args.recursive,
        ),
    )
    print(
        f"notion sync done, processed={result.processed}, created={result.created}, updated={result.updated}, skipped={result.skipped}, failed={result.failed}"
    )


if __name__ == "__main__":
    main()
