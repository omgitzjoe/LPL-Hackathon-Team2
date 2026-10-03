import unittest

from backend import compliance
from backend.bedrock_client import _mock_draft
from backend.mock_clients import get_client

CLIENT = get_client("C-1001")
GOOD = _mock_draft(CLIENT, "Draft a portfolio review for Jane Doe")


def rule_ids(result, severity=None):
    return {f["rule_id"] for f in result["findings"] if severity in (None, f["severity"])}


class ComplianceTests(unittest.TestCase):
    def test_standard_mock_draft_passes(self):
        result = compliance.check_draft(GOOD, CLIENT)
        self.assertTrue(result["passed"], result["findings"])
        self.assertEqual(result["blocking"], 0)

    def test_guaranteed_return_is_blocked(self):
        result = compliance.check_draft(GOOD + "\nThis strategy offers guaranteed returns.", CLIENT)
        self.assertFalse(result["passed"])
        self.assertIn("PROMISSORY_LANGUAGE", rule_ids(result, "block"))

    def test_negated_guarantee_is_allowed(self):
        text = GOOD + "\nPast performance does not guarantee future results."
        self.assertTrue(compliance.check_draft(text, CLIENT)["passed"])

    def test_risk_free_claim_is_blocked(self):
        result = compliance.check_draft(GOOD + "\nThis bond fund is risk-free.", CLIENT)
        self.assertIn("PROMISSORY_LANGUAGE", rule_ids(result, "block"))

    def test_missing_disclosures_and_draft_marker_are_blocked(self):
        result = compliance.check_draft("Dear Jane Doe, your portfolio is doing well.", CLIENT)
        ids = rule_ids(result, "block")
        self.assertTrue(
            {"MISSING_DRAFT_MARKER", "MISSING_DISCLOSURE_INFORMATIONAL",
             "MISSING_DISCLOSURE_PAST_PERFORMANCE", "MISSING_SUITABILITY"} <= ids
        )

    def test_placeholder_and_ssn_are_blocked(self):
        text = GOOD + "\n[Advisor Name] TBD  SSN 123-45-6789"
        ids = rule_ids(compliance.check_draft(text, CLIENT), "block")
        self.assertIn("PLACEHOLDER_TEXT", ids)
        self.assertIn("SENSITIVE_SSN", ids)

    def test_projection_and_superlative_only_warn(self):
        text = GOOD + "\nOur best fund has projected returns of 9% and will outperform."
        result = compliance.check_draft(text, CLIENT)
        self.assertTrue(result["passed"])
        self.assertTrue({"PERFORMANCE_PROJECTION", "SUPERLATIVE_CLAIM", "FUTURE_RESULT_CLAIM"} <= rule_ids(result, "warn"))

    def test_best_interest_is_not_a_superlative(self):
        text = GOOD + "\nWe act in your best interest."
        self.assertNotIn("SUPERLATIVE_CLAIM", rule_ids(compliance.check_draft(text, CLIENT)))

    def test_wrong_client_name_warns(self):
        result = compliance.check_draft(GOOD.replace("Jane Doe", "Someone Else"), CLIENT)
        self.assertIn("CLIENT_NAME_MISSING", rule_ids(result, "warn"))

    def test_empty_draft_is_blocked(self):
        self.assertFalse(compliance.check_draft("   ", CLIENT)["passed"])

    def test_summary_is_stable_and_flat(self):
        summary = compliance.summarize(compliance.check_draft("hello", CLIENT))
        self.assertEqual(summary, sorted(set(summary)))
        self.assertTrue(all(":" in s for s in summary))


if __name__ == "__main__":
    unittest.main()
