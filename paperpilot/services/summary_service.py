from __future__ import annotations

import datetime as dt
from datetime import timezone
import base64
import hashlib
import html
import logging
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional
import re

from pypdf import PdfReader

from paperpilot.clients.ai import AIClient
from paperpilot.clients.arxiv import ArxivClient
from paperpilot.clients.open_access import OpenAccessClient
from paperpilot.clients.zotero import ZoteroClient

try:
    from paperpilot.clients.deepxiv import DeepXivClient
except ImportError:
    DeepXivClient = None  # type: ignore[misc,assignment]
from paperpilot.models.results import StageResult
from paperpilot.services.markdown_render import render_markdown_html
from paperpilot.services.summary_version import AI_SUMMARY_VERSION, versioned_ai_summary_label
from paperpilot.storage.paper_summary_store import PaperSummary, PaperSummaryFact, PaperSummaryFigure, PaperSummaryStore
from paperpilot.storage.summary_parser import extract_structured_fields, extract_summary_facts


logger = logging.getLogger(__name__)


@dataclass
class SummaryOptions:
    max_pages: int = 12
    max_chars: int = 12000
    note_tag: str = "AI总结"
    force: bool = False
    locale: str = "zh"
    use_deepxiv: bool = False
    deepxiv_sections: tuple[str, ...] = ("Introduction", "Method", "Experiments")
    mode: str = "general"
    attach_zotero: bool = True
    extract_figures: bool = True
    figure_limit: int = 0
    download_missing_pdfs: bool = False
    attach_downloaded_pdfs: bool = True


@dataclass
class ExtractedFigure:
    file_path: Path
    page: int
    caption: str
    figure_type: str = "figure"
    relevance: str = "candidate"


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_key_from_metadata(data: dict[str, Any], title_hint: str = "") -> str:
    doi = str(data.get("DOI") or data.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    arxiv_id = extract_arxiv_id(data)
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower()}"
    title = str(data.get("title") or data.get("shortTitle") or title_hint or "").strip().lower()
    title = re.sub(r"\s+", " ", title)
    return f"title:{title}" if title else ""


