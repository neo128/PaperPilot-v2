from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from paperpilot.clients.ai import AIClient
from paperpilot.clients.arxiv import ArxivClient
from paperpilot.clients.open_access import OpenAccessClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.models.results import StageResult
from paperpilot.services.summary_service import SummaryOptions, SummaryService
from paperpilot.services.summary_version import versioned_ai_summary_label
from paperpilot.storage.paper_summary_store import PaperSummaryStore
from paperpilot.utils.config import AISettings, load_app_settings
from paperpilot.utils.env import load_dotenv_if_present, optional_env
from paperpilot.utils.run_logging import log_stage_result

try:
    from paperpilot.clients.deepxiv import DeepXivClient
except ImportError:
    DeepXivClient = None  # type: ignore[misc,assignment]


def _cli_args() -> list[str]:
    """Strip subcommand name from sys.argv for use when called via main.py."""
    args = list(sys.argv[1:])
    if args and args[0] == "summary":
        args = args[1:]
    if args and args[0] == "attach":
        return args
    while args and not args[0].startswith("-"):
        args = args[1:]
    return args


def parse_args() -> argparse.Namespace:
    cli_args = _cli_args()
    if cli_args and cli_args[0] == "attach":
        parser = argparse.ArgumentParser(description="Attach local Markdown AI summaries to matching Zotero items.")
        parser.add_argument("command", choices=["attach"])
        parser.add_argument("--summary-dir", required=True, help="Directory containing *.summary.md files.")
        parser.add_argument("--mapping-csv", required=True, help="CSV with paper_id,zotero_key,title columns, e.g. bib/citation_keys.csv.")
        parser.add_argument("--glob", default="*.summary.md", help="Summary filename glob inside --summary-dir.")
        parser.add_argument("--content-type", default="text/markdown")
        parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip if a matching v2 Markdown attachment already exists.")
        parser.add_argument("--force", action="store_true", help="Upload even if a matching attachment already exists.")
        parser.add_argument("--dry-run", action="store_true", help="Preview uploads without writing to Zotero.")
        parser.add_argument("--report-path", help="Write JSON upload report to this path.")
        return parser.parse_args(cli_args)

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
    parser.add_argument("--figure-limit", type=int, default=0, help="Maximum extracted figures to insert; 0 means no fixed count limit.")
    parser.add_argument("--no-extract-figures", action="store_true", help="Do not extract and insert PDF figures into generated summaries.")
    parser.add_argument("--download-missing-pdfs", action="store_true", default=True, help="Download open-access PDFs when Zotero PDF attachments are missing or broken.")
    parser.add_argument("--no-download-missing-pdfs", dest="download_missing_pdfs", action="store_false", help="Do not download missing PDFs; fall back to abstracts when available.")
    parser.add_argument("--no-attach-downloaded-pdfs", action="store_true", help="Download PDFs locally but do not upload them back to Zotero.")
    parser.add_argument("--unpaywall-email", help="Email for Unpaywall DOI lookup. Defaults to UNPAYWALL_EMAIL.")
    parser.add_argument("--locale", default="zh")
    parser.add_argument("--model", help="Override AI model.")
    parser.add_argument("--use-deepxiv", action="store_true", help="Use DeepXiv as the preferred structured paper source before PDF fallback.")
    return parser.parse_args(cli_args)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_cli_env() -> None:
    """Load .env from cwd first, then the source checkout root as a fallback."""
    cwd_env = Path.cwd() / ".env"
    repo_env = _repo_root() / ".env"
    load_dotenv_if_present(cwd_env)
    if repo_env != cwd_env:
        load_dotenv_if_present(repo_env)


def _load_ai_settings(model_override: str | None = None) -> AISettings:
    _load_cli_env()
    return AISettings(
        provider=optional_env("AI_PROVIDER", "openai") or "openai",
        base_url=optional_env("AI_BASE_URL"),
        api_key=optional_env("AI_API_KEY") or optional_env("OPENAI_API_KEY"),
        model=model_override or optional_env("AI_MODEL"),
    )


def _paper_id_from_summary_path(path: Path) -> str:
    return path.name.split("_", 1)[0].removesuffix(".summary.md")


