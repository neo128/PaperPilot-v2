from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from paperpilot.clients.ai import AIClient
from paperpilot.clients.open_access import OpenAccessClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.review_service import (
    LiteratureReviewService,
    ReviewCurateOptions,
    ReviewFetchPdfOptions,
    ReviewMatrixOptions,
    ReviewProject,
    ReviewQCOptions,
    ReviewReadOptions,
    ReviewVerifyOptions,
    slugify,
)
from paperpilot.services.watch_service import WatchOptions, WatchService
from paperpilot.storage.paper_summary_store import PaperSummaryStore
from paperpilot.utils.config import AISettings, load_app_settings

try:
    from paperpilot.clients.deepxiv import DeepXivClient
except ImportError:
    DeepXivClient = None  # type: ignore[misc,assignment]


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
    read.add_argument("--no-local-pdfs", action="store_true", help="Do not add project-local PDF text to reading context.")
    read.add_argument("--pdf-max-pages", type=int, default=12)
    read.add_argument("--paper-id", action="append", default=[], help="Read only a specific paper ID; repeatable.")
    read.add_argument("--model")
    read.add_argument("--summary-db-path", default=".paperpilot/summaries.sqlite3", help="SQLite DB for review AI reading cards and extracted facts.")
    read.add_argument("--summary-mode", choices=["canonical", "direct"], default="canonical", help="Use cached canonical AI summaries before review-specific reading.")
    read.add_argument("--force-summary", action="store_true", help="Regenerate canonical summaries before review reading.")
    read.add_argument("--force-read-pdf", action="store_true", help="Bypass canonical summaries and read available PDFs directly for review reading.")

    draft = sub.add_parser("draft", help="Draft review_v1.md from coded pool and reading cards")
    _add_project_args(draft)
    draft.add_argument("--locale", default="zh")
    draft.add_argument("--model")

    qc = sub.add_parser("qc", help="Run automated QC checks on coded pool, citations, and review draft")
    _add_project_args(qc)
    qc.add_argument("--draft-path", default="reports/review_draft.md", help="Draft path relative to project root, or an absolute path.")

    matrix = sub.add_parser("matrix", help="Build taxonomy and comparison matrices from the coded pool")
    _add_project_args(matrix)
    matrix.add_argument("--include-tier", action="append", default=[], help="Tier letter to include. Defaults to A, B, and C.")

    verify = sub.add_parser("verify", help="Build a full-text verification queue for core review papers")
    _add_project_args(verify)
    verify.add_argument("--include-tier", action="append", default=[], help="Tier letter to include. Defaults to A and B.")
    verify.add_argument("--skip-zotero", action="store_true", help="Do not inspect Zotero child attachments.")
    verify.add_argument("--storage-dir", help="Override local Zotero storage directory.")

    fetch_pdfs = sub.add_parser("fetch-pdfs", help="Fetch open-access PDFs for core review papers")
    _add_project_args(fetch_pdfs)
    fetch_pdfs.add_argument("--include-tier", action="append", default=[], help="Tier letter to include. Defaults to A and B.")
    fetch_pdfs.add_argument("--unpaywall-email", help="Email for Unpaywall DOI lookup. Defaults to UNPAYWALL_EMAIL.")
    fetch_pdfs.add_argument("--output-dir", help="PDF output directory. Defaults to data/interim/pdfs under the review project.")
    fetch_pdfs.add_argument("--attach-zotero", action="store_true", help="Create Zotero linked-url PDF attachments for discovered OA PDFs.")
    fetch_pdfs.add_argument("--dry-run", action="store_true", help="Discover OA PDFs without downloading or attaching.")
    fetch_pdfs.add_argument("--force", action="store_true", help="Redownload even if a local PDF already exists.")
    fetch_pdfs.add_argument("--limit", type=int, default=0)

    curate = sub.add_parser("curate", help="Curate coded pool and downgrade clearly off-topic papers to D")
    _add_project_args(curate)
    curate.add_argument("--apply", action="store_true", help="Also overwrite paper_pool_coded.csv with curated tier/score values.")
    curate.add_argument("--include-keyword", action="append", default=[], help="Extra positive domain keyword or comma-separated keywords.")
    curate.add_argument("--exclude-keyword", action="append", default=[], help="Extra off-topic keyword or comma-separated keywords.")
    curate.add_argument("--min-positive-hits", type=int, default=1)

    sync = sub.add_parser("sync-zotero", help="Write generated reading cards back to Zotero notes")
    _add_project_args(sync)
    sync.add_argument("--summary-db-path", default=".paperpilot/summaries.sqlite3", help="SQLite DB for synced reading cards and extracted facts.")

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
    run.add_argument("--no-local-pdfs", action="store_true", help="Do not add project-local PDF text to reading context.")
    run.add_argument("--pdf-max-pages", type=int, default=12)
    run.add_argument("--model")
    run.add_argument("--force-read", action="store_true", help="Regenerate reading cards and coded rows even when they already exist.")
    run.add_argument("--full", action="store_true", help="Run the full review automation chain around read/draft.")
    run.add_argument("--fetch-pdfs", action="store_true", help="Fetch open-access PDFs before AI reading.")
    run.add_argument("--verify", action="store_true", help="Build the full-text verification queue before AI reading.")
    run.add_argument("--curate", action="store_true", help="Curate the coded pool after AI reading.")
    run.add_argument("--matrix", action="store_true", help="Build taxonomy and comparison matrices after curation/read.")
    run.add_argument("--qc", action="store_true", help="Run QC after drafting.")
    run.add_argument("--apply-curation", action="store_true", help="Overwrite paper_pool_coded.csv with curated tier/score values.")
    run.add_argument("--include-keyword", action="append", default=[], help="Extra positive curation keyword or comma-separated keywords.")
    run.add_argument("--exclude-keyword", action="append", default=[], help="Extra off-topic curation keyword or comma-separated keywords.")
    run.add_argument("--min-positive-hits", type=int, default=1)
    run.add_argument("--fulltext-tier", action="append", default=[], help="Tier letter for fetch/verify targets. Defaults to A and B after coding, all papers before coding.")
    run.add_argument("--matrix-tier", action="append", default=[], help="Tier letter for matrix targets. Defaults to A, B, and C.")
    run.add_argument("--unpaywall-email", help="Email for Unpaywall DOI lookup. Defaults to UNPAYWALL_EMAIL.")
    run.add_argument("--fetch-output-dir", help="PDF output directory. Defaults to data/interim/pdfs under the review project.")
    run.add_argument("--attach-zotero-pdfs", action="store_true", help="Create Zotero linked-url PDF attachments for discovered OA PDFs.")
    run.add_argument("--fetch-dry-run", action="store_true", help="Discover OA PDFs without downloading or attaching.")
    run.add_argument("--fetch-force", action="store_true", help="Redownload PDFs even if a local PDF already exists.")
    run.add_argument("--fetch-limit", type=int, default=0)
    run.add_argument("--verify-skip-zotero", action="store_true", help="Do not inspect Zotero child attachments during verify.")
    run.add_argument("--storage-dir", help="Override local Zotero storage directory for verify.")
    run.add_argument("--qc-draft-path", default="reports/review_draft.md", help="Draft path for QC, relative to project root or absolute.")
    run.add_argument("--summary-db-path", default=".paperpilot/summaries.sqlite3", help="SQLite DB for all AI reading cards and extracted facts.")
    run.add_argument("--summary-mode", choices=["canonical", "direct"], default="canonical", help="Use cached canonical AI summaries before review-specific reading.")
    run.add_argument("--force-summary", action="store_true", help="Regenerate canonical summaries before review reading.")
    run.add_argument("--force-read-pdf", action="store_true", help="Bypass canonical summaries and read available PDFs directly for review reading.")
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