def _safe_asset_key(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("_")
    return text[:120] or "paper"


def _caption_for_page(page_text: str) -> str:
    for line in (page_text or "").splitlines():
        cleaned = " ".join(line.strip().split())
        if re.match(r"^(fig(?:ure)?|table)\s*\\d*", cleaned, re.I):
            return cleaned[:300]
    return ""


def _figure_type_from_caption(caption: str) -> str:
    lowered = (caption or "").lower()
    if "table" in lowered:
        return "table"
    if any(token in lowered for token in ["architecture", "framework", "pipeline", "overview", "method", "system"]):
        return "architecture"
    if any(token in lowered for token in ["result", "comparison", "performance", "accuracy"]):
        return "result"
    return "figure"


def _normalized_title_for_match(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return " ".join(text.split())


def _titles_match(left: str, right: str) -> bool:
    left_norm = _normalized_title_for_match(left)
    right_norm = _normalized_title_for_match(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


def _mime_for_image(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "image/png"


def _image_markdown(figure: ExtractedFigure, index: int, *, embed: bool = False) -> list[str]:
    caption = figure.caption or f"Candidate figure extracted from page {figure.page}"
    image_ref = str(figure.file_path)
    if embed and figure.file_path.exists():
        encoded = base64.b64encode(figure.file_path.read_bytes()).decode("ascii")
        image_ref = f"data:{_mime_for_image(figure.file_path)};base64,{encoded}"
    return [
        "",
        f"> **图表 {index}（第 {figure.page} 页，{figure.figure_type}）**：{caption}",
        f"![图表 {index}]({image_ref})",
        "",
    ]


def _figure_heading_keywords(figure: ExtractedFigure) -> tuple[str, ...]:
    figure_type = (figure.figure_type or "").lower()
    caption = (figure.caption or "").lower()
    if figure_type in {"architecture", "figure"} and any(token in caption for token in ["architecture", "framework", "pipeline", "overview", "method", "system"]):
        return ("方法", "技术", "模型", "架构", "路线", "method", "approach", "architecture")
    if figure_type in {"result", "table"} or any(token in caption for token in ["result", "comparison", "performance", "accuracy", "table"]):
        return ("实验", "结果", "评估", "性能", "对比", "experiment", "result", "evaluation")
    if any(token in caption for token in ["dataset", "benchmark", "data"]):
        return ("数据", "基准", "实验", "dataset", "benchmark")
    return ("方法", "实验", "结果", "总结", "method", "result")


def make_note_html(summary: str) -> str:
    """Convert markdown summary to HTML suitable for Zotero rich-text notes."""
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = dt.datetime.now().strftime(f"{versioned_ai_summary_label('AI总结')}（%Y%m%d-%H%M%S）")
    body = render_markdown_html(summary or "")
    return (
        f"<h1>{html.escape(title)}</h1>"
        f"<p><strong>AI总结版本：</strong>{html.escape(AI_SUMMARY_VERSION)}</p>"
        f"<div style=\"line-height:1.5; font-size:12px\">{body}</div>"
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
    def __init__(
        self,
        zotero: Optional[ZoteroClient],
        ai: AIClient,
        storage_dir: Path,
        deepxiv: Optional[DeepXivClient] = None,
        summary_store: Optional[PaperSummaryStore] = None,
        open_access: Optional[OpenAccessClient] = None,
        arxiv: Optional[ArxivClient] = None,
    ) -> None:
        self.zotero = zotero
        self.ai = ai
        self.storage_dir = storage_dir
        self.deepxiv = deepxiv
        self.summary_store = summary_store
        self.open_access = open_access
        self.arxiv = arxiv

    def _save_to_store(
        self,
        summary: str,
        *,
        zotero_key: str,
        title: str,
        locale: str = "zh",
        model: Optional[str] = None,
        source: Optional[str] = None,
        summary_kind: str = "canonical",
        review_slug: Optional[str] = None,
        pdf_hash: Optional[str] = None,
        canonical_key: Optional[str] = None,
        summary_profile: Optional[str] = None,
        source_priority: Optional[int] = None,
        stale_reason: Optional[str] = None,
        figures: Optional[list[ExtractedFigure]] = None,
    ) -> Optional[str]:
        if not self.summary_store or not summary:
            return None
        fields = extract_structured_fields(
            summary,
            zotero_key=zotero_key,
            title_hint=title,
            locale=locale,
            model=model,
            source=source,
        )
        fields["paper_id"] = f"summary_{zotero_key}_{dt.datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        fields["summary_version"] = AI_SUMMARY_VERSION
        fields["summary_kind"] = summary_kind
        fields["review_slug"] = review_slug
        fields["pdf_hash"] = pdf_hash
        fields["canonical_key"] = canonical_key or (f"zotero:{zotero_key}" if zotero_key else "")
        fields["summary_profile"] = summary_profile
        fields["source_priority"] = source_priority
        fields["stale_reason"] = stale_reason
        facts = [
            PaperSummaryFact(paper_id=fields["paper_id"], **fact)
            for fact in extract_summary_facts(
                summary,
                zotero_key=zotero_key,
                title_hint=title,
                source=source,
                summary_version=AI_SUMMARY_VERSION,
            )
        ]
        figure_rows = [
            PaperSummaryFigure(
                paper_id=fields["paper_id"],
                zotero_key=zotero_key,
                title=fields.get("title") or title,
                figure_index=index,
                page=figure.page,
                file_path=str(figure.file_path),
                caption=figure.caption,
                figure_type=figure.figure_type,
                relevance=figure.relevance,
                summary_version=AI_SUMMARY_VERSION,
            )
            for index, figure in enumerate(figures or [], start=1)
        ]
        self.summary_store.save(PaperSummary(**fields), facts=facts, figures=figure_rows)
        return str(fields["paper_id"])

    def _cached_canonical(self, *, zotero_key: str, canonical_key: str, pdf_hash: Optional[str], options: SummaryOptions) -> Optional[PaperSummary]:
        if not self.summary_store or options.force:
            return None
        return self.summary_store.get_valid_canonical(
            zotero_key=zotero_key,
            canonical_key=canonical_key,
            summary_version=AI_SUMMARY_VERSION,
            pdf_hash=pdf_hash,
        )

    def _cached_by_canonical_key(self, *, canonical_key: str, pdf_hash: Optional[str] = None) -> Optional[PaperSummary]:
        if not self.summary_store or not canonical_key:
            return None
        return self.summary_store.get_valid_canonical(
            canonical_key=canonical_key,
            summary_version=AI_SUMMARY_VERSION,
            pdf_hash=pdf_hash,
        )

    def _reuse_summary_for_item(
        self,
        *,
        cached: PaperSummary,
        note_parent_key: str,
        title: str,
        options: SummaryOptions,
        insert_note: bool,
    ) -> bool:
        summary_md = cached.full_summary_md or ""
        if not summary_md:
            return False
        if insert_note and options.attach_zotero:
            self._write_summary_attachment(note_parent_key, summary_md, title=title, mode=options.mode, replace_existing=options.force)
        logger.info(
            "summary: reused canonical summary item_key=%s source_zotero_key=%s canonical_key=%s",
            note_parent_key,
            cached.zotero_key,
            cached.canonical_key,
        )
        return True

    def _markdown_with_embedded_local_images(self, summary_md: str) -> str:
        def repl(match: re.Match[str]) -> str:
            alt = match.group("alt")
            target = match.group("target").strip()
            if target.startswith(("http://", "https://", "data:", "zotero://")):
                return match.group(0)
            image_path = Path(target).expanduser()
            if not image_path.is_absolute():
                image_path = Path.cwd() / image_path
            if not image_path.exists() or not image_path.is_file():
                return match.group(0)
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            return f"![{alt}](data:{_mime_for_image(image_path)};base64,{encoded})"

        return re.sub(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)", repl, summary_md)

    def _write_summary_attachment(
        self,
        parent_key: str,
        summary_md: str,
        *,
        title: str,
        mode: str = "general",
        replace_existing: bool = False,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        if not self.zotero or not parent_key or not summary_md:
            return False, None, None
        create_file_attachment = getattr(self.zotero, "create_file_attachment", None)
        if not callable(create_file_attachment):
            self.zotero.create_note(parent_key, make_note_html(summary_md), tags=[versioned_ai_summary_label("AI总结")])
            return True, None, versioned_ai_summary_label("AI总结")
        attachment_dir = Path(".paperpilot-zotero-attachments") / "canonical"
        attachment_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", title or parent_key).strip("_") or parent_key
        md_path = attachment_dir / f"{stem}_{AI_SUMMARY_VERSION}.md"
        attachment_md = self._markdown_with_embedded_local_images(summary_md)
        md_path.write_text(attachment_md, encoding="utf-8")
        attachment_title = f"PaperPilot {versioned_ai_summary_label('AI总结')} Markdown - {title or parent_key}"
        try:
            for child in self.zotero.fetch_children(parent_key):
                data = child.get("data") or child
                tags = {str(tag.get("tag") or "") for tag in data.get("tags") or []}
                if (
                    str(data.get("filename") or "") == md_path.name
                    or str(data.get("title") or "") == attachment_title
                    or f"{versioned_ai_summary_label('AI总结')}-md" in tags
                ):
                    existing_key = child.get("key") or data.get("key")
                    if not replace_existing:
                        return True, existing_key, attachment_title
                    delete_item = getattr(self.zotero, "delete_item", None)
                    version = child.get("version") or data.get("version")
                    if callable(delete_item) and existing_key and version is not None:
                        delete_item(existing_key, int(version))
                    break
        except Exception:
            logger.debug("summary: failed to inspect existing Zotero summary attachments", exc_info=True)
        attachment_key = create_file_attachment(
            parent_key,
            md_path,
            title=attachment_title,
            content_type="text/markdown",
            tags=["AI总结附件", f"{versioned_ai_summary_label('AI总结')}-md", f"summary-mode:{mode}"],
        )
        return True, attachment_key, attachment_title

    def _figure_asset_root(self) -> Path:
        if self.summary_store is not None:
            return self.summary_store.db_path.parent / "summary-assets"
        return Path(".paperpilot") / "summary-assets"

    def _downloaded_pdf_root(self) -> Path:
        if self.summary_store is not None:
            return self.summary_store.db_path.parent / "downloaded-pdfs"
        return Path(".paperpilot") / "downloaded-pdfs"

    def _downloaded_pdf_destination(self, *, parent_key: str, title: str, metadata: dict[str, Any]) -> Path:
        canonical_key = canonical_key_from_metadata(metadata, title) or f"zotero:{parent_key}"
        paper_dir = self._downloaded_pdf_root() / _safe_asset_key(parent_key or canonical_key)
        filename = f"{_safe_asset_key(title or canonical_key)}.pdf"
        return paper_dir / filename

    def _summary_metadata(self, data: dict[str, Any], note_parent_key: str) -> dict[str, Any]:
        if data.get("itemType") != "attachment":
            return data
        if not self.zotero or not note_parent_key:
            return data
        try:
            parent = self.zotero.fetch_item(note_parent_key)
        except Exception:
            logger.debug("summary: failed to fetch parent metadata for attachment parent_key=%s", note_parent_key, exc_info=True)
            return data
        parent_data = parent.get("data") or parent
        return parent_data if isinstance(parent_data, dict) else data

    def _attach_downloaded_pdf(self, parent_key: str, pdf_path: Path, *, title: str) -> None:
        if not self.zotero or not parent_key or not pdf_path.exists():
            return
        expected_title = f"PaperPilot downloaded PDF - {title or pdf_path.stem}"
        try:
            for child in self.zotero.fetch_children(parent_key):
                data = child.get("data") or child
                if (
                    data.get("itemType") == "attachment"
                    and (
                        str(data.get("filename") or "") == pdf_path.name
                        or str(data.get("title") or "") == expected_title
                    )
                ):
                    return
        except Exception:
            logger.debug("summary: failed to inspect existing downloaded PDF attachments", exc_info=True)
        create_file_attachment = getattr(self.zotero, "create_file_attachment", None)
        if callable(create_file_attachment):
            create_file_attachment(
                parent_key,
                pdf_path,
                title=expected_title,
                content_type="application/pdf",
                tags=["PaperPilot下载PDF", "summary-source:open-access"],
            )

    def _download_missing_pdf(
        self,
        *,
        parent_key: str,
        title: str,
        metadata: dict[str, Any],
        options: SummaryOptions,
    ) -> tuple[Optional[Path], str]:
        if not options.download_missing_pdfs or self.open_access is None:
            return None, "disabled"
        destination = self._downloaded_pdf_destination(parent_key=parent_key, title=title, metadata=metadata)
        if destination.exists():
            logger.info("summary: using previously downloaded PDF item_key=%s path=%s", parent_key, destination)
            if options.attach_zotero and options.attach_downloaded_pdfs:
                self._attach_downloaded_pdf(parent_key, destination, title=title)
            return destination, "local_download_cache"
        doi = str(metadata.get("DOI") or metadata.get("doi") or "").strip()
        arxiv_id = extract_arxiv_id(metadata) or ""
        if not arxiv_id and not doi and self.arxiv is not None and title:
            try:
                candidates = self.arxiv.search(title, limit=5, sort_by="relevance")
            except Exception as exc:
                logger.warning("summary: arXiv title lookup failed title=%s error=%s", title, exc)
                candidates = []
            for candidate in candidates:
                candidate_title = str(candidate.get("title") or "")
                candidate_arxiv_id = str(candidate.get("arxiv_id") or "").strip()
                if candidate_arxiv_id and _titles_match(title, candidate_title):
                    arxiv_id = normalize_arxiv_id(candidate_arxiv_id) or candidate_arxiv_id
                    logger.info(
                        "summary: resolved missing PDF by arXiv title search item_key=%s arxiv_id=%s title=%s",
                        parent_key,
                        arxiv_id,
                        candidate_title,
                    )
                    break
        lookup = self.open_access.find_pdf(doi=doi, arxiv_id=arxiv_id)
        if lookup.status != "found" or not lookup.pdf_url:
            return None, lookup.status or "not_found"
        downloaded = self.open_access.download_pdf(lookup.pdf_url, destination, force=options.force)
        if options.attach_zotero and options.attach_downloaded_pdfs:
            self._attach_downloaded_pdf(parent_key, downloaded, title=title)
        logger.info(
            "summary: downloaded missing PDF item_key=%s source=%s path=%s",
            parent_key,
            lookup.source,
            downloaded,
        )
        return downloaded, lookup.source or "open_access"

    def _extract_key_figures(self, pdf_path: Path, canonical_key: str, limit: int) -> list[ExtractedFigure]:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception:
            return []
        asset_dir = self._figure_asset_root() / _safe_asset_key(canonical_key or pdf_path.stem)
        asset_dir.mkdir(parents=True, exist_ok=True)
        figures: list[ExtractedFigure] = []
        for page_index, page in enumerate(reader.pages, start=1):
            if limit > 0 and len(figures) >= limit:
                break
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            caption = _caption_for_page(page_text)
            try:
                images = list(page.images)
            except Exception:
                continue
            for image_index, image in enumerate(images, start=1):
                if limit > 0 and len(figures) >= limit:
                    break
                name = getattr(image, "name", "") or f"image_{image_index}.png"
                suffix = Path(name).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
                    suffix = ".png"
                out_path = asset_dir / f"fig_{len(figures) + 1:03d}_p{page_index:03d}{suffix}"
                try:
                    pil_image = getattr(image, "image", None)
                    if pil_image is not None:
                        width, height = getattr(pil_image, "size", (0, 0))
                        if width < 160 or height < 120 or width * height < 30000:
                            continue
                        pil_image.save(out_path)
                    else:
                        data = getattr(image, "data", b"")
                        if not data:
                            continue
                        out_path.write_bytes(data)
                except Exception:
                    continue
                if out_path.exists() and out_path.stat().st_size > 0:
                    figures.append(
                        ExtractedFigure(
                            file_path=out_path,
                            page=page_index,
                            caption=caption,
                            figure_type=_figure_type_from_caption(caption),
                        )
                    )
        return figures

    def _inject_figures_section(self, summary_md: str, figures: list[ExtractedFigure]) -> str:
        if not figures:
            return summary_md
        lines = summary_md.rstrip().splitlines()
        insertions: dict[int, list[str]] = {}
        deferred: list[tuple[int, ExtractedFigure]] = []
        heading_indexes = [
            (idx, line)
            for idx, line in enumerate(lines)
            if re.match(r"^#{1,4}\s+", line.strip())
        ]

        for figure_index, figure in enumerate(figures, start=1):
            keywords = _figure_heading_keywords(figure)
            target_index: Optional[int] = None
            for idx, heading in heading_indexes:
                lowered = heading.lower()
                if any(keyword.lower() in lowered for keyword in keywords):
                    target_index = idx + 1
                    break
            if target_index is None:
                deferred.append((figure_index, figure))
            else:
                insertions.setdefault(target_index, []).extend(_image_markdown(figure, figure_index))

        out: list[str] = []
        for idx, line in enumerate(lines):
            out.append(line)
            if idx + 1 in insertions:
                out.extend(insertions[idx + 1])

        if deferred:
            out.extend(["", "## 图表补充"])
            for figure_index, figure in deferred:
                out.extend(_image_markdown(figure, figure_index))
        return "\n".join(out).rstrip() + "\n"

    def summarize_text(
        self,
        *,
        title: str,
        text: str,
        zotero_key: str,
        options: SummaryOptions,
        source: str,
        canonical_key: str = "",
        pdf_hash: Optional[str] = None,
        pdf_path: Optional[Path] = None,
        insert_attachment: bool = False,
    ) -> str:
        canonical_key = canonical_key or (f"zotero:{zotero_key}" if zotero_key else "")
        cached = self._cached_canonical(zotero_key=zotero_key, canonical_key=canonical_key, pdf_hash=pdf_hash, options=options)
        if cached and cached.full_summary_md:
            return cached.full_summary_md
        summary = self.ai.summarize_paper_excerpt(
            title=title,
            text=text,
            locale=options.locale,
            max_chars=options.max_chars,
            mode=options.mode,
        )
        figures = (
            self._extract_key_figures(pdf_path, canonical_key, options.figure_limit)
            if options.extract_figures and pdf_path is not None
            else []
        )
        summary = self._inject_figures_section(summary, figures)
        paper_id = self._save_to_store(
            summary,
            zotero_key=zotero_key,
            title=title,
            locale=options.locale,
            source=source,
            summary_kind="canonical",
            pdf_hash=pdf_hash,
            canonical_key=canonical_key,
            summary_profile=options.mode,
            source_priority={"pdf": 30, "deepxiv": 20, "abstract": 10, "text": 5}.get(source, 0),
            figures=figures,
        )
        if insert_attachment and options.attach_zotero:
            ok, attachment_key, attachment_title = self._write_summary_attachment(
                zotero_key,
                summary,
                title=title,
                mode=options.mode,
                replace_existing=options.force,
            )
            if paper_id and self.summary_store:
                self.summary_store.update_attachment_status(
                    paper_id,
                    attachment_key=attachment_key,
                    attachment_title=attachment_title,
                    status="uploaded" if ok else "failed",
                )
        return summary

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
        started = time.monotonic()
        result = StageResult(stage="summary")
        logger.info("summary: starting local PDF summaries count=%d summary_dir=%s", len(pdf_paths), summary_dir)
        if summary_dir:
            summary_dir.mkdir(parents=True, exist_ok=True)
        for pdf_path in pdf_paths:
            result.processed += 1
            logger.info("summary: processing local PDF path=%s", pdf_path)
            if not pdf_path.exists():
                result.failed += 1
                result.errors.append(f"Missing PDF: {pdf_path}")
                logger.error("summary: missing PDF path=%s", pdf_path)
                continue
            title = pdf_path.stem
            pdf_hash = file_sha256(pdf_path)
            canonical_key = f"pdf:{pdf_hash}"
            cached = self._cached_canonical(zotero_key=title, canonical_key=canonical_key, pdf_hash=pdf_hash, options=options)
            if cached and cached.full_summary_md:
                logger.info("summary: using cached canonical summary title=%s pdf_hash=%s", title, pdf_hash[:12])
                if summary_dir:
                    out_file = summary_dir / f"{pdf_path.stem}.summary.md"
                    out_file.write_text(cached.full_summary_md, encoding="utf-8")
                    result.artifacts[str(pdf_path)] = str(out_file)
                result.skipped += 1
                continue
            text = extract_pdf_text(pdf_path, options.max_pages)
            if not text:
                result.failed += 1
                result.errors.append(f"Empty extracted text: {pdf_path}")
                logger.error("summary: empty extracted text path=%s", pdf_path)
                continue
            logger.info("summary: extracted text chars=%d title=%s", len(text), title)
            summary = self.summarize_text(
                title=title,
                text=text,
                zotero_key=title,
                options=options,
                source="pdf",
                canonical_key=canonical_key,
                pdf_hash=pdf_hash,
                pdf_path=pdf_path,
                insert_attachment=False,
            )
            if summary_dir:
                out_file = summary_dir / f"{pdf_path.stem}.summary.md"
                out_file.write_text(summary, encoding="utf-8")
                result.artifacts[str(pdf_path)] = str(out_file)
                logger.info("summary: wrote markdown summary path=%s", out_file)
            result.created += 1
        result.duration_sec = round(time.monotonic() - started, 3)
        logger.info(
            "summary: finished local PDFs processed=%d created=%d skipped=%d failed=%d duration_sec=%.3f",
            result.processed,
            result.created,
            result.skipped,
            result.failed,
            result.duration_sec,
        )
        return result

    def summarize_items(
        self,
        items: list[dict[str, Any]],
        options: SummaryOptions,
        insert_note: bool = True,
    ) -> StageResult:
        started = time.monotonic()
        result = StageResult(stage="summary")
        logger.info("summary: starting Zotero item summaries count=%d insert_note=%s", len(items), insert_note)
        seen_parent_keys: set[str] = set()
        regenerated_canonical_keys: set[str] = set()
        for entry in items:
            data = entry.get("data", entry)
            result.processed += 1
            title = data.get("title") or data.get("shortTitle") or data.get("key")
            logger.info("summary: processing item key=%s title=%s", data.get("key"), title)
            parent_key = data.get("key")
            note_parent_key = data.get("parentItem") or parent_key
            if note_parent_key in seen_parent_keys:
                result.skipped += 1
                logger.info("summary: duplicate parent in input, skipping item key=%s parent_key=%s", data.get("key"), note_parent_key)
                continue
            seen_parent_keys.add(note_parent_key)
            metadata = self._summary_metadata(data, note_parent_key)
            title = metadata.get("title") or metadata.get("shortTitle") or title
            canonical_key = canonical_key_from_metadata(metadata, title)

            if self.zotero and not options.force and has_existing_ai_summary(self.zotero, note_parent_key, options.note_tag):
                result.skipped += 1
                logger.info("summary: existing AI summary found, skipping item key=%s", note_parent_key)
                continue

            created_for_item = False
            can_reuse_before_read = (not options.force) or (canonical_key in regenerated_canonical_keys)
            if can_reuse_before_read:
                cached_by_key = self._cached_by_canonical_key(canonical_key=canonical_key)
                if cached_by_key and self._reuse_summary_for_item(
                    cached=cached_by_key,
                    note_parent_key=note_parent_key,
                    title=title,
                    options=options,
                    insert_note=insert_note,
                ):
                    result.skipped += 1
                    continue

            if options.use_deepxiv and self.deepxiv is not None:
                arxiv_id = extract_arxiv_id(metadata)
                if arxiv_id:
                    deepxiv_text = self._build_deepxiv_context(arxiv_id, options.deepxiv_sections)
                    if deepxiv_text:
                        summary = self.ai.summarize_paper_excerpt(
                            title=title,
                            text=deepxiv_text,
                            locale=options.locale,
                            max_chars=options.max_chars,
                            mode=options.mode,
                        )
                        paper_id = self._save_to_store(
                            summary,
                            zotero_key=note_parent_key,
                            title=title,
                            locale=options.locale,
                            source="deepxiv",
                            summary_kind="canonical",
                            canonical_key=canonical_key,
                            summary_profile=options.mode,
                            source_priority=20,
                        )
                        if insert_note and options.attach_zotero:
                            ok, attachment_key, attachment_title = self._write_summary_attachment(
                                note_parent_key,
                                summary,
                                title=title,
                                mode=options.mode,
                                replace_existing=options.force,
                            )
                            if paper_id and self.summary_store:
                                self.summary_store.update_attachment_status(
                                    paper_id,
                                    attachment_key=attachment_key,
                                    attachment_title=attachment_title,
                                    status="uploaded" if ok else "failed",
                                )
                        result.created += 1
                        created_for_item = True
                        if canonical_key:
                            regenerated_canonical_keys.add(canonical_key)

            if created_for_item:
                continue

            if data.get("itemType") == "attachment":
                pdfs = find_pdf_attachments([data])
            else:
                if not self.zotero:
                    result.failed += 1
                    result.errors.append(f"Zotero client required for parent item {parent_key}")
                    logger.error("summary: Zotero client required for parent item key=%s", parent_key)
                    continue
                children = self.zotero.fetch_children(parent_key)
                pdfs = find_pdf_attachments(children)

            if not pdfs:
                downloaded_pdf, download_status = self._download_missing_pdf(
                    parent_key=note_parent_key,
                    title=title,
                    metadata=metadata,
                    options=options,
                )
                if downloaded_pdf is not None:
                    pdfs = [{"key": note_parent_key, "filename": downloaded_pdf.name, "path": str(downloaded_pdf), "itemType": "attachment", "contentType": "application/pdf", "linkMode": "linked_file"}]
                elif download_status not in {"disabled", "missing_identifier"}:
                    result.errors.append(f"PDF download unavailable for {note_parent_key}: {download_status}")

            if not pdfs:
                abstract_text = (metadata.get("abstractNote") or metadata.get("abstract") or "").strip()
                if abstract_text:
                    cached_by_key = self._cached_by_canonical_key(canonical_key=canonical_key) if can_reuse_before_read else None
                    if cached_by_key and self._reuse_summary_for_item(
                        cached=cached_by_key,
                        note_parent_key=note_parent_key,
                        title=title,
                        options=options,
                        insert_note=insert_note,
                    ):
                        result.skipped += 1
                        continue
                    logger.info("summary: using abstract fallback item key=%s", note_parent_key)
                    summary = self.ai.summarize_paper_excerpt(
                        title=title,
                        text=abstract_text,
                        locale=options.locale,
                        max_chars=min(options.max_chars, 4000),
                        mode=options.mode,
                    )
                    paper_id = self._save_to_store(
                        summary,
                        zotero_key=note_parent_key,
                        title=title,
                        locale=options.locale,
                        source="abstract",
                        summary_kind="canonical",
                        canonical_key=canonical_key,
                        summary_profile=options.mode,
                        source_priority=10,
                    )
                    if insert_note and options.attach_zotero:
                        ok, attachment_key, attachment_title = self._write_summary_attachment(
                            note_parent_key,
                            summary,
                            title=title,
                            mode=options.mode,
                            replace_existing=options.force,
                        )
                        if paper_id and self.summary_store:
                            self.summary_store.update_attachment_status(
                                paper_id,
                                attachment_key=attachment_key,
                                attachment_title=attachment_title,
                                status="uploaded" if ok else "failed",
                            )
                    result.created += 1
                    if canonical_key:
                        regenerated_canonical_keys.add(canonical_key)
                    continue
                result.skipped += 1
                logger.info("summary: no PDF or abstract, skipping item key=%s", note_parent_key)
                continue

            for attachment in pdfs:
                pdf_path = resolve_pdf_path(self.storage_dir, attachment)
                if not pdf_path.exists():
                    logger.warning("summary: missing Zotero PDF path=%s item_key=%s; trying open-access download", pdf_path, note_parent_key)
                    downloaded_pdf, download_status = self._download_missing_pdf(
                        parent_key=note_parent_key,
                        title=title,
                        metadata=metadata,
                        options=options,
                    )
                    if downloaded_pdf is None:
                        result.errors.append(f"Missing PDF: {pdf_path}; download_status={download_status}")
                        logger.error(
                            "summary: missing Zotero PDF and download failed path=%s item_key=%s status=%s",
                            pdf_path,
                            note_parent_key,
                            download_status,
                        )
                        continue
                    pdf_path = downloaded_pdf
                pdf_hash = file_sha256(pdf_path)
                cached = self._cached_canonical(
                    zotero_key=note_parent_key,
                    canonical_key=canonical_key,
                    pdf_hash=pdf_hash,
                    options=options,
                )
                if not cached and can_reuse_before_read:
                    cached = self._cached_by_canonical_key(canonical_key=canonical_key, pdf_hash=pdf_hash)
                if cached and cached.full_summary_md:
                    self._reuse_summary_for_item(
                        cached=cached,
                        note_parent_key=note_parent_key,
                        title=title,
                        options=options,
                        insert_note=insert_note,
                    )
                    result.skipped += 1
                    created_for_item = True
                    logger.info("summary: using cached canonical summary item_key=%s", note_parent_key)
                    continue
                text = extract_pdf_text(pdf_path, options.max_pages)
                if not text:
                    result.errors.append(f"Empty extracted text: {pdf_path}")
                    logger.error("summary: empty extracted text path=%s item_key=%s", pdf_path, note_parent_key)
                    continue
                summary = self.summarize_text(
                    title=title,
                    text=text,
                    zotero_key=note_parent_key,
                    options=options,
                    source="pdf",
                    canonical_key=canonical_key,
                    pdf_hash=pdf_hash,
                    pdf_path=pdf_path,
                    insert_attachment=insert_note,
                )
                result.created += 1
                if canonical_key:
                    regenerated_canonical_keys.add(canonical_key)
                created_for_item = True
            if not created_for_item:
                result.failed += 1
                logger.error("summary: no summary created item_key=%s title=%s", parent_key, title)
        result.duration_sec = round(time.monotonic() - started, 3)
        logger.info(
            "summary: finished Zotero items processed=%d created=%d skipped=%d failed=%d duration_sec=%.3f",
            result.processed,
            result.created,
            result.skipped,
            result.failed,
            result.duration_sec,
        )
        return result