def _load_summary_mapping(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = {
            str(row.get("paper_id") or "").strip(): row
            for row in csv.DictReader(handle)
            if str(row.get("paper_id") or "").strip()
        }
    return rows


def _matching_summary_attachment(child: dict, *, filename: str, title: str) -> bool:
    data = child.get("data") or child
    tags = {str(tag.get("tag") or "") for tag in data.get("tags") or []}
    return (
        str(data.get("filename") or "") == filename
        or str(data.get("title") or "") == title
        or f"{versioned_ai_summary_label('AI总结')}-md" in tags
    )


def attach_local_summaries(args: argparse.Namespace) -> StageResult:
    env_file = Path.cwd() / ".env"
    if not env_file.exists():
        env_file = _repo_root() / ".env"
    settings = load_app_settings(env_file)
    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key, timeout=60)
    summary_dir = Path(args.summary_dir).expanduser()
    mapping = _load_summary_mapping(Path(args.mapping_csv).expanduser())
    result = StageResult(stage="summary:attach")
    report: list[dict[str, object]] = []

    for path in sorted(summary_dir.glob(args.glob)):
        result.processed += 1
        paper_id = _paper_id_from_summary_path(path)
        row = mapping.get(paper_id)
        if not row:
            result.skipped += 1
            report.append({"paper_id": paper_id, "path": str(path), "status": "missing_mapping"})
            continue
        zotero_key = str(row.get("zotero_key") or "").strip()
        title = str(row.get("title") or path.stem).strip()
        if not zotero_key:
            result.skipped += 1
            report.append({"paper_id": paper_id, "path": str(path), "status": "missing_zotero_key"})
            continue
        attachment_title = f"PaperPilot {versioned_ai_summary_label('AI总结')} Markdown - {title}"
        try:
            children = zotero.fetch_children(zotero_key)
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{paper_id}: fetch_children failed for {zotero_key}: {exc}")
            report.append({"paper_id": paper_id, "zotero_key": zotero_key, "status": "fetch_children_failed", "error": str(exc)})
            continue
        existing = next((child for child in children if _matching_summary_attachment(child, filename=path.name, title=attachment_title)), None)
        if existing and not args.force:
            result.skipped += 1
            existing_key = existing.get("key") or (existing.get("data") or {}).get("key")
            report.append({"paper_id": paper_id, "zotero_key": zotero_key, "status": "skipped_existing", "attachment_key": existing_key})
            continue
        if args.dry_run:
            result.skipped += 1
            report.append({"paper_id": paper_id, "zotero_key": zotero_key, "status": "dry_run", "path": str(path)})
            continue
        try:
            attachment_key = zotero.create_file_attachment(
                zotero_key,
                path,
                title=attachment_title,
                content_type=args.content_type,
                tags=[
                    "AI总结附件",
                    f"{versioned_ai_summary_label('AI总结')}-md",
                    "summary-kind:canonical",
                    "summary-mode:general",
                ],
            )
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{paper_id}: upload failed for {zotero_key}: {exc}")
            report.append({"paper_id": paper_id, "zotero_key": zotero_key, "status": "upload_failed", "error": str(exc), "path": str(path)})
            continue
        result.created += 1
        report.append({"paper_id": paper_id, "zotero_key": zotero_key, "status": "uploaded", "attachment_key": attachment_key, "path": str(path)})

    report_path = Path(args.report_path).expanduser() if args.report_path else summary_dir / "zotero_attach_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    result.artifacts["report"] = str(report_path)
    log_stage_result(result)
    return result


def main() -> None:
    args = parse_args()
    if getattr(args, "command", None) == "attach":
        result = attach_local_summaries(args)
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str))
        return

    zotero = None
    if args.pdf_path:
        ai_settings = _load_ai_settings(args.model)
        storage_dir = Path(args.storage_dir).expanduser() if args.storage_dir else (
            Path(optional_env("ZOTERO_STORAGE_DIR")).expanduser() if optional_env("ZOTERO_STORAGE_DIR") else Path.home() / "Zotero" / "storage"
        )
    else:
        env_file = Path.cwd() / ".env"
        if not env_file.exists():
            env_file = _repo_root() / ".env"
        settings = load_app_settings(env_file)
        storage_dir = Path(args.storage_dir).expanduser() if args.storage_dir else (settings.zotero.storage_dir or Path.home() / "Zotero" / "storage")
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
    open_access = OpenAccessClient(email=args.unpaywall_email or os.environ.get("UNPAYWALL_EMAIL")) if args.download_missing_pdfs else None
    arxiv = ArxivClient(timeout=30) if args.download_missing_pdfs else None
    service = SummaryService(
        zotero,
        ai,
        storage_dir,
        deepxiv=deepxiv,
        summary_store=summary_store,
        open_access=open_access,
        arxiv=arxiv,
    )

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
                extract_figures=not args.no_extract_figures,
                figure_limit=args.figure_limit,
                download_missing_pdfs=False,
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
                    items.extend(list(zotero.iter_items(collection=key, tag=args.tag, limit=args.limit, top_only=True)))
            else:
                items = list(zotero.iter_items(collection=None, tag=args.tag, limit=args.limit, top_only=True))

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
                extract_figures=not args.no_extract_figures,
                figure_limit=args.figure_limit,
                download_missing_pdfs=args.download_missing_pdfs,
                attach_downloaded_pdfs=not args.no_attach_downloaded_pdfs,
            ),
            insert_note=(args.insert_note or not args.pdf_path) and not args.no_zotero_attachment,
        )
    print(
        f"summary done, processed={result.processed}, created={result.created}, skipped={result.skipped}, failed={result.failed}"
    )
    log_stage_result(result)
    if result.errors:
        print("errors:")
        for err in result.errors:
            print(f"- {err}")
    summary_store.close()


if __name__ == "__main__":
    main()
