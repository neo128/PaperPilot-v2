from __future__ import annotations

import argparse
import sys

from paperpilot.clients.deepxiv import DeepXivClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.watch_service import WatchOptions, WatchService
from paperpilot.utils.config import load_app_settings
from paperpilot.utils.run_logging import log_stage_result


def _cli_args() -> list[str]:
    """Strip subcommand name from sys.argv for use when called via main.py."""
    args = list(sys.argv[1:])
    while args and not args[0].startswith("-"):
        args = args[1:]
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search papers and import into Zotero")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--collection-name")
    parser.add_argument("--create-collections", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--journals", action="store_true", help="Also search curated journals/conferences (Nature, Science, CVPR, ICRA, etc.)")
    parser.add_argument("--prompt", help="Additional review prompt used when expanding literature-search query groups.")
    parser.add_argument("--expand-queries", action="store_true", help="Expand the topic into Phase-1 query groups such as benchmark/survey/dataset/system.")
    parser.add_argument("--no-reuse-existing", action="store_true", help="Create Zotero items without checking whether matching items already exist.")
    parser.add_argument("--use-deepxiv", action="store_true", help="Use DeepXiv before arXiv. Defaults to arXiv only.")
    return parser.parse_args(_cli_args())


def main() -> None:
    args = parse_args()
    settings = load_app_settings()
    deepxiv = DeepXivClient() if args.use_deepxiv else None
    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)
    service = WatchService(zotero=zotero, deepxiv=deepxiv)
    result = service.search_and_import(
        WatchOptions(
            query=args.query,
            limit=args.limit,
            create_collections=args.create_collections,
            collection_name=args.collection_name,
            dry_run=args.dry_run,
            journals=args.journals,
            prompt=args.prompt,
            expand_queries=args.expand_queries,
            reuse_existing=not args.no_reuse_existing,
        )
    )
    print(
        f"watch done, processed={result.processed}, created={result.created}, updated={result.updated}, skipped={result.skipped}, failed={result.failed}"
    )
    log_stage_result(result)


if __name__ == "__main__":
    main()
