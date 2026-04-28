from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from paperpilot.clients.ai import AIClient
from paperpilot.clients.deepxiv import DeepXivClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.review_service import LiteratureReviewService, ReviewProject, ReviewReadOptions, slugify
from paperpilot.services.watch_service import WatchOptions, WatchService
from paperpilot.utils.config import AISettings, load_app_settings


def _cli_args() -> list[str]:
    args = list(sys.argv[1:])
    if args and args[0] == "review":
        return args[1:]
    return args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Literature review workspace and automation")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Create a local literature-review workspace")
    init.add_argument("--topic", required=True)
    init.add_argument("--slug")
    init.add_argument("--root", default=".review_projects")

    build_pool = sub.add_parser("build-pool", help="Build paper_pool CSV files from Zotero")
    _add_project_args(build_pool)
    _add_zotero_source_args(build_pool)

    read = sub.add_parser("read", help="AI-read papers and write reading cards plus coded CSV")
    _add_project_args(read)
    read.add_argument("--limit", type=int, default=25)
    read.add_argument("--force", action="store_true")
    read.add_argument("--locale", default="zh")
    read.add_argument("--max-chars", type=int, default=12000)
    read.add_argument("--use-deepxiv", action="store_true")
    read.add_argument("--insert-zotero-notes", action="store_true")
    read.add_argument("--model")

    draft = sub.add_parser("draft", help="Draft review_v1.md from coded pool and reading cards")
    _add_project_args(draft)
    draft.add_argument("--locale", default="zh")
    draft.add_argument("--model")

    sync = sub.add_parser("sync-zotero", help="Write generated reading cards back to Zotero notes")
    _add_project_args(sync)

    run = sub.add_parser("run", help="Run search/import, pool build, AI reading, and draft")
    run.add_argument("--topic", required=True)
    run.add_argument("--slug")
    run.add_argument("--root", default=".review_projects")
    run.add_argument("--limit", type=int, default=25)
    run.add_argument("--collection-name")
    run.add_argument("--create-collections", action="store_true")
    run.add_argument("--tag")
    run.add_argument("--watch-query")
    run.add_argument("--prompt")
    run.add_argument("--expand-queries", action="store_true")
    run.add_argument("--journals", action="store_true")
    run.add_argument("--locale", default="zh")
    run.add_argument("--max-chars", type=int, default=12000)
    run.add_argument("--use-deepxiv", action="store_true")
    run.add_argument("--insert-zotero-notes", action="store_true")
    run.add_argument("--model")
    return parser


def _add_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slug", required=True)
    parser.add_argument("--topic", help="Review topic. Defaults to slug when omitted.")
    parser.add_argument("--root", default=".review_projects")


def _add_zotero_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--collection", help="Zotero collection key")
    parser.add_argument("--collection-name", help="Zotero collection name")
    parser.add_argument("--tag", help="Zotero tag")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--recursive", action="store_true")


def _project(args: argparse.Namespace) -> ReviewProject:
    topic = args.topic or args.slug
    slug = args.slug or slugify(topic)
    return ReviewProject(slug=slug, topic=topic, root=Path(args.root))


def _settings_and_clients(args: argparse.Namespace, need_ai: bool = False, use_deepxiv: bool = False):
    settings = load_app_settings()
    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)
    ai = None
    if need_ai:
        if not settings.ai.api_key:
            raise SystemExit(
                "AI API key is required for review read/draft/run. "
                "Set AI_API_KEY in .env, or set OPENAI_API_KEY in the environment. "
                "To only build the Zotero paper pool without AI, run `review build-pool`."
            )
        model = getattr(args, "model", None) or settings.ai.model
        if not model:
            raise SystemExit(
                "AI model is required for review read/draft/run. "
                "Set AI_MODEL in .env or pass --model. "
                "For OpenAI-compatible providers, also set AI_BASE_URL when needed."
            )
        ai = AIClient(
            AISettings(
                provider=settings.ai.provider,
                base_url=settings.ai.base_url,
                api_key=settings.ai.api_key,
                model=model,
            )
        )
    deepxiv = None
    if use_deepxiv:
        try:
            deepxiv = DeepXivClient()
        except Exception:
            deepxiv = None
    return settings, zotero, ai, deepxiv


def _resolve_collection(zotero: ZoteroClient, collection: Optional[str], collection_name: Optional[str]) -> Optional[str]:
    if collection:
        return collection
    if collection_name:
        resolved = zotero.resolve_collection_key(collection_name)
        if not resolved:
            raise SystemExit(f"Collection not found: {collection_name}")
        return resolved
    return None


