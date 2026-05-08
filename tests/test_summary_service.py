import tempfile
import unittest
from pathlib import Path

from paperpilot.services.summary_service import (
    ExtractedFigure,
    SummaryOptions,
    SummaryService,
    extract_arxiv_id,
    find_pdf_attachments,
    normalize_arxiv_id,
    resolve_pdf_path,
    make_note_html,
)
from paperpilot.storage.paper_summary_store import PaperSummaryStore


class FakeZotero:
    def __init__(self):
        self.notes = []
        self.attachments = []
        self.children = []

    def fetch_children(self, parent_key):
        return self.children

    def fetch_item(self, item_key):
        return {"data": {"key": item_key, "title": "Paper", "itemType": "journalArticle", "url": "https://arxiv.org/abs/2409.05591"}}

    def create_note(self, parent_key, note_html, tags=None):
        self.notes.append((parent_key, note_html, tags))

    def create_file_attachment(self, parent_key, file_path, *, title=None, content_type=None, tags=None):
        self.attachments.append((parent_key, title, str(file_path), content_type, tags))
        return f"ATTACH{len(self.attachments)}"


class FakeAI:
    def __init__(self):
        self.calls = []

    def summarize_paper_excerpt(self, **kwargs):
        self.calls.append(kwargs)
        return """# 1. 论文基本信息

- 标题：Paper
- 年份：2026

# 2. 一句话总结

## 原文明确内容

This is a test summary.

# 3. 方法与架构

The method uses a compact architecture.

# 8. 实验与结果

- Accuracy reaches 91.2% on the benchmark.（91.2% benchmark result）
"""


class FakeDeepXiv:
    def brief(self, arxiv_id):
        return {"arxiv_id": arxiv_id, "tldr": "brief"}

    def head(self, arxiv_id):
        return {"title": "Head Title", "abstract": "Head Abstract"}

    def section(self, arxiv_id, section):
        return f"{section} content"


class FakeOpenAccess:
    def __init__(self):
        self.lookups = []
        self.downloads = []

    def find_pdf(self, *, doi="", arxiv_id=""):
        self.lookups.append((doi, arxiv_id))
        return type(
            "Lookup",
            (),
            {
                "status": "found",
                "source": "arxiv",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            },
        )()

    def download_pdf(self, pdf_url, destination, *, force=False):
        self.downloads.append((pdf_url, destination, force))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"not-a-real-pdf")
        return destination


class FakeArxiv:
    def __init__(self):
        self.searches = []

    def search(self, query, limit=10, sort_by="submittedDate"):
        self.searches.append((query, limit, sort_by))
        return [
            {
                "title": query,
                "arxiv_id": "2604.12345v1",
                "src_url": "https://arxiv.org/pdf/2604.12345v1.pdf",
            }
        ]


class SummaryServiceHelpersTest(unittest.TestCase):
    def test_find_pdf_attachments(self):
        children = [
            {"data": {"itemType": "attachment", "filename": "a.pdf", "contentType": "application/pdf", "linkMode": "imported_file"}},
            {"data": {"itemType": "attachment", "filename": "b.txt", "contentType": "text/plain", "linkMode": "imported_file"}},
        ]
        pdfs = find_pdf_attachments(children)
        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0]["filename"], "a.pdf")

    def test_resolve_pdf_path_storage(self):
        root = Path("/tmp/storage")
        attachment = {"path": "storage:ABC/test.pdf"}
        self.assertEqual(resolve_pdf_path(root, attachment), root / "ABC/test.pdf")

    def test_extract_arxiv_id(self):
        item = {"url": "https://arxiv.org/abs/2409.05591"}
        self.assertEqual(extract_arxiv_id(item), "2409.05591")

    def test_extract_arxiv_id_strips_pdf_and_version_suffix(self):
        item = {"url": "https://arxiv.org/pdf/2604.11174v1.pdf"}
        self.assertEqual(extract_arxiv_id(item), "2604.11174")

    def test_normalize_arxiv_id_handles_archive_location(self):
        self.assertEqual(normalize_arxiv_id("2604.11585v3.pdf"), "2604.11585")

    def test_make_note_html_marks_ai_summary_version(self):
        note_html = make_note_html("# Summary")

        self.assertIn("AI总结-v2", note_html)
        self.assertIn("AI总结版本：</strong>v2", note_html)
        self.assertIn("<h1>Summary</h1>", note_html)


