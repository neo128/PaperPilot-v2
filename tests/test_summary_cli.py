from __future__ import annotations

from paperpilot.cli.summary import _matching_summary_attachment, _paper_id_from_summary_path
from pathlib import Path


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