def _collect_zotero_items(
    zotero: ZoteroClient,
    *,
    collection: Optional[str] = None,
    collection_name: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 100,
    recursive: bool = False,
) -> list[dict[str, Any]]:
    collection_key = _resolve_collection(zotero, collection, collection_name)
    if not collection_key:
        return list(zotero.iter_items(collection=None, tag=tag, limit=limit, top_only=True))
    if not recursive:
        return list(zotero.iter_items(collection=collection_key, tag=tag, limit=limit, top_only=True))

    out: list[dict[str, Any]] = []
    stack = [collection_key]
    seen: set[str] = set()
    while stack:
        key = stack.pop()
        if key in seen:
            continue
        seen.add(key)
        out.extend(list(zotero.iter_items(collection=key, tag=tag, limit=limit, top_only=True)))
        for child in zotero.list_child_collections(key):
            child_key = child.get("key")
            if child_key:
                stack.append(child_key)
    return out[:limit]


def _print_result(result) -> None:
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args(_cli_args())

    if args.command == "init":
        project = _project(args)
        service = LiteratureReviewService()
        _print_result(service.init_project(project))
        return

    if args.command == "build-pool":
        _, zotero, _, _ = _settings_and_clients(args)
        items = _collect_zotero_items(
            zotero,
            collection=args.collection,
            collection_name=args.collection_name,
            tag=args.tag,
            limit=args.limit,
            recursive=args.recursive,
        )
        service = LiteratureReviewService(zotero=zotero)
        _print_result(service.build_pool_from_zotero_items(_project(args), items))
        return

    if args.command == "read":
        _, zotero, ai, deepxiv = _settings_and_clients(args, need_ai=True, use_deepxiv=args.use_deepxiv)
        service = LiteratureReviewService(ai=ai, zotero=zotero, deepxiv=deepxiv)
        _print_result(
            service.read_and_code(
                _project(args),
                ReviewReadOptions(
                    limit=args.limit,
                    force=args.force,
                    locale=args.locale,
                    max_chars=args.max_chars,
                    use_deepxiv=args.use_deepxiv,
                    insert_zotero_notes=args.insert_zotero_notes,
                ),
            )
        )
        return

    if args.command == "draft":
        _, _, ai, _ = _settings_and_clients(args, need_ai=True)
        service = LiteratureReviewService(ai=ai)
        _print_result(service.draft_review(_project(args), locale=args.locale))
        return

    if args.command == "sync-zotero":
        _, zotero, _, _ = _settings_and_clients(args)
        service = LiteratureReviewService(zotero=zotero)
        _print_result(service.sync_reading_notes_to_zotero(_project(args)))
        return

    if args.command == "run":
        _, zotero, ai, deepxiv = _settings_and_clients(args, need_ai=True, use_deepxiv=args.use_deepxiv)
        project = _project(args)
        service = LiteratureReviewService(ai=ai, zotero=zotero, deepxiv=deepxiv)
        results = [service.init_project(project)]

        if args.watch_query or args.topic:
            watch_deepxiv = deepxiv
            if watch_deepxiv is None:
                try:
                    watch_deepxiv = DeepXivClient()
                except Exception:
                    watch_deepxiv = None
            watch = WatchService(zotero=zotero, deepxiv=watch_deepxiv)
            watch_result = watch.search_and_import(
                WatchOptions(
                    query=args.watch_query or args.topic,
                    limit=args.limit,
                    create_collections=args.create_collections or bool(args.collection_name),
                    collection_name=args.collection_name,
                    journals=args.journals,
                    prompt=args.prompt,
                    expand_queries=args.expand_queries,
                )
            )
            results.append(watch_result)
            managed_keys = watch_result.artifacts.get("managed_keys") or []
            items = [zotero.fetch_item(key) for key in managed_keys]
        else:
            items = []

        if not items:
            items = _collect_zotero_items(
                zotero,
                collection_name=args.collection_name,
                tag=args.tag,
                limit=args.limit,
            )
        results.append(service.build_pool_from_zotero_items(project, items))
        results.append(
            service.read_and_code(
                project,
                ReviewReadOptions(
                    limit=args.limit,
                    locale=args.locale,
                    max_chars=args.max_chars,
                    use_deepxiv=args.use_deepxiv,
                    insert_zotero_notes=args.insert_zotero_notes,
                ),
            )
        )
        results.append(service.draft_review(project, locale=args.locale))
        print(json.dumps({"success": all(r.failed == 0 for r in results), "stages": [r.__dict__ for r in results]}, ensure_ascii=False, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
