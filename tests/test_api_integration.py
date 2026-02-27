import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class ParkingStatusApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(main.app)

    @staticmethod
    def _fake_fetch_json_factory(regs_rows: list[dict], meter_rows: list[dict]):
        def _fake_fetch_json(url: str):
            if "nfid-uabd" in url:
                return regs_rows
            if "693u-uax6" in url:
                return meter_rows
            return []

        return _fake_fetch_json

    def test_hydrant_override_blocks_parking(self) -> None:
        with (
            patch.object(main, "_fetch_json", side_effect=self._fake_fetch_json_factory([], [])),
            patch.object(main, "find_nearest_hydrant_distance_ft", return_value=(None, None)),
        ):
            response = self.client.get(
                "/parking-status",
                params={"hydrant_distance_ft": 12},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["parking_decision"]["status"], "blocked")
        self.assertIn("hydrant", data["parking_decision"]["primary_reason"].lower())
        self.assertIn("violation_summary", data)
        self.assertGreaterEqual(data["violation_summary"]["estimated_total_max_usd"], 115)
        hydrant_rules = [r for r in data["rules"] if r["type"] == "hydrant_proximity"]
        self.assertTrue(hydrant_rules)
        self.assertFalse(hydrant_rules[0]["valid"])
        self.assertEqual(hydrant_rules[0]["distance_ft"], 12.0)
        self.assertIsNotNone(hydrant_rules[0]["violation_estimate"])
        self.assertIn("fine_source", hydrant_rules[0]["violation_estimate"])
        self.assertIn("last_updated", hydrant_rules[0]["violation_estimate"])

    def test_loading_zone_blocks_passenger_but_allows_commercial_truck(self) -> None:
        regs = [{"order_type": "parking", "sign_desc": "Truck Loading Only"}]
        with (
            patch.object(main, "_fetch_json", side_effect=self._fake_fetch_json_factory(regs, [])),
            patch.object(main, "find_nearest_hydrant_distance_ft", return_value=(None, None)),
        ):
            passenger_resp = self.client.get(
                "/parking-status",
                params={"vehicle_type": "passenger", "commercial_plate": "false"},
            )
            truck_resp = self.client.get(
                "/parking-status",
                params={"vehicle_type": "truck", "commercial_plate": "true"},
            )

        self.assertEqual(passenger_resp.status_code, 200)
        self.assertEqual(truck_resp.status_code, 200)
        passenger = passenger_resp.json()
        truck = truck_resp.json()

        self.assertEqual(passenger["parking_decision"]["status"], "blocked")
        self.assertIn("loading", passenger["parking_decision"]["primary_reason"].lower())
        self.assertEqual(truck["parking_decision"]["status"], "safe")
        truck_rule = next(r for r in truck["rules"] if r["type"] == "truck_loading_only")
        self.assertTrue(truck_rule["valid"])

    def test_official_zone_respects_agency_profile(self) -> None:
        regs = [{"order_type": "parking", "sign_desc": "NYPD Official Vehicles Only"}]
        with (
            patch.object(main, "_fetch_json", side_effect=self._fake_fetch_json_factory(regs, [])),
            patch.object(main, "find_nearest_hydrant_distance_ft", return_value=(None, None)),
        ):
            none_resp = self.client.get("/parking-status", params={"agency_affiliation": "none"})
            police_resp = self.client.get("/parking-status", params={"agency_affiliation": "police"})

        self.assertEqual(none_resp.status_code, 200)
        self.assertEqual(police_resp.status_code, 200)
        self.assertEqual(none_resp.json()["parking_decision"]["status"], "blocked")
        self.assertEqual(police_resp.json()["parking_decision"]["status"], "safe")

    def test_auto_hydrant_lookup_adds_rule_when_found(self) -> None:
        with (
            patch.object(main, "_fetch_json", side_effect=self._fake_fetch_json_factory([], [])),
            patch.object(main, "find_nearest_hydrant_distance_ft", return_value=(18.2, "5bgh-vtsn")),
        ):
            response = self.client.get("/parking-status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        hydrant_rule = next(r for r in data["rules"] if r["type"] == "hydrant_proximity")
        self.assertTrue(hydrant_rule["valid"])
        self.assertIn("5bgh-vtsn", hydrant_rule["source"])

    def test_demo_route_returns_html(self) -> None:
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
