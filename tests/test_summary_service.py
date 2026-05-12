import tempfile
import unittest
from pathlib import Path

from paperpilot.services.summary_service import (
    ExtractedFigure,
    SummaryOptions,
    SummaryService,
    _caption_for_page,
    extract_arxiv_id,
    find_pdf_attachments,
    normalize_arxiv_id,
    resolve_pdf_path,
    make_note_html,
)
from paperpilot.storage.paper_summary_store import PaperSummary, PaperSummaryStore


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

- 标题：Paper [原文]
- 年份：2026 [原文]
- 研究领域：机器人学习与系统评估 [原文]
- 关键词：compact architecture, benchmark, accuracy [原文]
- 任务类型：方法论文 [原文]

# 2. 一句话总结

该论文提出一种紧凑架构，用于在给定基准上完成测试任务，并报告了 91.2% 的准确率。[原文]

# 3. 研究问题

现有方法在测试基准上需要更清晰的模块组织和可复用评估流程；论文希望用较小的系统结构支撑稳定评估。[原文]

# 4. 方法概述

The method uses a compact architecture.

该方法输入论文测试文本与任务配置，输出结构化预测结果；核心模块包括特征整理、紧凑架构推理与结果评估。[原文]

# 5. 技术流程拆解（Step-by-step）

Step 1：读取任务输入并整理为模型可处理的特征表示，输出标准化输入。[原文]
Step 2：通过紧凑架构完成推理，输出候选预测。[原文]
Step 3：在 benchmark 上计算准确率，输出可比较的实验结果。[原文]

# 6. 创新点评估（必须分级）

- 紧凑架构设计：【创新类型】工程；【创新强度】中；【是否已有类似工作】有；【是否容易被替代】中。[推断]

# 7. 技术坐标系定位

该方法偏 black-box 行为优化，重点在系统结构和评估结果，而不是内部机制解释。[推断]

# 8. 实验与结果

- 数据集/任务：benchmark 测试任务。[原文]
- 指标：Accuracy。[原文]
- 主要结果：Accuracy reaches 91.2% on the benchmark.（91.2% benchmark result）[原文]
- 消融实验：原文未包含该类信息。[原文]
- 泛化实验：原文未包含该类信息。[原文]

# 9. 局限性

作者未展开更多真实部署和跨数据集泛化结果；这限制了结论的外推范围。[推断]

# 10. 失败模式（关键）

若输入分布明显偏离 benchmark，紧凑架构可能出现性能下降；该失败可通过额外验证集检测，也可通过扩展训练数据修复。[推断]

# 11. 通用复用价值

该论文适合作为方法对比、轻量架构设计和指标记录的示例材料。[启发]

# 12. 分类标签（结构化）

任务类型：方法评估；方法类型：紧凑架构；数据类型：benchmark；是否使用真实机器人数据：否；是否使用仿真：原文未包含该类信息；是否使用语言：原文未包含该类信息；是否使用视觉：原文未包含该类信息；是否涉及动作序列：否；是否涉及世界模型：否；是否涉及 VLA：否；是否涉及记忆/语义表示：否；是否支持长程任务：否。[原文]

# 13. 跨域适配与具身智能启发（可选）

非具身智能论文。该紧凑架构思路可启发机器人系统在资源受限场景中做模块裁剪，但这属于跨域迁移设想。[启发]

# 14. 潜在研究机会

- 背景问题：轻量系统在复杂任务上容易泛化不足；未解决空白：缺少跨场景验证；技术路线：增加多基准评估；预期价值：提高工程可靠性；难点：构造覆盖充分的测试集。[启发]
- 背景问题：单一准确率难解释错误来源；未解决空白：缺少错误分解；技术路线：加入失败模式分类；预期价值：辅助系统调试；难点：错误标注成本较高。[启发]

# 15. 高质量证据片段（强约束）

