from __future__ import annotations

import tempfile
from pathlib import Path

from paperpilot.storage.paper_summary_store import PaperSummary, PaperSummaryFact, PaperSummaryFigure, PaperSummaryStore
from paperpilot.storage.summary_parser import extract_structured_fields, extract_summary_facts


SAMPLE_MD = """# 1. 论文基本信息

## 原文明确内容

- 标题：Test Paper Title
- 年份：2025
- 作者：Alice, Bob
- 机构：Test University
- 领域：Machine Learning
- 关键词：test, ml, ai
- 任务类型：classification

# 2. 一句话总结

## 原文明确内容

This paper proposes a new method for X.

# 3. 研究问题

## 原文明确内容

Current methods fail to handle Y.
"""


def test_store_create_and_save():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test Paper")
        fields["paper_id"] = "test_001"

        store.save(PaperSummary(**fields))

        retrieved = store.get_by_zotero_key("ABC123")
        assert retrieved is not None
        assert retrieved.zotero_key == "ABC123"
        assert "Test Paper Title" in retrieved.title
        assert retrieved.year == "2025"
        assert retrieved.authors == "Alice, Bob"
        assert "new method for X" in (retrieved.one_line_summary or "")
        assert "fail to handle Y" in (retrieved.research_problem or "")

        store.close()


def test_store_saves_extracted_facts():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test Paper")
        fields["paper_id"] = "test_facts"
        store.save(
            PaperSummary(**fields),
            facts=[
                PaperSummaryFact(
                    paper_id="test_facts",
                    zotero_key="ABC123",
                    title="Test Paper",
                    fact_type="metric",
                    label="Accuracy",
                    value=91.2,
                    unit="%",
                    context="Accuracy reaches 91.2% on the benchmark.",
                    evidence="91.2% on the benchmark",
                    confidence="high",
                    source_section="experiments",
                    source="pdf",
                    summary_version="v2",
                )
            ],
        )

        facts = store.list_facts(paper_id="test_facts")
        assert len(facts) == 1
        assert facts[0].fact_type == "metric"
        assert facts[0].value == 91.2

        store.close()


def test_store_saves_extracted_figures():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test Paper")
        fields["paper_id"] = "test_figures"
        store.save(
            PaperSummary(**fields),
            figures=[
                PaperSummaryFigure(
                    paper_id="test_figures",
                    zotero_key="ABC123",
                    title="Test Paper",
                    figure_index=1,
                    page=2,
                    file_path="/tmp/fig_001.png",
                    caption="Figure 1. System architecture",
                    figure_type="architecture",
                    relevance="candidate",
                    summary_version="v2",
                )
            ],
        )

        figures = store.list_figures(paper_id="test_figures")
        assert len(figures) == 1
        assert figures[0].page == 2
        assert figures[0].figure_type == "architecture"

        store.close()


def test_store_updates_zotero_attachment_status():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test Paper")
        fields["paper_id"] = "test_attachment"
        store.save(PaperSummary(**fields))

        store.update_attachment_status(
            "test_attachment",
            attachment_key="ATTACH1",
            attachment_title="PaperPilot AI总结-v2 Markdown - Test Paper",
            status="uploaded",
            attached_at="2026-05-07T00:00:00+00:00",
        )
        summary = store.get_by_zotero_key("ABC123")

        assert summary is not None
        assert summary.zotero_attachment_key == "ATTACH1"
        assert summary.attachment_status == "uploaded"
        store.close()


def test_store_has_summary():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test")
        fields["paper_id"] = "test_002"
        store.save(PaperSummary(**fields))

        assert store.has_summary("ABC123") is True
        assert store.has_summary("NONEXIST") is False

        store.close()


def test_store_list_and_count():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        for i in range(3):
            fields = extract_structured_fields(SAMPLE_MD, zotero_key=f"KEY{i}", title_hint=f"Paper {i}")
            fields["paper_id"] = f"test_{i}"
            store.save(PaperSummary(**fields))

        assert store.count() == 3
        items = store.list_summaries(limit=2)
        assert len(items) == 2

        store.close()


def test_store_search():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.sqlite3"
        store = PaperSummaryStore(db)

        fields = extract_structured_fields(SAMPLE_MD, zotero_key="ABC123", title_hint="Test Paper")
        fields["paper_id"] = "test_search"
        store.save(PaperSummary(**fields))

        results = store.search("method")
        assert len(results) >= 1

        results_none = store.search("zzzznonexistent")
        assert len(results_none) == 0

        store.close()


def test_parser_section_split():
    sections = extract_structured_fields(SAMPLE_MD)
    assert sections["title"] == "Test Paper Title"
    assert sections["year"] == "2025"
    assert sections["authors"] == "Alice, Bob"
    assert sections["institution"] == "Test University"
    assert sections["field"] == "Machine Learning"
    assert sections["keywords"] == "test, ml, ai"
    assert sections["task_type"] == "classification"
    assert sections["one_line_summary"] == "This paper proposes a new method for X."
    assert sections["research_problem"] is not None


def test_fact_extraction_uses_conservative_confidence_rules():
    md = """# 1. 论文基本信息

- 标题：Theory Paper
- 年份：2026

# 3. 研究问题

- This theoretical paper discusses digital platforms and 3 attention regimes.

# 8. 实验与结果

- Top-1 accuracy reaches 91.2% on Habitat benchmark.（原文）
- The benchmark includes 12 tasks and 30 scenes.（原文）

# 13. 跨域适配与具身智能启发

- [原文] The method is evaluated in the Habitat simulator.
- [启发] Habitat simulator may be a relevant comparison platform for future work.
"""

    facts = extract_summary_facts(md, title_hint="Theory Paper")
    metric_contexts = [fact["context"] for fact in facts if fact["fact_type"] == "metric"]
    platform_contexts = [fact["context"] for fact in facts if fact["fact_type"] == "platform"]

    assert not any("digital platforms" in context for context in metric_contexts + platform_contexts)
    assert not any("[启发]" in context for context in metric_contexts + platform_contexts)
    assert any("91.2%" in context for context in metric_contexts)
    assert any("[原文] The method is evaluated in the Habitat simulator." in context for context in platform_contexts)
