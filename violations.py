from __future__ import annotations

from dataclasses import dataclass

from schemas import ParkingRule, ViolationEstimate, ViolationSummary


@dataclass(frozen=True)
class _FineBand:
    min_usd: int
    max_usd: int
    violation_code: str
    confidence: float
    note: str


NYC_FINE_BANDS: dict[str, _FineBand] = {
    "hydrant_proximity": _FineBand(115, 115, "NYC-HYDRANT-15FT", 0.95, "NYC hydrant clearance violation."),
    "no_standing": _FineBand(95, 115, "NYC-NO-STANDING", 0.8, "No standing violation estimate by zone/time."),
    "no parking": _FineBand(65, 115, "NYC-NO-PARKING", 0.8, "No parking violation estimate by zone/time."),
    "street_cleaning": _FineBand(65, 65, "NYC-ASP", 0.9, "Alternate-side parking estimate."),
    "truck_loading_only": _FineBand(95, 115, "NYC-TRUCK-LOADING", 0.75, "Truck/loading-only curb misuse estimate."),
    "loading_only": _FineBand(95, 115, "NYC-LOADING-ONLY", 0.75, "Loading-only curb misuse estimate."),
    "taxi_only": _FineBand(95, 115, "NYC-TAXI-ONLY", 0.7, "Taxi stand curb misuse estimate."),
    "fhv_only": _FineBand(95, 115, "NYC-FHV-ONLY", 0.7, "FHV/TLC curb misuse estimate."),
    "fire_zone": _FineBand(115, 150, "NYC-FIRE-ZONE", 0.7, "Emergency/fire access obstruction estimate."),
    "official_vehicle_only": _FineBand(95, 150, "NYC-OFFICIAL-ONLY", 0.65, "Official vehicle-only zone misuse estimate."),
}


def estimate_violation_for_rule(rule: ParkingRule) -> ViolationEstimate | None:
    # Metered parking is a compliance/payment reminder in this MVP, not a direct ticket assertion.
    if rule.type == "metered":
        return None

    # No violation estimate if rule currently allows parking.
    if rule.valid:
        return None

    band = NYC_FINE_BANDS.get(rule.type)
    if band is None:
        return None

    return ViolationEstimate(
        violation_code=band.violation_code,
        min_fine_usd=band.min_usd,
        max_fine_usd=band.max_usd,
        confidence=band.confidence,
        note=band.note,
    )


def summarize_violations(rules: list[ParkingRule]) -> ViolationSummary:
    estimates = [r.violation_estimate for r in rules if r.violation_estimate is not None]
    if not estimates:
        return ViolationSummary(
            estimated_total_min_usd=0,
            estimated_total_max_usd=0,
            highest_single_max_usd=0,
            high_risk_violations=0,
        )

    total_min = sum(e.min_fine_usd for e in estimates)
    total_max = sum(e.max_fine_usd for e in estimates)
    highest = max(e.max_fine_usd for e in estimates)
    high_risk = sum(1 for e in estimates if e.max_fine_usd >= 115)

    return ViolationSummary(
        estimated_total_min_usd=total_min,
        estimated_total_max_usd=total_max,
        highest_single_max_usd=highest,
        high_risk_violations=high_risk,
    )