- 中文证据转述：论文报告 benchmark 上准确率为 91.2%；定位短语：91.2% benchmark result；支撑结论：该方法有明确指标结果；为什么能支撑：该短语直接给出指标和测试语境。[原文]
- 中文证据转述：论文方法使用 compact architecture；定位短语：compact architecture；支撑结论：核心设计是紧凑架构；为什么能支撑：该短语直接命名方法结构。[原文]
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

    def test_default_skips_abstract_when_no_pdf(self):
        zotero = FakeZotero()
        service = SummaryService(zotero, FakeAI(), Path("/tmp"))
        items = [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "abstractNote": "This is the abstract."}}]
        result = service.summarize_items(items, SummaryOptions(), insert_note=True)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(zotero.notes, [])
        self.assertEqual(zotero.attachments, [])

    def test_explicit_abstract_card_does_not_upload_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            zotero = FakeZotero()
            service = SummaryService(zotero, FakeAI(), Path(tmp), summary_store=store)
            items = [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "abstractNote": "This is the abstract."}}]

            result = service.summarize_items(items, SummaryOptions(allow_abstract_fallback=True), insert_note=True)

            self.assertEqual(result.created, 1)
            self.assertEqual(zotero.notes, [])
            self.assertEqual(zotero.attachments, [])
            summary = store.get_by_zotero_key("ITEMA")
            self.assertEqual(summary.summary_kind, "abstract_card")
            self.assertEqual(summary.summary_profile, "abstract_card")
            self.assertEqual(summary.source_coverage, "abstract_only")
            store.close()

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

    def test_summary_attachment_keeps_local_image_links_for_zotero(self):
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
            self.assertNotIn("data:image/png;base64,", md)
            self.assertIn(str(image_path), md)

    def test_caption_for_page_requires_explicit_figure_or_table_caption(self):
        self.assertEqual(_caption_for_page("Title\nNo figure caption here."), "")
        caption = _caption_for_page(
            "Some text. Figure 1: World model architecture with vision, memory, and controller modules. More text."
        )
        self.assertTrue(caption.startswith("Figure 1: World model architecture"))

    def test_summary_writes_sqlite_record_and_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            zotero = FakeZotero()
            service = SummaryService(zotero, FakeAI(), Path(tmp), summary_store=store)
            items = [{"data": {"key": "ITEMA", "title": "Paper", "itemType": "journalArticle", "abstractNote": "This is the abstract."}}]

            result = service.summarize_items(items, SummaryOptions(allow_abstract_fallback=True), insert_note=False)

            self.assertEqual(result.created, 1)
            self.assertTrue(store.has_summary("ITEMA"))
            self.assertGreaterEqual(len(store.list_facts(fact_type="metric")), 1)
            summary = store.get_by_zotero_key("ITEMA")
            self.assertEqual(summary.summary_kind, "abstract_card")
            self.assertEqual(summary.summary_profile, "abstract_card")
            self.assertIsNotNone(summary.quality_score)
            self.assertTrue(summary.quality_label)
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

            result = service.summarize_items(items, SummaryOptions(allow_abstract_fallback=True), insert_note=True)

            self.assertEqual(result.created, 2)
            self.assertEqual(result.skipped, 0)
            self.assertEqual(result.failed, 0)
            self.assertEqual(len(ai.calls), 2)
            self.assertEqual(zotero.attachments, [])
            store.close()

    def test_low_quality_cached_canonical_is_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            store.save(
                PaperSummary(
                    paper_id="bad_cached",
                    zotero_key="OLDITEM",
                    title="Same Paper",
                    full_summary_md="# Bad\n当前批量总结：题名和元数据表明，需要进一步确认。",
                    source="pdf",
                    summary_version="v2",
                    summary_kind="canonical",
                    canonical_key="title:same paper",
                    quality_score=0,
                    quality_label="metadata_card",
                    source_coverage="metadata_only",
                )
            )
            zotero = FakeZotero()
            ai = FakeAI()
            service = SummaryService(zotero, ai, Path(tmp), summary_store=store)

            result = service.summarize_items(
                [{"data": {"key": "ITEMA", "title": "Same Paper", "itemType": "journalArticle", "abstractNote": "Abstract A"}}],
                SummaryOptions(allow_abstract_fallback=True),
                insert_note=False,
            )

            self.assertEqual(result.created, 1)
            self.assertEqual(len(ai.calls), 1)
            summary = store.get_by_zotero_key("ITEMA")
            self.assertIsNotNone(summary)
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

            result = service.summarize_items(items, SummaryOptions(force=True, allow_abstract_fallback=True), insert_note=True)

            self.assertEqual(result.created, 2)
            self.assertEqual(result.skipped, 0)
            self.assertEqual(result.failed, 0)
            self.assertEqual(len(ai.calls), 2)
            self.assertEqual(zotero.attachments, [])
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

    def test_refuses_truncated_pdf_summary_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "long.pdf"
            pdf_path.write_bytes(b"not-a-real-pdf")
            store = PaperSummaryStore(Path(tmp) / "summaries.sqlite3")
            ai = FakeAI()
            service = SummaryService(None, ai, Path(tmp), summary_store=store)
            service_module = __import__("paperpilot.services.summary_service", fromlist=["extract_pdf_text"])
            old_extract = service_module.extract_pdf_text
            service_module.extract_pdf_text = lambda path, max_pages: "很长的论文文本" * 1000
            try:
                result = service.summarize_local_pdfs(
                    [pdf_path],
                    SummaryOptions(max_chars=100),
                    summary_dir=Path(tmp) / "out",
                )
            finally:
                service_module.extract_pdf_text = old_extract

            self.assertEqual(result.created, 0)
            self.assertEqual(result.failed, 1)
            self.assertEqual(ai.calls, [])
            self.assertEqual(store.count(), 0)
            store.close()


if __name__ == "__main__":
    unittest.main()