def _summary_store(args: argparse.Namespace) -> PaperSummaryStore:
    return PaperSummaryStore(Path(args.summary_db_path).expanduser())


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
        summary_store = _summary_store(args)
        service = LiteratureReviewService(ai=ai, zotero=zotero, deepxiv=deepxiv, summary_store=summary_store)
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
                    use_local_pdfs=not args.no_local_pdfs,
                    pdf_max_pages=args.pdf_max_pages,
                    paper_ids=tuple(args.paper_id),
                    summary_mode=args.summary_mode,
                    force_summary=args.force_summary,
                    force_read_pdf=args.force_read_pdf,
                ),
            )
        )
        summary_store.close()
        return

    if args.command == "draft":
        _, _, ai, _ = _settings_and_clients(args, need_ai=True)
        service = LiteratureReviewService(ai=ai)
        _print_result(service.draft_review(_project(args), locale=args.locale))
        return

    if args.command == "qc":
        service = LiteratureReviewService()
        _print_result(service.qc_review(_project(args), ReviewQCOptions(draft_path=args.draft_path)))
        return

    if args.command == "matrix":
        service = LiteratureReviewService()
        include_tiers = tuple(args.include_tier) if args.include_tier else ("A", "B", "C")
        _print_result(service.build_matrices(_project(args), ReviewMatrixOptions(include_tiers=include_tiers)))
        return

    if args.command == "verify":
        storage_dir = Path(args.storage_dir).expanduser() if args.storage_dir else None
        zotero = None
        if not args.skip_zotero:
            settings, zotero, _, _ = _settings_and_clients(args)
            storage_dir = storage_dir or settings.zotero.storage_dir
        service = LiteratureReviewService(zotero=zotero)
        include_tiers = tuple(args.include_tier) if args.include_tier else ("A", "B")
        _print_result(
            service.verify_fulltext(
                _project(args),
                ReviewVerifyOptions(
                    include_tiers=include_tiers,
                    check_zotero=not args.skip_zotero,
                    storage_dir=storage_dir,
                ),
            )
        )
        return

    if args.command == "fetch-pdfs":
        settings = None
        zotero = None
        if args.attach_zotero:
            settings, zotero, _, _ = _settings_and_clients(args)
        else:
            try:
                from paperpilot.utils.env import load_dotenv_if_present

                load_dotenv_if_present(".env")
            except Exception:
                pass
        email = args.unpaywall_email or os.environ.get("UNPAYWALL_EMAIL")
        include_tiers = tuple(args.include_tier) if args.include_tier else ("A", "B")
        output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
        service = LiteratureReviewService(zotero=zotero, open_access=OpenAccessClient(email=email))
        _print_result(
            service.fetch_open_access_pdfs(
                _project(args),
                ReviewFetchPdfOptions(
                    include_tiers=include_tiers,
                    email=email,
                    output_dir=output_dir,
                    attach_zotero=args.attach_zotero,
                    dry_run=args.dry_run,
                    force=args.force,
                    limit=args.limit,
                ),
            )
        )
        return

    if args.command == "curate":
        service = LiteratureReviewService()
        _print_result(
            service.curate_coded_pool(
                _project(args),
                ReviewCurateOptions(
                    apply=args.apply,
                    include_keywords=_keyword_args(args.include_keyword),
                    exclude_keywords=_keyword_args(args.exclude_keyword),
                    min_positive_hits=args.min_positive_hits,
                ),
            )
        )
        return

    if args.command == "sync-zotero":
        _, zotero, _, _ = _settings_and_clients(args)
        summary_store = _summary_store(args)
        service = LiteratureReviewService(zotero=zotero, summary_store=summary_store)
        _print_result(service.sync_reading_notes_to_zotero(_project(args)))
        summary_store.close()
        return

    if args.command == "run":
        settings, zotero, ai, deepxiv = _settings_and_clients(args, need_ai=True, use_deepxiv=args.use_deepxiv)
        project = _project(args)
        run_fetch_pdfs = args.full or args.fetch_pdfs
        run_verify = args.full or args.verify
        run_curate = args.full or args.curate
        run_matrix = args.full or args.matrix
        run_qc = args.full or args.qc
        open_access = None
        if run_fetch_pdfs:
            email = args.unpaywall_email or os.environ.get("UNPAYWALL_EMAIL")
            open_access = OpenAccessClient(email=email)
        summary_store = _summary_store(args)
        service = LiteratureReviewService(ai=ai, zotero=zotero, deepxiv=deepxiv, open_access=open_access, summary_store=summary_store)
        results = [service.init_project(project)]

        if args.watch_query or args.topic:
            watch_deepxiv = deepxiv if args.use_deepxiv else None
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
        fulltext_tiers = tuple(args.fulltext_tier) if args.fulltext_tier else ("A", "B")
        if run_fetch_pdfs:
            output_dir = Path(args.fetch_output_dir).expanduser() if args.fetch_output_dir else None
            results.append(
                service.fetch_open_access_pdfs(
                    project,
                    ReviewFetchPdfOptions(
                        include_tiers=fulltext_tiers,
                        email=args.unpaywall_email or os.environ.get("UNPAYWALL_EMAIL"),
                        output_dir=output_dir,
                        attach_zotero=args.attach_zotero_pdfs,
                        dry_run=args.fetch_dry_run,
                        force=args.fetch_force,
                        limit=args.fetch_limit,
                    ),
                )
            )
        if run_verify:
            storage_dir = Path(args.storage_dir).expanduser() if args.storage_dir else settings.zotero.storage_dir
            results.append(
                service.verify_fulltext(
                    project,
                    ReviewVerifyOptions(
                        include_tiers=fulltext_tiers,
                        check_zotero=not args.verify_skip_zotero,
                        storage_dir=storage_dir,
                    ),
                )
            )
        results.append(
            service.read_and_code(
                project,
                ReviewReadOptions(
                    limit=args.limit,
                    force=args.force_read,
                    locale=args.locale,
                    max_chars=args.max_chars,
                    use_deepxiv=args.use_deepxiv,
                    insert_zotero_notes=args.insert_zotero_notes,
                    use_local_pdfs=not args.no_local_pdfs,
                    pdf_max_pages=args.pdf_max_pages,
                    summary_mode=args.summary_mode,
                    force_summary=args.force_summary,
                    force_read_pdf=args.force_read_pdf,
                ),
            )
        )
        if run_curate:
            results.append(
                service.curate_coded_pool(
                    project,
                    ReviewCurateOptions(
                        apply=args.apply_curation,
                        include_keywords=_keyword_args(args.include_keyword),
                        exclude_keywords=_keyword_args(args.exclude_keyword),
                        min_positive_hits=args.min_positive_hits,
                    ),
                )
            )
        if run_matrix:
            matrix_tiers = tuple(args.matrix_tier) if args.matrix_tier else ("A", "B", "C")
            results.append(service.build_matrices(project, ReviewMatrixOptions(include_tiers=matrix_tiers)))
        results.append(service.draft_review(project, locale=args.locale))
        if run_qc:
            results.append(service.qc_review(project, ReviewQCOptions(draft_path=args.qc_draft_path)))
        print(json.dumps({"success": all(r.failed == 0 for r in results), "stages": [r.__dict__ for r in results]}, ensure_ascii=False, indent=2, default=str))
        summary_store.close()
        return

    parser.print_help()


def _keyword_args(values: list[str]) -> tuple[str, ...]:
    keywords: list[str] = []
    for value in values or []:
        keywords.extend(part.strip() for part in value.split(",") if part.strip())
    return tuple(keywords)


if __name__ == "__main__":
    main()
