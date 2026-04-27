from __future__ import annotations

import argparse
import json
import sys

from paperpilot.pipeline import NotionStageConfig, PipelineConfig, PipelineOrchestrator, SummaryStageConfig, WatchStageConfig


def _cli_args() -> list[str]:
    """Strip subcommand name from sys.argv for use when called via main.py."""
    args = list(sys.argv[1:])
    while args and not args[0].startswith("-"):
        args = args[1:]
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PaperPilot-v2 pipeline")
    parser.add_argument("--skip-watch", action="store_true")
    parser.add_argument("--skip-summary", action="store_true")
    parser.add_argument("--enable-summary", action="store_true")
    parser.add_argument("--skip-notion", action="store_true")
    parser.add_argument("--watch-query")
    parser.add_argument("--watch-limit", type=int, default=10)
    parser.add_argument("--watch-collection-name")
    parser.add_argument("--watch-create-collections", action="store_true")
    parser.add_argument("--watch-dry-run", action="store_true")
    parser.add_argument("--summary-tag")
    parser.add_argument("--summary-collection")
    parser.add_argument("--summary-collection-name")
    parser.add_argument("--summary-limit", type=int, default=20)
    parser.add_argument("--summary-use-deepxiv", action="store_true")
    parser.add_argument("--summary-no-insert-note", action="store_true")
    parser.add_argument("--notion-tag")
    parser.add_argument("--notion-collection")
    parser.add_argument("--notion-collection-name")
    parser.add_argument("--notion-limit", type=int, default=200)
    parser.add_argument("--notion-dry-run", action="store_true")
    parser.add_argument("--notion-recursive", action="store_true")
    return parser.parse_args(_cli_args())


def main() -> None:
    args = parse_args()
    config = PipelineConfig(
        watch=WatchStageConfig(
            enabled=not args.skip_watch,
            query=args.watch_query or "agent memory",
            limit=args.watch_limit,
            collection_name=args.watch_collection_name,
            create_collections=args.watch_create_collections,
            dry_run=args.watch_dry_run,
        ),
        summary=SummaryStageConfig(
            enabled=args.enable_summary and not args.skip_summary,
            tag=args.summary_tag,
            collection=args.summary_collection,
            collection_name=args.summary_collection_name,
            limit=args.summary_limit,
            use_deepxiv=args.summary_use_deepxiv,
            insert_note=not args.summary_no_insert_note,
        ),
        notion=NotionStageConfig(
            enabled=not args.skip_notion,
            tag=args.notion_tag,
            collection=args.notion_collection,
            collection_name=args.notion_collection_name,
            limit=args.notion_limit,
            dry_run=args.notion_dry_run,
            recursive=args.notion_recursive,
        ),
    )
    result = PipelineOrchestrator(config).run()
    print(json.dumps({
        "success": result.success,
        "stages": [stage.__dict__ for stage in result.stages],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
