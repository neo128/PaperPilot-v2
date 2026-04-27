from __future__ import annotations

import datetime as dt
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional
import re

from pypdf import PdfReader

from paperpilot.clients.ai import AIClient
from paperpilot.clients.deepxiv import DeepXivClient
from paperpilot.clients.zotero import ZoteroClient
from paperpilot.models.results import StageResult


@dataclass
class SummaryOptions:
    max_pages: int = 12
    max_chars: int = 12000
    note_tag: str = "AI总结"
    force: bool = False
    locale: str = "zh"
    use_deepxiv: bool = False
    deepxiv_sections: tuple[str, ...] = ("Introduction", "Method", "Experiments")


def find_pdf_attachments(children: Iterable[dict[str, Any]]) -> List[dict[str, Any]]:
    pdfs: List[dict[str, Any]] = []
    for child in children:
        data = child.get("data", child)
        if data.get("itemType") != "attachment":
            continue
        filename = (data.get("filename") or "").lower()
        is_pdf = data.get("contentType") == "application/pdf" or filename.endswith(".pdf")
        if not is_pdf:
            continue
        if data.get("linkMode") not in {"imported_file", "linked_file", "imported_url"}:
            continue
        pdfs.append(data)
    return pdfs


def resolve_pdf_path(storage_root: Path, attachment: dict[str, Any]) -> Path:
    path_hint = attachment.get("path")
    if path_hint:
        if path_hint.startswith("storage:"):
            rel = path_hint.split("storage:", 1)[1].lstrip("/")
            return storage_root / rel
        return Path(path_hint).expanduser()
    key = attachment["key"]
    filename = attachment.get("filename") or "document.pdf"
    return storage_root / key / filename


def has_existing_ai_summary(zotero: ZoteroClient, parent_key: str, note_tag: Optional[str] = None) -> bool:
    try:
        children = zotero.fetch_children(parent_key)
    except Exception:
        return False
    for child in children:
        data = child.get("data", child)
        if data.get("itemType") != "note":
            continue
        note_html = data.get("note") or ""
        if "AI总结" in note_html or "豆包自动总结" in note_html:
            return True
        if note_tag:
            for tag in data.get("tags") or []:
                if (tag.get("tag") or "") == note_tag:
                    return True
    return False


