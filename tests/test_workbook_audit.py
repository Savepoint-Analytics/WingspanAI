from pathlib import Path
from unittest import TestCase, skipIf

from wingspan_ai.content.workbook_audit import audit_workbook

WORKBOOK_PATH = Path("wingspan-card-list.xlsx")


@skipIf(not WORKBOOK_PATH.exists(), "wingspan-card-list.xlsx is not present in the repo root")
class WorkbookAuditTests(TestCase):
    def test_card_workbook_shape_is_recognized(self) -> None:
        audit = audit_workbook(WORKBOOK_PATH)

        self.assertEqual(audit.sheets["Birds"].row_count, 707)
        self.assertEqual(audit.sheets["Bonus"].row_count, 60)
        self.assertEqual(audit.sheets["Goals"].row_count, 56)
        self.assertIn("__Solver__", audit.ignored_sheets)

    def test_expansion_coverage_includes_base_and_expansions(self) -> None:
        audit = audit_workbook(WORKBOOK_PATH)
        bird_coverage = audit.expansion_coverage["Birds"]

        self.assertEqual(bird_coverage["core"], 180)
        self.assertEqual(bird_coverage["european"], 81)
        self.assertEqual(bird_coverage["oceania"], 95)
        self.assertEqual(bird_coverage["asia"], 90)
        self.assertEqual(bird_coverage["americas"], 111)

    def test_audit_flags_known_normalization_needs(self) -> None:
        audit = audit_workbook(WORKBOOK_PATH)
        issue_summary = {(issue.sheet, issue.field, issue.message) for issue in audit.issues}

        self.assertIn(
            (
                "Birds",
                "Wingspan",
                "non-numeric wingspan; normalize as variable or unknown wingspan",
            ),
            issue_summary,
        )
        self.assertIn(
            (
                "Goals",
                "round_end_scoring",
                "placement scoring columns are blank; likely duet/map goal",
            ),
            issue_summary,
        )
