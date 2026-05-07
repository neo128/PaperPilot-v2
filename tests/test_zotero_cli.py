from __future__ import annotations

from paperpilot.cli.zotero import _marked_on_or_after


def test_marked_on_or_after_prefers_note_marker_date():
    assert _marked_on_or_after("AI总结-v2（20260506-181250）", date_added="2026-03-01T00:00:00Z", cutoff="2026-04-01")
    assert not _marked_on_or_after("AI总结 （2026-03-10 16:01）", date_added="2026-05-01T00:00:00Z", cutoff="2026-04-01")


def test_marked_on_or_after_falls_back_to_date_added():
    assert _marked_on_or_after("AI总结 without explicit date", date_added="2026-04-02T00:00:00Z", cutoff="2026-04-01")
