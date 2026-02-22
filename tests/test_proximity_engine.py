import unittest

from proximity_engine import (
    distance_meters,
    evaluate_hydrant_clearance,
    meters_to_feet,
)


class HydrantClearanceTests(unittest.TestCase):
    def test_hydrant_blocked_under_threshold(self) -> None:
        result = evaluate_hydrant_clearance(12.0, threshold_ft=15.0)
        self.assertTrue(result.blocked)
        self.assertEqual(result.rule_type, "hydrant_proximity")
        self.assertEqual(result.severity, "high")
        self.assertIn("Too close to hydrant", result.reason)

    def test_hydrant_allowed_at_threshold(self) -> None:
        result = evaluate_hydrant_clearance(15.0, threshold_ft=15.0)
        self.assertFalse(result.blocked)
        self.assertEqual(result.severity, "low")
        self.assertIn("Hydrant clearance ok", result.reason)


class DistanceMathTests(unittest.TestCase):
    def test_zero_distance(self) -> None:
        self.assertAlmostEqual(distance_meters(40.0, -73.0, 40.0, -73.0), 0.0, places=4)

    def test_small_distance_is_positive(self) -> None:
        d = distance_meters(40.7580, -73.9855, 40.7581, -73.9855)
        self.assertGreater(d, 0.0)
        self.assertLess(d, 30.0)

    def test_meters_to_feet(self) -> None:
        self.assertAlmostEqual(meters_to_feet(1.0), 3.28084, places=5)


if __name__ == "__main__":
    unittest.main()