def extract_pdf_text(path: Path, max_pages: int) -> str:
    reader = PdfReader(str(path))
    pages = reader.pages[: max_pages or len(reader.pages)]
    texts: List[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        texts.append(text.strip())
    return "\n\n".join(filter(None, texts))


def make_note_html(summary: str) -> str:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_text = html.escape(summary or "")
    return (
        f"<p><strong>AI总结</strong>（{timestamp}）</p>"
        f"<div data-markdown=\"true\" data-mime-type=\"text/markdown\" style=\"white-space:pre-wrap\">{safe_text}</div>"
    )


def normalize_arxiv_id(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    pattern = re.compile(
        r"(?P<id>(?:[a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?(?:\.pdf)?",
        re.I,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group("id")


def extract_arxiv_id(data: dict[str, Any]) -> Optional[str]:
    candidates = [data.get("url"), data.get("DOI"), data.get("archiveLocation")]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = normalize_arxiv_id(candidate)
        if normalized:
            return normalized
    archive = data.get("archive")
    location = data.get("archiveLocation")
    if archive and str(archive).lower() == "arxiv" and location:
        return normalize_arxiv_id(location) or str(location).strip()
    return None


class SummaryService:
    def __init__(self, zotero: Optional[ZoteroClient], ai: AIClient, storage_dir: Path, deepxiv: Optional[DeepXivClient] = None) -> None:
        self.zotero = zotero
        self.ai = ai
        self.storage_dir = storage_dir
        self.deepxiv = deepxiv

    def _build_deepxiv_context(self, arxiv_id: str, sections: tuple[str, ...]) -> str:
        assert self.deepxiv is not None
        parts: list[str] = []
        try:
            brief = self.deepxiv.brief(arxiv_id)
            if isinstance(brief, dict):
                parts.append(f"[Brief]\n{brief}")
        except Exception:
            pass
        try:
            head = self.deepxiv.head(arxiv_id)
            if isinstance(head, dict):
                parts.append(f"[Head]\n{head}")
        except Exception:
            pass
        for sec in sections:
            try:
                sec_data = self.deepxiv.section(arxiv_id, sec)
                parts.append(f"[Section: {sec}]\n{sec_data}")
            except Exception:
                continue
        return "\n\n".join(parts).strip()

    def summarize_local_pdfs(
        self,
        pdf_paths: list[Path],
        options: SummaryOptions,
        summary_dir: Optional[Path] = None,
    ) -> StageResult:
        result = StageResult(stage="summary")
        if summary_dir:
            summary_dir.mkdir(parents=True, exist_ok=True)
        for pdf_path in pdf_paths:
            result.processed += 1
            if not pdf_path.exists():
                result.failed += 1
                result.errors.append(f"Missing PDF: {pdf_path}")
                continue
            title = pdf_path.stem
            text = extract_pdf_text(pdf_path, options.max_pages)
            if not text:
                result.failed += 1
                result.errors.append(f"Empty extracted text: {pdf_path}")
                continue
            summary = self.ai.summarize_paper_excerpt(
                title=title,
                text=text,
                locale=options.locale,
                max_chars=options.max_chars,
            )
            if summary_dir:
                out_file = summary_dir / f"{pdf_path.stem}.summary.md"
                out_file.write_text(summary, encoding="utf-8")
                result.artifacts[str(pdf_path)] = str(out_file)
            result.created += 1
        return result

    def summarize_items(
        self,
        items: list[dict[str, Any]],
        options: SummaryOptions,
        insert_note: bool = True,
    ) -> StageResult:
        result = StageResult(stage="summary")
        for entry in items:
            data = entry.get("data", entry)
            result.processed += 1
            title = data.get("title") or data.get("shortTitle") or data.get("key")
            parent_key = data.get("key")
            note_parent_key = data.get("parentItem") or parent_key

            if self.zotero and not options.force and has_existing_ai_summary(self.zotero, note_parent_key, options.note_tag):
                result.skipped += 1
                continue

            created_for_item = False

            if options.use_deepxiv and self.deepxiv is not None:
                arxiv_id = extract_arxiv_id(data)
                if arxiv_id:
                    deepxiv_text = self._build_deepxiv_context(arxiv_id, options.deepxiv_sections)
                    if deepxiv_text:
                        summary = self.ai.summarize_paper_excerpt(
                            title=title,
                            text=deepxiv_text,
                            locale=options.locale,
                            max_chars=options.max_chars,
                        )
                        if insert_note and self.zotero:
                            self.zotero.create_note(note_parent_key, make_note_html(summary), tags=[options.note_tag])
                        result.created += 1
                        created_for_item = True

            if created_for_item:
                continue

            if data.get("itemType") == "attachment":
                pdfs = find_pdf_attachments([data])
            else:
                if not self.zotero:
                    result.failed += 1
                    result.errors.append(f"Zotero client required for parent item {parent_key}")
                    continue
                children = self.zotero.fetch_children(parent_key)
                pdfs = find_pdf_attachments(children)

            if not pdfs:
                abstract_text = (data.get("abstractNote") or data.get("abstract") or "").strip()
                if abstract_text:
                    summary = self.ai.summarize_paper_excerpt(
                        title=title,
                        text=abstract_text,
                        locale=options.locale,
                        max_chars=min(options.max_chars, 4000),
                    )
                    if insert_note and self.zotero:
                        self.zotero.create_note(note_parent_key, make_note_html(summary), tags=[options.note_tag])
                    result.created += 1
                    continue
                result.skipped += 1
                continue

            for attachment in pdfs:
                pdf_path = resolve_pdf_path(self.storage_dir, attachment)
                if not pdf_path.exists():
                    result.errors.append(f"Missing PDF: {pdf_path}")
                    continue
                text = extract_pdf_text(pdf_path, options.max_pages)
                if not text:
                    result.errors.append(f"Empty extracted text: {pdf_path}")
                    continue
                summary = self.ai.summarize_paper_excerpt(
                    title=title,
                    text=text,
                    locale=options.locale,
                    max_chars=options.max_chars,
                )
                if insert_note and self.zotero:
                    self.zotero.create_note(note_parent_key, make_note_html(summary), tags=[options.note_tag])
                result.created += 1
                created_for_item = True
            if not created_for_item:
                result.failed += 1
        return result
