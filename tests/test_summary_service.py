import tempfile
import unittest
from pathlib import Path

from paperpilot.services.summary_service import (
    SummaryOptions,
    SummaryService,
    extract_arxiv_id,
    find_pdf_attachments,
    normalize_arxiv_id,
    resolve_pdf_path,
)


class FakeZotero:
    def __init__(self):
        self.notes = []

    def fetch_children(self, parent_key):
        return []

    def create_note(self, parent_key, note_html, tags=None):
        self.notes.append((parent_key, note_html, tags))


class FakeAI:
    def summarize_paper_excerpt(self, **kwargs):
        return "# Summary\n\nThis is a test summary."


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
        self.assertEqual(len(zotero.notes), 1)

    def test_use_deepxiv_before_pdf_fallback(self):
        zotero = FakeZotero()
        service = SummaryService(zotero, FakeAI(), Path("/tmp"), deepxiv=FakeDeepXiv())
        items = [{"data": {"key": "ITEM2", "title": "Paper", "itemType": "journalArticle", "url": "https://arxiv.org/abs/2409.05591"}}]
        result = service.summarize_items(items, SummaryOptions(use_deepxiv=True), insert_note=True)
        self.assertEqual(result.created, 1)
        self.assertEqual(len(zotero.notes), 1)

    def test_summarize_local_pdfs_to_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "test.pdf"
            pdf_path.write_bytes(b"not-a-real-pdf")
            service = SummaryService(None, FakeAI(), Path(tmp))
            # patch extract step by monkey patching method target module behavior is overkill, so use a subclass
            service_module = __import__("paperpilot.services.summary_service", fromlist=["extract_pdf_text"])
            old_extract = service_module.extract_pdf_text
            service_module.extract_pdf_text = lambda path, max_pages: "paper text"
            try:
                result = service.summarize_local_pdfs([pdf_path], SummaryOptions(), summary_dir=Path(tmp) / "out")
            finally:
                service_module.extract_pdf_text = old_extract
            self.assertEqual(result.created, 1)
            self.assertTrue((Path(tmp) / "out" / "test.summary.md").exists())


if __name__ == "__main__":
    unittest.main()
