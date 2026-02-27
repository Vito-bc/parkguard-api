import unittest

from schemas import ParkingRule
from violations import estimate_violation_for_rule, summarize_violations


class ViolationsTests(unittest.TestCase):
    def test_estimate_for_blocked_hydrant(self) -> None:
        rule = ParkingRule(
            type="hydrant_proximity",
            description="Hydrant clearance",
            valid=False,
            source="test",
        )
        estimate = estimate_violation_for_rule(rule)
        self.assertIsNotNone(estimate)
        self.assertEqual(estimate.violation_code, "NYC-HYDRANT-15FT")
        self.assertEqual(estimate.max_fine_usd, 115)
        self.assertIsNotNone(estimate.fine_source)
        self.assertIsNotNone(estimate.last_updated)

    def test_no_estimate_when_rule_valid(self) -> None:
        rule = ParkingRule(
            type="street_cleaning",
            description="ASP",
            valid=True,
            source="test",
        )
        self.assertIsNone(estimate_violation_for_rule(rule))

    def test_summary_aggregates_estimates(self) -> None:
        rule1 = ParkingRule(type="hydrant_proximity", description="Hydrant", valid=False, source="test")
        rule2 = ParkingRule(type="street_cleaning", description="ASP", valid=False, source="test")
        e1 = estimate_violation_for_rule(rule1)
        e2 = estimate_violation_for_rule(rule2)
        rules = [
            rule1.model_copy(update={"violation_estimate": e1}),
            rule2.model_copy(update={"violation_estimate": e2}),
        ]
        summary = summarize_violations(rules)
        self.assertGreater(summary.estimated_total_max_usd, 0)
        self.assertEqual(summary.highest_single_max_usd, 115)
        self.assertGreaterEqual(summary.high_risk_violations, 1)


if __name__ == "__main__":
    unittest.main()
