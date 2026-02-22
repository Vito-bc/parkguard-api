from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


FEET_PER_METER = 3.28084


@dataclass
class ClearanceEvaluation:
    rule_type: str
    distance_ft: float
    threshold_ft: float
    blocked: bool
    severity: str
    reason: str


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance using haversine formula."""
    r = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return r * c


def meters_to_feet(value_m: float) -> float:
    return value_m * FEET_PER_METER


def evaluate_hydrant_clearance(
    distance_ft: float,
    *,
    threshold_ft: float = 15.0,
) -> ClearanceEvaluation:
    blocked = distance_ft < threshold_ft
    if blocked:
        reason = f"Too close to hydrant: {distance_ft:.1f} ft (minimum {threshold_ft:.0f} ft)."
        severity = "high"
    else:
        reason = f"Hydrant clearance ok: {distance_ft:.1f} ft from nearest hydrant."
        severity = "low"

    return ClearanceEvaluation(
        rule_type="hydrant_proximity",
        distance_ft=round(distance_ft, 1),
        threshold_ft=threshold_ft,
        blocked=blocked,
        severity=severity,
        reason=reason,
    )
