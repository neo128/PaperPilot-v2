import tempfile
import unittest
from pathlib import Path

from paperpilot.services.review_service import LiteratureReviewService, ReviewProject, ReviewReadOptions


class FakeAI:
    def read_paper_structured(self, **kwargs):
        return "## 研究问题\n测试研究问题。\n\n## 方法\n测试方法。"

    def code_paper_for_review(self, **kwargs):
        return {
            "priority_score": 82,
            "tier": "A 核心池",
            "research_direction": "agent memory",
            "task_type": "long-term agent",
            "method_type": "memory architecture",
            "core_contribution": "A test contribution.",
            "main_limitation": "A test limitation.",
            "evidence_strength": "medium",
            "engineering_reusability": "requires adaptation",
            "relation_to_target_topic": "high",
            "coding_confidence": "medium",
            "coding_note": "fake coding",
        }

    def draft_literature_review(self, **kwargs):
        return "# Review Draft\n\nThis is a fake draft."


class FakeZotero:
    def __init__(self):
        self.notes = []

    def create_note(self, parent_key, note_html, tags=None):
        self.notes.append((parent_key, note_html, tags))


def zotero_item(key, title, doi="", arxiv_id="", abstract="abstract"):
    return {
        "key": key,
        "data": {
            "key": key,
            "itemType": "journalArticle",
            "title": title,
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
            "date": "2025",
            "publicationTitle": "TestConf",
            "DOI": doi,
            "archive": "arXiv" if arxiv_id else "",
            "archiveLocation": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "https://example.com/paper",
            "abstractNote": abstract,
        },
    }


class LiteratureReviewServiceTest(unittest.TestCase):
    def test_init_project_creates_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="agent-memory", topic="agent memory", root=Path(tmp))
            result = LiteratureReviewService().init_project(project)

            self.assertEqual(result.created, 1)
            self.assertTrue((project.path / "research_plan.md").exists())
            self.assertTrue((project.path / "data/processed/paper_pool_verified.csv").exists())
            self.assertTrue((project.path / "notes/templates/reading_note_template.md").exists())

    def test_build_pool_deduplicates_and_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="agent-memory", topic="agent memory", root=Path(tmp))
            service = LiteratureReviewService()
            items = [
                zotero_item("A", "Same Paper", doi="10.123/test"),
                zotero_item("B", "Same Paper", doi="10.123/test"),
                zotero_item("C", "Different Paper", arxiv_id="2501.00001"),
            ]

            result = service.build_pool_from_zotero_items(project, items)

            self.assertEqual(result.processed, 3)
            self.assertEqual(result.created, 2)
            self.assertEqual(result.skipped, 1)
            csv_text = (project.path / "data/processed/paper_pool_verified.csv").read_text(encoding="utf-8")
            self.assertIn("Same Paper", csv_text)
            self.assertIn("Different Paper", csv_text)

    def test_read_code_draft_and_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="agent-memory", topic="agent memory", root=Path(tmp))
            zotero = FakeZotero()
            service = LiteratureReviewService(ai=FakeAI(), zotero=zotero)
            service.build_pool_from_zotero_items(project, [zotero_item("A", "Paper A", doi="10.123/a")])

            read_result = service.read_and_code(
                project,
                ReviewReadOptions(limit=1, insert_zotero_notes=True),
            )
            draft_result = service.draft_review(project)
            sync_result = service.sync_reading_notes_to_zotero(project)

            self.assertEqual(read_result.created, 1)
            self.assertEqual(draft_result.created, 1)
            self.assertEqual(sync_result.created, 1)
            self.assertTrue((project.path / "data/processed/paper_pool_coded.csv").exists())
            self.assertTrue((project.path / "reports/review_draft.md").exists())
            self.assertGreaterEqual(len(zotero.notes), 2)


if __name__ == "__main__":
    unittest.main()
