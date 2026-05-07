"""Download PDFs from arXiv, summarize with AI, and save to SQLite.

Usage:
    python arxiv_summary.py --keys KEY1,KEY2,KEY3 [--limit N] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from paperpilot.clients.ai import AIClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.services.summary_service import (
    extract_arxiv_id,
    extract_pdf_text,
    has_existing_ai_summary,
    make_note_html,
)
from paperpilot.storage.paper_summary_store import PaperSummaryStore
from paperpilot.storage.summary_parser import extract_structured_fields
from paperpilot.utils.config import AISettings, load_app_settings

try:
    import requests
except ImportError:
    print("requests is required: pip install requests")
    sys.exit(1)


def download_arxiv_pdf(arxiv_id: str, dest: Path, timeout: int = 120) -> Path:
    """Download a PDF from arXiv."""
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    print(f"  Downloading {url} -> {dest}")
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv PDF download + AI summary pipeline")
    parser.add_argument("--keys", help="Comma-separated Zotero item keys (e.g. KEY1,KEY2)")
    parser.add_argument("--limit", type=int, default=10, help="Max items to process from all items if no --keys")
    parser.add_argument("--force", action="store_true", help="Re-summarize even if summary already exists")
    parser.add_argument("--download-dir", help="Where to save downloaded PDFs (default: .paperpilot/arxiv_pdfs/)")
    parser.add_argument("--storage-dir", help="Zotero storage dir override")
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--model", help="AI model override")
    parser.add_argument("--insert-note", action="store_true", help="Also write summary as Zotero note")
    parser.add_argument("--output-dir", default=".", help="Where to save markdown files (default: current dir)")
    args = parser.parse_args()

    settings = load_app_settings()
    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)
    ai = AIClient(
        AISettings(
            provider=settings.ai.provider,
            base_url=settings.ai.base_url,
            api_key=settings.ai.api_key,
            model=args.model or settings.ai.model,
        )
    )
    download_dir = Path(args.download_dir) if args.download_dir else Path(".paperpilot/arxiv_pdfs")
    summary_db = Path(".paperpilot/summaries.sqlite3")
    summary_db.parent.mkdir(parents=True, exist_ok=True)
    store = PaperSummaryStore(summary_db)

    # Collect items
    item_keys = [k.strip() for k in args.keys.split(",") if k.strip()] if args.keys else []
    items = []
    if item_keys:
        for key in item_keys:
            entry = zotero.fetch_item(key)
            if entry:
                items.append(entry)
    else:
        for entry in zotero.iter_items(collection=None, limit=args.limit, top_only=True):
            items.append(entry)

    print(f"Checking {len(items)} items...")
    stats = {"downloaded": 0, "skipped_existing": 0, "skipped_summary": 0, "summarized": 0, "failed": 0, "errors": []}

    for entry in items:
        data = entry.get("data", entry)
        key = data.get("key")
        title = data.get("title") or key
        print(f"\n[{key}] {title[:80]}")

        # Check if already summarized
        if not args.force and has_existing_ai_summary(zotero, key):
            print("  Skipped: already has AI summary note")
            stats["skipped_summary"] += 1
            continue

        # Extract arXiv ID
        arxiv_id = extract_arxiv_id(data)
        if not arxiv_id:
            print("  Failed: no arXiv ID found")
            stats["failed"] += 1
            stats["errors"].append(f"{key}: no arXiv ID")
            continue

        # Check if PDF already downloaded
        pdf_path = download_dir / f"{arxiv_id.replace('/', '_')}.pdf"
        if pdf_path.exists():
            print(f"  PDF already exists: {pdf_path}")
        else:
            try:
                download_arxiv_pdf(arxiv_id, pdf_path)
                stats["downloaded"] += 1
                print(f"  Downloaded: {pdf_path.name}")
            except Exception as e:
                print(f"  Failed to download: {e}")
                stats["failed"] += 1
                stats["errors"].append(f"{key}: download failed: {e}")
                continue

        # Extract text and summarize
        try:
            text = extract_pdf_text(pdf_path, args.max_pages)
        except Exception as e:
            print(f"  Failed to extract text: {e}")
            stats["failed"] += 1
            stats["errors"].append(f"{key}: text extraction failed: {e}")
            continue

        if not text.strip():
            print("  Failed: empty text after extraction")
            stats["failed"] += 1
            stats["errors"].append(f"{key}: empty text")
            continue

        print(f"  Extracted {len(text)} chars, calling AI...")
        try:
            summary = ai.summarize_paper_excerpt(
                title=title,
                text=text,
                locale="zh",
                max_chars=args.max_chars,
                model=args.model,
            )
        except Exception as e:
            print(f"  AI summar failed: {e}")
            stats["failed"] += 1
            stats["errors"].append(f"{key}: AI failed: {e}")
            continue

        # Save to SQLite
        fields = extract_structured_fields(
            summary,
            zotero_key=key,
            title_hint=title,
            locale="zh",
            model=args.model or settings.ai.model,
            source="arxiv",
        )
        fields["paper_id"] = f"summary_{key}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        from paperpilot.storage.paper_summary_store import PaperSummary
        store.save(PaperSummary(**fields))
        print(f"  Saved to SQLite")

        # Optionally write Zotero note
        if args.insert_note:
            try:
                zotero.create_note(key, make_note_html(summary), tags=["AI总结"])
                print(f"  Zotero note created")
            except Exception as e:
                print(f"  Zotero note failed: {e}")

        stats["summarized"] += 1

        # Save as markdown file with v2 naming convention
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_title = title[:50].replace("/", "_").replace("\\", "_")
        md_filename = f"AI总结-v2（{timestamp}）.md"
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / md_filename
        md_path.write_text(summary, encoding="utf-8")
        print(f"  Saved: {md_path}")

        # Rate limit between papers
        if len(items) > 1:
            print("  Waiting 5s before next paper...")
            time.sleep(5)

    print(f"\n{'='*60}")
    print(f"Done! Downloaded={stats['downloaded']}, Summarized={stats['summarized']}, "
          f"Skipped(summary)={stats['skipped_summary']}, Failed={stats['failed']}")
    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"]:
            print(f"  - {err}")

    store.close()


if __name__ == "__main__":
    main()
