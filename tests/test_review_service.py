import csv
import tempfile
import unittest
from pathlib import Path

from paperpilot.services.review_service import (
    CODED_POOL_FIELDS,
    CURATED_POOL_FIELDS,
    FULLTEXT_VERIFICATION_FIELDS,
    MATRIX_FIELDS,
    LiteratureReviewService,
    ReviewCurateOptions,
    ReviewFetchPdfOptions,
    ReviewMatrixOptions,
    ReviewProject,
    ReviewQCOptions,
    ReviewReadOptions,
    ReviewVerifyOptions,
)
from paperpilot.clients.open_access import OAPdfResult


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
        self.children = {}
        self.attachments = []

    def create_note(self, parent_key, note_html, tags=None):
        self.notes.append((parent_key, note_html, tags))

    def fetch_children(self, parent_key):
        return self.children.get(parent_key, [])

    def create_attachment_url(self, parent_key, title, url, content_type="application/pdf"):
        self.attachments.append((parent_key, title, url, content_type))


class FakeOA:
    def __init__(self, result=None):
        self.result = result or OAPdfResult(status="found", source="unpaywall", pdf_url="https://example.com/paper.pdf")

    def find_pdf(self, *, doi="", arxiv_id=""):
        return self.result

    def download_pdf(self, pdf_url, destination, *, force=False):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-1.4\n")
        return destination


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

    def test_curate_coded_pool_downgrades_off_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService()
            service.init_project(project)
            rows = [
                {
                    "paper_id": "P001",
                    "title": "A review of learning-based dynamics models for robotic manipulation",
                    "priority_score": "82",
                    "tier": "A 核心池",
                    "research_direction": "robotics world model",
                    "task_type": "robot manipulation",
                    "method_type": "dynamics model",
                    "relation_to_target_topic": "high",
                    "coding_confidence": "high",
                    "status": "success",
                },
                {
                    "paper_id": "P002",
                    "title": "Closest alien world to our solar system could be ripe for life",
                    "priority_score": "70",
                    "tier": "B 主体池",
                    "research_direction": "astronomy",
                    "task_type": "planetary science",
                    "method_type": "climate model",
                    "relation_to_target_topic": "low",
                    "coding_confidence": "low",
                    "status": "success",
                },
            ]
            coded_path = project.path / "data/processed/paper_pool_coded.csv"
            with coded_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

            result = service.curate_coded_pool(project, ReviewCurateOptions())

            self.assertEqual(result.processed, 2)
            self.assertEqual(result.updated, 1)
            curated_path = project.path / "data/processed/paper_pool_curated.csv"
            with curated_path.open(encoding="utf-8", newline="") as f:
                curated = list(csv.DictReader(f))
            self.assertEqual(curated[0]["curation_action"], "keep")
            self.assertEqual(curated[1]["tier"], "D 存档池")
            self.assertEqual(curated[1]["curation_action"], "downgrade_to_d")
            self.assertIn("negative_keywords", curated[1]["curation_reason"])
            self.assertTrue((project.path / "reports/curation_report.md").exists())

    def test_curate_apply_overwrites_coded_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService()
            service.init_project(project)
            coded_path = project.path / "data/processed/paper_pool_coded.csv"
            with coded_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "title": "Rethinking Slime Mold Taxonomy",
                    "priority_score": "75",
                    "tier": "B 主体池",
                    "relation_to_target_topic": "low",
                    "coding_confidence": "low",
                })

            service.curate_coded_pool(project, ReviewCurateOptions(apply=True))

            with coded_path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["tier"], "D 存档池")
            self.assertNotIn("curation_action", rows[0])
            with (project.path / "data/processed/paper_pool_curated.csv").open(encoding="utf-8", newline="") as f:
                curated_rows = list(csv.DictReader(f))
            self.assertEqual(list(curated_rows[0].keys()), CURATED_POOL_FIELDS)

    def test_curate_preview_confirms_existing_d_without_status_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService()
            service.init_project(project)
            coded_path = project.path / "data/processed/paper_pool_coded.csv"
            with coded_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "title": "Systematic analysis of AI model cards",
                    "priority_score": "70",
                    "tier": "D 存档池",
                    "relation_to_target_topic": "low",
                    "coding_confidence": "high",
                    "coding_note": "Already archived.",
                })
            status_path = project.path / "reports/deep_reading_status.md"
            status_path.write_text("sentinel\n", encoding="utf-8")

            result = service.curate_coded_pool(project, ReviewCurateOptions())

            self.assertEqual(result.updated, 0)
            self.assertEqual(result.skipped, 1)
            self.assertEqual(status_path.read_text(encoding="utf-8"), "sentinel\n")
            with (project.path / "data/processed/paper_pool_curated.csv").open(encoding="utf-8", newline="") as f:
                curated_rows = list(csv.DictReader(f))
            self.assertEqual(curated_rows[0]["curation_action"], "confirm_d")
            self.assertEqual(curated_rows[0]["priority_score"], "40")

    def test_qc_review_reports_citation_and_tier_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService()
            service.init_project(project)
            card_path = project.path / "notes/core/P001_card.md"
            card_path.write_text("needs_verification\n", encoding="utf-8")
            rows = [
                {
                    "paper_id": "P001",
                    "title": "Core robot world model",
                    "priority_score": "90",
                    "tier": "A 核心池",
                    "citation_key": "Core2026WorldModel",
                    "relation_to_target_topic": "high",
                    "coding_confidence": "high",
                    "reading_card": "notes/core/P001_card.md",
                },
                {
                    "paper_id": "P002",
                    "title": "Uncited robot world model",
                    "priority_score": "70",
                    "tier": "B 主体池",
                    "citation_key": "Uncited2026WorldModel",
                    "relation_to_target_topic": "high",
                    "coding_confidence": "high",
                    "reading_card": "notes/core/P002_missing.md",
                },
                {
                    "paper_id": "P003",
                    "title": "Off topic clinical AI",
                    "priority_score": "40",
                    "tier": "D 存档池",
                    "citation_key": "Offtopic2026Clinical",
                    "relation_to_target_topic": "low",
                },
            ]
            coded_path = project.path / "data/processed/paper_pool_coded.csv"
            with coded_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            with (project.path / "bib/citation_keys.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["paper_id", "citation_key", "title", "year", "zotero_key"])
                writer.writeheader()
                writer.writerow({"paper_id": "P001", "citation_key": "Core2026WorldModel", "title": "Core robot world model"})
            (project.path / "bib/references.bib").write_text("@article{Core2026WorldModel,\n}\n", encoding="utf-8")
            (project.path / "reports/review_draft.md").write_text(
                "# Draft\n\n## 分类框架\nEvidence uses [P001] and [P003] citation_key: MissingKey2026.\n",
                encoding="utf-8",
            )

            result = service.qc_review(project, ReviewQCOptions())

            self.assertEqual(result.created, 1)
            self.assertGreaterEqual(result.updated, 4)
            report = (project.path / "reports/qc_report.md").read_text(encoding="utf-8")
            self.assertIn("D-tier papers appear in evidence sections", report)
            self.assertIn("P003", report)
            self.assertIn("A/B papers not cited in draft", report)
            self.assertIn("MissingKey2026", report)

    def test_build_matrices_excludes_d_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService()
            service.init_project(project)
            card_path = project.path / "notes/core/P001_card.md"
            card_path.write_text("full text note\n", encoding="utf-8")
            coded_path = project.path / "data/processed/paper_pool_coded.csv"
            with coded_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows([
                    {
                        "paper_id": "P001",
                        "title": "Trust-aware world models for robot manipulation",
                        "priority_score": "90",
                        "tier": "A 核心池",
                        "citation_key": "Trust2026Robot",
                        "method_type": "trust-aware model-based planning",
                        "model_or_system_type": "uncertainty-quantified world model",
                        "reading_card": "notes/core/P001_card.md",
                    },
                    {
                        "paper_id": "P002",
                        "title": "Clinical policy paper",
                        "priority_score": "40",
                        "tier": "D 存档池",
                        "citation_key": "Clinical2026Policy",
                    },
                ])

            result = service.build_matrices(project, ReviewMatrixOptions())

            self.assertEqual(result.created, 3)
            matrix_path = project.path / "data/processed/comparison_matrix.csv"
            with matrix_path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0].keys()), MATRIX_FIELDS)
            self.assertEqual([row["paper_id"] for row in rows], ["P001"])
            self.assertEqual(rows[0]["taxonomy_branch"], "Trust-Aware / Uncertainty-Quantified Models")
            report = (project.path / "reports/comparison_matrix.md").read_text(encoding="utf-8")
            self.assertIn("Taxonomy Matrix", report)
            self.assertTrue((project.path / "figs/taxonomy_overview.mmd").exists())

    def test_verify_fulltext_detects_local_zotero_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=root)
            storage_dir = root / "zotero_storage"
            pdf_path = storage_dir / "ATTACH1" / "paper.pdf"
            pdf_path.parent.mkdir(parents=True)
            pdf_path.write_bytes(b"%PDF-1.4\n")
            zotero = FakeZotero()
            zotero.children["ZOT1"] = [{
                "data": {
                    "key": "ATTACH1",
                    "itemType": "attachment",
                    "filename": "paper.pdf",
                    "contentType": "application/pdf",
                    "linkMode": "imported_file",
                    "path": "storage:ATTACH1/paper.pdf",
                }
            }]
            service = LiteratureReviewService(zotero=zotero)
            service.init_project(project)
            with (project.path / "data/processed/paper_pool_verified.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "paper_id",
                    "zotero_key",
                    "title",
                    "doi",
                    "arxiv_id",
                    "paper_url",
                    "citation_key",
                ], extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "zotero_key": "ZOT1",
                    "title": "Robot world model",
                    "doi": "10.123/test",
                    "paper_url": "https://doi.org/10.123/test",
                    "citation_key": "Robot2026World",
                })
            with (project.path / "data/processed/paper_pool_coded.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "zotero_key": "ZOT1",
                    "title": "Robot world model",
                    "priority_score": "90",
                    "tier": "A 核心池",
                    "citation_key": "Robot2026World",
                })

            result = service.verify_fulltext(project, ReviewVerifyOptions(storage_dir=storage_dir))

            self.assertEqual(result.created, 2)
            queue_path = project.path / "data/processed/fulltext_verification_queue.csv"
            with queue_path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0].keys()), FULLTEXT_VERIFICATION_FIELDS)
            self.assertEqual(rows[0]["verification_status"], "ready_local_pdf")
            self.assertEqual(rows[0]["local_pdf_count"], "1")
            report = (project.path / "reports/fulltext_verification_status.md").read_text(encoding="utf-8")
            self.assertIn("Ready For Full-Text Rereading", report)

    def test_fetch_open_access_pdfs_downloads_project_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            service = LiteratureReviewService(open_access=FakeOA())
            service.init_project(project)
            with (project.path / "data/processed/paper_pool_verified.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "paper_id",
                    "zotero_key",
                    "title",
                    "doi",
                    "arxiv_id",
                    "paper_url",
                    "citation_key",
                ], extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "zotero_key": "ZOT1",
                    "title": "Robot world model",
                    "doi": "10.123/test",
                    "paper_url": "https://doi.org/10.123/test",
                    "citation_key": "Robot2026World",
                })
            with (project.path / "data/processed/paper_pool_coded.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerow({
                    "paper_id": "P001",
                    "zotero_key": "ZOT1",
                    "title": "Robot world model",
                    "priority_score": "90",
                    "tier": "A 核心池",
                    "citation_key": "Robot2026World",
                })

            result = service.fetch_open_access_pdfs(project, ReviewFetchPdfOptions())

            self.assertEqual(result.created, 1)
            fetch_csv = project.path / "data/processed/fulltext_fetch_report.csv"
            with fetch_csv.open(encoding="utf-8", newline="") as f:
                fetch_rows = list(csv.DictReader(f))
            self.assertEqual(fetch_rows[0]["oa_status"], "downloaded")
            self.assertTrue(Path(fetch_rows[0]["local_pdf_path"]).exists())

            verify = service.verify_fulltext(project, ReviewVerifyOptions(check_zotero=False))
            self.assertEqual(verify.artifacts["status_counts"], {"ready_local_pdf": 1})

    def test_fetch_open_access_pdfs_can_attach_zotero_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ReviewProject(slug="world-models", topic="taxonomy of world models for embodied AI", root=Path(tmp))
            zotero = FakeZotero()
            service = LiteratureReviewService(zotero=zotero, open_access=FakeOA())
            service.init_project(project)
            with (project.path / "data/processed/paper_pool_verified.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["paper_id", "zotero_key", "title", "doi", "citation_key"], extrasaction="ignore")
                writer.writeheader()
                writer.writerow({"paper_id": "P001", "zotero_key": "ZOT1", "title": "Robot world model", "doi": "10.123/test", "citation_key": "Robot2026World"})
            with (project.path / "data/processed/paper_pool_coded.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODED_POOL_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerow({"paper_id": "P001", "zotero_key": "ZOT1", "title": "Robot world model", "tier": "A 核心池", "citation_key": "Robot2026World"})

            result = service.fetch_open_access_pdfs(project, ReviewFetchPdfOptions(attach_zotero=True))

            self.assertEqual(result.created, 1)
            self.assertEqual(len(zotero.attachments), 1)
            self.assertEqual(zotero.attachments[0][0], "ZOT1")


if __name__ == "__main__":
    unittest.main()
