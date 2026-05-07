from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from paperpilot.clients.zotero import ZoteroClient
from paperpilot.models.results import StageResult
from paperpilot.utils.config import load_app_settings
from paperpilot.utils.run_logging import log_stage_result


AI_NOTE_MARKERS = ("AI总结", "AI精读", "豆包自动总结", "PaperPilot AI总结", "PaperPilot AI精读")


def _cli_args() -> list[str]:
    args = list(sys.argv[1:])
    if args and args[0] == "zotero":
        return args[1:]
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zotero maintenance utilities for PaperPilot.")
    sub = parser.add_subparsers(dest="command")

    cleanup = sub.add_parser("cleanup-ai-notes", help="Delete old rich-text AI summary/reading notes from Zotero.")
    cleanup.add_argument("--after", required=True, help="Only match notes marked on/after this date, e.g. 2026-04-01.")
    cleanup.add_argument("--query", action="append", default=[], help="Zotero q search term; defaults to AI note markers.")
    cleanup.add_argument("--limit", type=int, default=100)
    cleanup.add_argument("--backup-dir", default=".paperpilot/cleanup-backups")
    cleanup.add_argument("--apply", action="store_true", help="Actually delete matching notes. Default is dry-run.")
    return parser.parse_args(_cli_args())


def _compact_cutoff(date_text: str) -> str:
    return date_text.replace("-", "")[:8]


def _marked_on_or_after(blob: str, *, date_added: str, cutoff: str) -> bool:
    compact_cutoff = _compact_cutoff(cutoff)
    dates = [
        match.replace("-", "")
        for match in re.findall(r"20\d{2}-?(?:0[1-9]|1[0-2])-?(?:[0-3]\d)", blob)
    ]
    if dates:
        return any(date >= compact_cutoff for date in dates)
    iso_cutoff = f"{cutoff[:10]}T00:00:00Z"
    return bool(date_added and date_added >= iso_cutoff)


def _note_preview(note_html: str, limit: int = 180) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", note_html or ""))
    return " ".join(text.split())[:limit]


def _find_ai_note_candidates(zotero: ZoteroClient, *, after: str, queries: list[str], limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in queries or list(AI_NOTE_MARKERS):
        for entry in zotero.search_items(query, limit=limit, top_only=False):
            data = entry.get("data") or entry
            key = str(entry.get("key") or data.get("key") or "")
            if not key or key in seen or data.get("itemType") != "note":
                continue
            seen.add(key)
            note_html = str(data.get("note") or "")
            tags = [str(tag.get("tag") or "") for tag in data.get("tags") or []]
            blob = note_html + "\n" + "\n".join(tags)
            if not any(marker in blob for marker in AI_NOTE_MARKERS):
                continue
            date_added = str(data.get("dateAdded") or entry.get("dateAdded") or "")
            if not _marked_on_or_after(blob, date_added=date_added, cutoff=after):
                continue
            candidates.append(
                {
                    "key": key,
                    "version": int(entry.get("version") or data.get("version") or 0),
                    "parent": data.get("parentItem"),
                    "dateAdded": date_added,
                    "dateModified": str(data.get("dateModified") or entry.get("dateModified") or ""),
                    "tags": tags,
                    "note_html": note_html,
                    "preview": _note_preview(note_html),
                }
            )
    return candidates


def cleanup_ai_notes(args: argparse.Namespace) -> StageResult:
    settings = load_app_settings(Path.cwd() / ".env" if (Path.cwd() / ".env").exists() else Path(__file__).resolve().parents[2] / ".env")
    zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key, timeout=60)
    result = StageResult(stage="zotero:cleanup-ai-notes")
    candidates = _find_ai_note_candidates(zotero, after=args.after, queries=args.query, limit=args.limit)
    result.processed = len(candidates)

    backup_dir = Path(args.backup_dir).expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"zotero_ai_notes_after_{args.after}_{suffix}.json"
    backup_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    result.artifacts["backup"] = str(backup_path)

    if not args.apply:
        result.skipped = len(candidates)
        result.artifacts["dry_run"] = True
        log_stage_result(result)
        return result

    for candidate in candidates:
        try:
            zotero.delete_item(str(candidate["key"]), int(candidate["version"]))
            result.created += 1
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{candidate['key']}: {exc}")

    report_path = backup_path.with_suffix(".report.json")
    report_path.write_text(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.artifacts["report"] = str(report_path)
    log_stage_result(result)
    return result


def main() -> None:
    args = parse_args()
    if args.command == "cleanup-ai-notes":
        result = cleanup_ai_notes(args)
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str))
        return
    raise SystemExit("Missing Zotero command. Try: cleanup-ai-notes")


if __name__ == "__main__":
    main()
