from unittest import TestCase

from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules import audit_power_coverage, audit_rule_coverage, audit_scoring_coverage


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
        self.assertEqual(audit.source_references["round_goals"]["page"], 11)
        self.assertEqual(audit.source_references["bonus_cards"]["page"], 11)

    def test_power_and_combined_rule_audit_reports_coverage(self) -> None:
        catalog = make_sample_catalog()

        power_audit = audit_power_coverage(catalog)
        rule_audit = audit_rule_coverage(catalog)

        self.assertEqual(power_audit.total_birds, len(catalog.birds))
        self.assertEqual(power_audit.implementation_coverage, 1.0)
        self.assertEqual(rule_audit["powers"]["unsupported_power_count"], 0)
        self.assertIn("handler_source_references", rule_audit["powers"])
        self.assertIn("source_references", rule_audit["scoring"])
