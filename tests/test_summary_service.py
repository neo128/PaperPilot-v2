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

    def fetch_children(self, parent_key):
        return []

    def create_note(self, parent_key, note_html, tags=None):
        self.notes.append((parent_key, note_html, tags))

    def create_file_attachment(self, parent_key, file_path, *, title=None, content_type=None, tags=None):
        self.attachments.append((parent_key, title, str(file_path), content_type, tags))
        return f"ATTACH{len(self.attachments)}"


class FakeAI:
    def summarize_paper_excerpt(self, **kwargs):
        return """# 1. 论文基本信息

- 标题：Paper
- 年份：2026

# 2. 一句话总结

## 原文明确内容

This is a test summary.

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

    def test_use_deepxiv_before_pdf_fallback(self):
        zotero = FakeZotero()
        service = SummaryService(zotero, FakeAI(), Path("/tmp"), deepxiv=FakeDeepXiv())
        items = [{"data": {"key": "ITEM2", "title": "Paper", "itemType": "journalArticle", "url": "https://arxiv.org/abs/2409.05591"}}]
        result = service.summarize_items(items, SummaryOptions(use_deepxiv=True), insert_note=True)
        self.assertEqual(result.created, 1)
        self.assertEqual(zotero.notes, [])
        self.assertEqual(len(zotero.attachments), 1)

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
            self.assertIn("## 关键图表", out_md.read_text(encoding="utf-8"))
            self.assertIn("Figure 1. System architecture", out_md.read_text(encoding="utf-8"))
            figures = store.list_figures()
            self.assertEqual(len(figures), 1)
            self.assertEqual(figures[0].caption, "Figure 1. System architecture")
            store.close()


if __name__ == "__main__":
    unittest.main()