class SummaryServiceTest(unittest.TestCase):
    def test_skip_when_no_pdf(self):
        service = SummaryService(FakeZotero(), FakeAI(), Path("/tmp"))
        items = [{"data": {"key": "ITEM1", "title": "Paper", "itemType": "journalArticle"}}]
        result = service.summarize_items(items, SummaryOptions(), insert_note=True)
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.skipped, 1)

    def test_fallback_to_abstract_when_no_pdf(self):
        zotero = FakeZotero()
        service = SummaryService(zotero, FakeAI(), Path("/tmp"))
        items = [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "abstractNote": "This is the abstract."}}]
        result = service.summarize_items(items, SummaryOptions(), insert_note=True)
        self.assertEqual(result.created, 1)
        self.assertEqual(zotero.notes, [])
        self.assertEqual(len(zotero.attachments), 1)
        self.assertEqual(zotero.attachments[0][3], "text/markdown")
        self.assertIn("AI总结-v2-md", zotero.attachments[0][4])

    def test_summary_attachment_skips_existing_markdown_attachment(self):
        zotero = FakeZotero()
        zotero.children = [
            {
                "key": "EXISTING",
                "data": {
                    "itemType": "attachment",
                    "title": "PaperPilot AI总结-v2 Markdown - Paper",
                    "filename": "Paper_v2.md",
                    "tags": [{"tag": "AI总结-v2-md"}],
                },
            }
        ]
        service = SummaryService(zotero, FakeAI(), Path("/tmp"))

        ok, attachment_key, _ = service._write_summary_attachment("ITEMA", "# Summary", title="Paper")

        self.assertTrue(ok)
        self.assertEqual(attachment_key, "EXISTING")
        self.assertEqual(zotero.attachments, [])

    def test_summary_attachment_embeds_local_images_for_zotero(self):
        with tempfile.TemporaryDirectory() as tmp:
            zotero = FakeZotero()
            service = SummaryService(zotero, FakeAI(), Path(tmp))
            image_path = Path(tmp) / "figure.png"
            image_path.write_bytes(b"fake-image")

            ok, attachment_key, _ = service._write_summary_attachment("ITEMA", f"![Fig]({image_path})", title="Paper")

            self.assertTrue(ok)
            self.assertEqual(attachment_key, "ATTACH1")
            md_path = Path(zotero.attachments[0][2])
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", md)
            self.assertNotIn(str(image_path), md)

    def test_summary_writes_sqlite_record_and_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            zotero = FakeZotero()
            service = SummaryService(zotero, FakeAI(), Path(tmp), summary_store=store)
            items = [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "abstractNote": "This is the abstract."}}]

            result = service.summarize_items(items, SummaryOptions(), insert_note=False)

            self.assertEqual(result.created, 1)
            self.assertTrue(store.has_summary("ITEMA"))
            self.assertGreaterEqual(len(store.list_facts(fact_type="metric")), 1)
            summary = store.get_by_zotero_key("ITEMA")
            self.assertEqual(summary.summary_kind, "canonical")
            self.assertEqual(summary.summary_profile, "general")
            store.close()

    def test_reuses_canonical_summary_for_duplicate_paper_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            zotero = FakeZotero()
            ai = FakeAI()
            service = SummaryService(zotero, ai, Path(tmp), summary_store=store)
            items = [
                {"data": {"key": "ITEMA", "title": "Same Paper", "itemType": "journalArticle", "abstractNote": "Abstract A"}},
                {"data": {"key": "ITEMB", "title": "Same Paper", "itemType": "journalArticle", "abstractNote": "Abstract B"}},
            ]

            result = service.summarize_items(items, SummaryOptions(), insert_note=True)

            self.assertEqual(result.created, 1)
            self.assertEqual(result.skipped, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(len(ai.calls), 1)
            self.assertEqual(len(zotero.attachments), 2)
            store.close()

    def test_force_summary_regenerates_duplicate_canonical_only_once_per_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            zotero = FakeZotero()
            ai = FakeAI()
            service = SummaryService(zotero, ai, Path(tmp), summary_store=store)
            items = [
                {"data": {"key": "ITEMA", "title": "Same Paper", "itemType": "journalArticle", "abstractNote": "Abstract A"}},
                {"data": {"key": "ITEMB", "title": "Same Paper", "itemType": "journalArticle", "abstractNote": "Abstract B"}},
            ]

            result = service.summarize_items(items, SummaryOptions(force=True), insert_note=True)

            self.assertEqual(result.created, 1)
            self.assertEqual(result.skipped, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(len(ai.calls), 1)
            self.assertEqual(len(zotero.attachments), 2)
            store.close()

    def test_use_deepxiv_before_pdf_fallback(self):
        zotero = FakeZotero()
        service = SummaryService(zotero, FakeAI(), Path("/tmp"), deepxiv=FakeDeepXiv())
        items = [{"data": {"key": "ITEM2", "title": "Paper", "itemType": "journalArticle", "url": "https://arxiv.org/abs/2409.05591"}}]
        result = service.summarize_items(items, SummaryOptions(use_deepxiv=True), insert_note=True)
        self.assertEqual(result.created, 1)
        self.assertEqual(zotero.notes, [])
        self.assertEqual(len(zotero.attachments), 1)

    def test_downloads_missing_zotero_pdf_before_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            zotero = FakeZotero()
            zotero.children = [
                {
                    "data": {
                        "key": "PDF1",
                        "itemType": "attachment",
                        "filename": "missing.pdf",
                        "contentType": "application/pdf",
                        "linkMode": "linked_file",
                        "path": str(Path(tmp) / "missing.pdf"),
                    }
                }
            ]
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            oa = FakeOpenAccess()
            service = SummaryService(zotero, FakeAI(), Path(tmp), summary_store=store, open_access=oa)
            service_module = __import__("paperpilot.services.summary_service", fromlist=["extract_pdf_text", "file_sha256"])
            old_extract = service_module.extract_pdf_text
            old_hash = service_module.file_sha256
            service_module.extract_pdf_text = lambda path, max_pages: "paper text"
            service_module.file_sha256 = lambda path: "hash"
            try:
                result = service.summarize_items(
                    [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "url": "https://arxiv.org/abs/2409.05591"}}],
                    SummaryOptions(download_missing_pdfs=True),
                    insert_note=True,
                )
            finally:
                service_module.extract_pdf_text = old_extract
                service_module.file_sha256 = old_hash
                store.close()

            self.assertEqual(result.created, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(oa.lookups, [("", "2409.05591")])
            self.assertEqual(len(oa.downloads), 1)
            self.assertGreaterEqual(len(zotero.attachments), 2)
            self.assertIn("application/pdf", [attachment[3] for attachment in zotero.attachments])

    def test_downloads_missing_pdf_by_title_search_when_identifier_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            zotero = FakeZotero()
            zotero.children = [
                {
                    "data": {
                        "key": "PDF1",
                        "itemType": "attachment",
                        "filename": "missing.pdf",
                        "contentType": "application/pdf",
                        "linkMode": "linked_file",
                        "path": str(Path(tmp) / "missing.pdf"),
                    }
                }
            ]
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            oa = FakeOpenAccess()
            arxiv = FakeArxiv()
            service = SummaryService(zotero, FakeAI(), Path(tmp), summary_store=store, open_access=oa, arxiv=arxiv)
            service_module = __import__("paperpilot.services.summary_service", fromlist=["extract_pdf_text", "file_sha256"])
            old_extract = service_module.extract_pdf_text
            old_hash = service_module.file_sha256
            service_module.extract_pdf_text = lambda path, max_pages: "paper text"
            service_module.file_sha256 = lambda path: "hash"
            try:
                result = service.summarize_items(
                    [{"data": {"key": "ITEMA", "title": "Residual Context Diffusion Language Models", "itemType": "journalArticle"}}],
                    SummaryOptions(download_missing_pdfs=True),
                    insert_note=False,
                )
            finally:
                service_module.extract_pdf_text = old_extract
                service_module.file_sha256 = old_hash
                store.close()

            self.assertEqual(result.created, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(arxiv.searches[0][0], "Residual Context Diffusion Language Models")
            self.assertEqual(oa.lookups, [("", "2604.12345")])

    def test_summarize_local_pdfs_to_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "test.pdf"
            pdf_path.write_bytes(b"not-a-real-pdf")
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            service = SummaryService(None, FakeAI(), Path(tmp), summary_store=store)
            # patch extract step by monkey patching method target module behavior is overkill, so use a subclass
            service_module = __import__("paperpilot.services.summary_service", fromlist=["extract_pdf_text"])
            old_extract = service_module.extract_pdf_text
            service_module.extract_pdf_text = lambda path, max_pages: "paper text"
            fig_path = Path(tmp) / "fig_001.png"
            fig_path.write_bytes(b"fake-png")
            service._extract_key_figures = lambda path, key, limit: [
                ExtractedFigure(
                    file_path=fig_path,
                    page=1,
                    caption="Figure 1. System architecture",
                    figure_type="architecture",
                )
            ]
            try:
                result = service.summarize_local_pdfs([pdf_path], SummaryOptions(), summary_dir=Path(tmp) / "out")
            finally:
                service_module.extract_pdf_text = old_extract
            self.assertEqual(result.created, 1)
            out_md = Path(tmp) / "out" / "test.summary.md"
            self.assertTrue(out_md.exists())
            summary_md = out_md.read_text(encoding="utf-8")
            self.assertNotIn("## 关键图表", summary_md)
            self.assertIn("**图表 1（第 1 页，architecture）**", summary_md)
            self.assertIn("Figure 1. System architecture", summary_md)
            self.assertLess(summary_md.index("**图表 1"), summary_md.index("The method uses a compact architecture."))
            figures = store.list_figures()
            self.assertEqual(len(figures), 1)
            self.assertEqual(figures[0].caption, "Figure 1. System architecture")
            store.close()


if __name__ == "__main__":
    unittest.main()
