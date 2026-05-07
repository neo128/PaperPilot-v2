from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paperpilot.clients.ai import AIClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.summary_service import SummaryOptions, SummaryService
from paperpilot.storage.paper_summary_store import PaperSummaryStore
from paperpilot.utils.config import AISettings, load_app_settings

try:
    from paperpilot.clients.deepxiv import DeepXivClient
except ImportError:
    DeepXivClient = None  # type: ignore[misc,assignment]


def _cli_args() -> list[str]:
    """Strip subcommand name from sys.argv for use when called via main.py."""
    args = list(sys.argv[1:])
    while args and not args[0].startswith("-"):
        args = args[1:]
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Zotero PDFs and write AI notes.")
    parser.add_argument("--tag", help="Only process items tagged with this string.")
    parser.add_argument("--collection", help="Only process items inside the specified collection key.")
    parser.add_argument("--collection-name", help="Lookup a Zotero collection by name.")
    parser.add_argument("--item-keys", help="Comma-separated list of specific Zotero item keys to process.")
    parser.add_argument("--pdf-path", action="append", help="Process standalone local PDF path, repeatable.")
    parser.add_argument("--summary-dir", help="Save summaries to this directory when using --pdf-path.")
    parser.add_argument("--insert-note", action="store_true", help="Insert generated summaries back into Zotero notes.")
    parser.add_argument("--recursive", action="store_true", help="Include child collections recursively when collection is selected.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of items to process.")
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--note-tag", default="AI总结")
    parser.add_argument("--storage-dir", help="Override Zotero storage directory.")
    parser.add_argument("--summary-db-path", default=".paperpilot/summaries.sqlite3", help="SQLite DB for AI summary records and extracted facts.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-summary", action="store_true", help="Regenerate canonical AI summaries even when cached.")
    parser.add_argument("--mode", choices=["general", "brief"], default="general", help="AI summary profile for standalone summaries.")
    parser.add_argument("--no-zotero-attachment", action="store_true", help="Do not upload generated Markdown summaries as Zotero attachments.")
    parser.add_argument("--locale", default="zh")
    parser.add_argument("--model", help="Override AI model.")
    parser.add_argument("--use-deepxiv", action="store_true", help="Use DeepXiv as the preferred structured paper source before PDF fallback.")
    return parser.parse_args(_cli_args())


def main() -> None:
    args = parse_args()
    settings = load_app_settings()
    storage_dir = Path(args.storage_dir) if args.storage_dir else (settings.zotero.storage_dir or Path.home() / "Zotero" / "storage")

    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)
    ai_settings = AISettings(
        provider=settings.ai.provider,
        base_url=settings.ai.base_url,
        api_key=settings.ai.api_key,
        model=args.model or settings.ai.model,
    )
    ai = AIClient(ai_settings)
    deepxiv = DeepXivClient() if args.use_deepxiv else None
    summary_store = PaperSummaryStore(Path(args.summary_db_path).expanduser())
    service = SummaryService(zotero, ai, storage_dir, deepxiv=deepxiv, summary_store=summary_store)

    if args.pdf_path:
        pdf_paths = [Path(p).expanduser() for p in args.pdf_path]
        result = service.summarize_local_pdfs(
            pdf_paths,
            SummaryOptions(
                max_pages=args.max_pages,
                max_chars=args.max_chars,
                note_tag=args.note_tag,
                force=args.force or args.force_summary,
                locale=args.locale,
                use_deepxiv=args.use_deepxiv,
                mode=args.mode,
                attach_zotero=not args.no_zotero_attachment,
            ),
            summary_dir=Path(args.summary_dir).expanduser() if args.summary_dir else None,
        )
    else:
        collection_key = args.collection
        if args.collection_name:
            collection_key = zotero.resolve_collection_key(args.collection_name)
            if not collection_key:
                raise SystemExit(f"Collection not found: {args.collection_name}")

        items = []
        if args.item_keys:
            items = [zotero.fetch_item(key.strip()) for key in args.item_keys.split(",") if key.strip()]
        else:
            collection_keys = []
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
            if collection_keys:
                for key in collection_keys:
                    items.extend(list(zotero.iter_items(collection=key, tag=args.tag, limit=args.limit, top_only=False)))
            else:
                items = list(zotero.iter_items(collection=None, tag=args.tag, limit=args.limit, top_only=False))

        result = service.summarize_items(
        items,
        SummaryOptions(
            max_pages=args.max_pages,
            max_chars=args.max_chars,
            note_tag=args.note_tag,
            force=args.force or args.force_summary,
            locale=args.locale,
            use_deepxiv=args.use_deepxiv,
            mode=args.mode,
            attach_zotero=not args.no_zotero_attachment,
        ),
        insert_note=(args.insert_note or not args.pdf_path) and not args.no_zotero_attachment,
    )
    print(
        f"summary done, processed={result.processed}, created={result.created}, skipped={result.skipped}, failed={result.failed}"
    )
    if result.errors:
        print("errors:")
        for err in result.errors:
            print(f"- {err}")
    summary_store.close()


if __name__ == "__main__":
    main()
