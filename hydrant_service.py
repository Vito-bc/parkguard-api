from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from proximity_engine import evaluate_hydrant_clearance
from schemas import ParkingRule


def build_hydrant_rules(
    *,
    lat: float,
    lon: float,
    radius: int,
    hydrant_distance_ft: float | None,
    gps_accuracy_m: float,
    lookup_fn: Callable[..., tuple[float | None, str | None]],
) -> tuple[list[ParkingRule], dict]:
    now = datetime.now(UTC)
    freshness = {
        "status": "none",
        "cache_hit": None,
        "fetched_at": now,
    }

    rules: list[ParkingRule] = []
    resolved_hydrant_distance_ft = hydrant_distance_ft
    hydrant_source = "ParkGuard Hydrant Proximity (demo scaffold)"

    if resolved_hydrant_distance_ft is not None:
        freshness["status"] = "override"
    else:
        resolved_hydrant_distance_ft, hydrant_dataset_id = lookup_fn(
            lat=lat,
            lon=lon,
            search_radius_m=max(radius, 75),
        )
        if hydrant_dataset_id:
            hydrant_source = f"NYC Open Data Hydrants ({hydrant_dataset_id})"
            freshness["status"] = "lookup_hit"
        else:
            freshness["status"] = "lookup_miss"

    if resolved_hydrant_distance_ft is not None:
        hydrant_eval = evaluate_hydrant_clearance(resolved_hydrant_distance_ft, threshold_ft=15.0)
        rules.append(
            ParkingRule(
                type=hydrant_eval.rule_type,
                description="Fire hydrant clearance rule",
                distance_ft=hydrant_eval.distance_ft,
                threshold_ft=hydrant_eval.threshold_ft,
                severity=hydrant_eval.severity,
                valid=not hydrant_eval.blocked,
                reason=hydrant_eval.reason,
                source=hydrant_source,
            )
        )
        return rules, freshness

    if gps_accuracy_m >= 10:
        rules.append(
            ParkingRule(
                type="hydrant_uncertain",
                description="Hydrant proximity uncertain due to GPS accuracy",
                severity="medium",
                valid=True,
                reason=f"Possible hydrant nearby (GPS accuracy +/-{gps_accuracy_m:.0f}m). Check manually.",
                source="ParkGuard GPS Fallback",
            )
        )
        freshness["status"] = "gps_fallback"

    return rules, freshness
