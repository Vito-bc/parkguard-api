from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from schemas import ParkingRule, ViolationEstimate, ViolationSummary


FINE_CATALOG_PATH = Path(__file__).parent / "data" / "nyc_fines.json"


@dataclass(frozen=True)
class _FineBand:
    min_usd: int
    max_usd: int
    violation_code: str
    confidence: float
    note: str
    fine_source: str
    last_updated: str


@lru_cache(maxsize=1)
def _load_fine_bands() -> dict[str, _FineBand]:
    default_source = "ParkGuard internal NYC MVP mapping"
    default_updated = "2026-02-27"
    fallback = {
        "hydrant_proximity": _FineBand(115, 115, "NYC-HYDRANT-15FT", 0.95, "NYC hydrant clearance violation.", default_source, default_updated),
        "street_cleaning": _FineBand(65, 65, "NYC-ASP", 0.9, "Alternate-side parking estimate.", default_source, default_updated),
        "truck_loading_only": _FineBand(95, 115, "NYC-TRUCK-LOADING", 0.75, "Truck/loading-only curb misuse estimate.", default_source, default_updated),
        "loading_only": _FineBand(95, 115, "NYC-LOADING-ONLY", 0.75, "Loading-only curb misuse estimate.", default_source, default_updated),
        "taxi_only": _FineBand(95, 115, "NYC-TAXI-ONLY", 0.7, "Taxi stand curb misuse estimate.", default_source, default_updated),
        "fhv_only": _FineBand(95, 115, "NYC-FHV-ONLY", 0.7, "FHV/TLC curb misuse estimate.", default_source, default_updated),
        "fire_zone": _FineBand(115, 150, "NYC-FIRE-ZONE", 0.7, "Emergency/fire access obstruction estimate.", default_source, default_updated),
        "official_vehicle_only": _FineBand(95, 150, "NYC-OFFICIAL-ONLY", 0.65, "Official vehicle-only zone misuse estimate.", default_source, default_updated),
        "no_standing": _FineBand(95, 115, "NYC-NO-STANDING", 0.8, "No standing violation estimate by zone/time.", default_source, default_updated),
        "no parking": _FineBand(65, 115, "NYC-NO-PARKING", 0.8, "No parking violation estimate by zone/time.", default_source, default_updated),
    }

    try:
        payload = json.loads(FINE_CATALOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback

    source = str(payload.get("source", default_source))
    last_updated = str(payload.get("last_updated", default_updated))
    rules = payload.get("rules")
    if not isinstance(rules, dict):
        return fallback

    mapped: dict[str, _FineBand] = {}
    for rule_type, spec in rules.items():
        if not isinstance(spec, dict):
            continue
        try:
            mapped[str(rule_type)] = _FineBand(
                min_usd=int(spec["min_fine_usd"]),
                max_usd=int(spec["max_fine_usd"]),
                violation_code=str(spec["violation_code"]),
                confidence=float(spec.get("confidence", 0.7)),
                note=str(spec.get("note", "")),
                fine_source=str(spec.get("fine_source", source)),
                last_updated=str(spec.get("last_updated", last_updated)),
            )
        except (KeyError, TypeError, ValueError):
            continue

    return mapped or fallback


def estimate_violation_for_rule(rule: ParkingRule) -> ViolationEstimate | None:
    if rule.type == "metered":
        return None

    if rule.valid:
        return None

    band = _load_fine_bands().get(rule.type)
    if band is None:
        return None

    return ViolationEstimate(
        violation_code=band.violation_code,
        min_fine_usd=band.min_usd,
        max_fine_usd=band.max_usd,
        confidence=band.confidence,
        note=band.note,
        fine_source=band.fine_source,
        last_updated=band.last_updated,
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
