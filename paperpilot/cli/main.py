from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paperpilot.cli.notion_sync import main as notion_sync_main
from paperpilot.cli.pipeline import main as pipeline_main
from paperpilot.cli.review import main as review_main
from paperpilot.cli.summary import main as summary_main
from paperpilot.cli.watch import main as watch_main
from paperpilot.cli.zotero import main as zotero_main
from paperpilot.pipeline import NotionStageConfig, PipelineConfig, PipelineOrchestrator, SummaryStageConfig, WatchStageConfig
from paperpilot.utils.run_logging import (
    log_command_finish,
    log_exception,
    log_pipeline_result,
    setup_run_logging,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paperpilot", description="PaperPilot v2 unified CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("watch", add_help=False)
    sub.add_parser("summary", add_help=False)
    sub.add_parser("notion-sync", add_help=False)
    sub.add_parser("pipeline", add_help=False)
    sub.add_parser("review", add_help=False)
    sub.add_parser("zotero", add_help=False)

    run = sub.add_parser("run", help="Run unified pipeline")
    run.add_argument("--watch-query")
    run.add_argument("--watch-limit", type=int, default=10)
    run.add_argument("--watch-dry-run", action="store_true")
    run.add_argument("--summary-limit", type=int, default=20)
    run.add_argument("--enable-summary", action="store_true")
    run.add_argument("--skip-summary", action="store_true")
    run.add_argument("--summary-use-deepxiv", action="store_true")
    run.add_argument("--summary-no-incremental", action="store_true")
    run.add_argument("--notion-limit", type=int, default=200)
    run.add_argument("--notion-dry-run", action="store_true")
    run.add_argument("--notion-no-incremental", action="store_true")
    run.add_argument("--state-db-path", default=".paperpilot-v2/state.sqlite3")
    return parser


def main() -> None:
    parser = build_parser()
    args, _ = parser.parse_known_args()
    setup_run_logging(command=args.command or "help", argv=sys.argv)

    try:
        if args.command == "watch":
            watch_main()
            log_command_finish(success=True)
            return
        if args.command == "summary":
            summary_main()
            log_command_finish(success=True)
            return
        if args.command == "notion-sync":
            notion_sync_main()
            log_command_finish(success=True)
            return
        if args.command == "pipeline":
            pipeline_main()
            log_command_finish(success=True)
            return
        if args.command == "review":
            review_main()
            log_command_finish(success=True)
            return
        if args.command == "zotero":
            zotero_main()
            log_command_finish(success=True)
            return
        if args.command == "run":
            config = PipelineConfig(
                state_db_path=Path(args.state_db_path),
                watch=WatchStageConfig(enabled=bool(args.watch_query), query=args.watch_query or "agent memory", limit=args.watch_limit, dry_run=args.watch_dry_run),
                summary=SummaryStageConfig(enabled=args.enable_summary and not args.skip_summary, limit=args.summary_limit, use_deepxiv=args.summary_use_deepxiv, incremental=not args.summary_no_incremental),
                notion=NotionStageConfig(limit=args.notion_limit, dry_run=args.notion_dry_run, incremental=not args.notion_no_incremental),
            )
            result = PipelineOrchestrator(config).run()
            log_pipeline_result(result)
            print(json.dumps({"success": result.success, "stages": [stage.__dict__ for stage in result.stages]}, ensure_ascii=False, indent=2))
            log_command_finish(success=result.success, exit_code=0 if result.success else 1)
            return

        parser.print_help()
        log_command_finish(success=True)
    except SystemExit as exc:
        code = int(exc.code or 0) if isinstance(exc.code, int) else 1
        log_command_finish(success=code == 0, exit_code=code)
        raise
    except Exception as exc:
        log_exception(exc)
        log_command_finish(success=False, exit_code=1)
        raise


if __name__ == "__main__":
    main()
