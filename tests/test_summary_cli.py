from __future__ import annotations

import json
import tempfile

from paperpilot.cli.summary import _matching_summary_attachment, _paper_id_from_summary_path, audit_local_summaries
from pathlib import Path
from types import SimpleNamespace


def test_paper_id_from_summary_path():
    assert _paper_id_from_summary_path(Path("P010_Modern_Neuromorphic.summary.md")) == "P010"


def test_matching_summary_attachment_detects_filename_title_or_tag():
    assert _matching_summary_attachment(
        {"data": {"filename": "P010.summary.md", "title": "Other", "tags": []}},
        filename="P010.summary.md",
        title="Expected",
    )
    assert _matching_summary_attachment(
        {"data": {"filename": "other.md", "title": "Expected", "tags": []}},
        filename="P010.summary.md",
        title="Expected",
    )
    assert _matching_summary_attachment(
        {"data": {"filename": "other.md", "title": "Other", "tags": [{"tag": "AI总结-v2-md"}]}},
        filename="P010.summary.md",
        title="Expected",
    )


def test_audit_local_summaries_writes_quality_report():
    with tempfile.TemporaryDirectory() as tmp:
        summary_dir = Path(tmp) / "summaries"
        summary_dir.mkdir()
        (summary_dir / "bad.md").write_text(
            "# 1. 论文基本信息\n当前批量总结：题名和元数据表明，需要进一步阅读全文确认。\n" * 10,
            encoding="utf-8",
        )
        report_path = Path(tmp) / "audit.json"

        result = audit_local_summaries(
            SimpleNamespace(
                summary_dir=str(summary_dir),
                glob="*.md",
                source="pdf",
                locale="zh",
                fail_under=70,
                report_path=str(report_path),
            )
        )

        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert result.processed == 1
        assert result.failed == 1
        assert rows[0]["label"] == "metadata_card"
