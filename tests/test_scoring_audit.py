from unittest import TestCase

from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules import audit_scoring_coverage


class ScoringAuditTests(TestCase):
    def test_scoring_audit_reports_supported_and_unsupported_handlers(self) -> None:
        catalog = make_sample_catalog()

        audit = audit_scoring_coverage(catalog)

        self.assertIn("Bird Feeder", audit.supported_bonus_cards)
        self.assertIn("Test Bonus 1", audit.unsupported_bonus_cards)
        self.assertEqual(audit.round_goal_coverage, 1.0)
        self.assertEqual(
            audit.source_references["round_goals"]["rulebook"],
            "rulebook_pdfs/WS_Core_Rulebook.pdf",
        )
