from __future__ import annotations

from schemas import ParkingRule


def derive_parking_decision(rules: list[ParkingRule]) -> dict:
    blocked_reasons: list[str] = []
    caution_reasons: list[str] = []
    risk_score = 0

    for rule in rules:
        if rule.type == "street_cleaning" and rule.active_now:
            blocked_reasons.append(rule.reason or "Street cleaning active now")
            risk_score = max(risk_score, 95)
            continue

        if rule.type in {"loading_only", "truck_loading_only"} and not rule.valid:
            blocked_reasons.append(rule.reason or rule.description)
            risk_score = max(risk_score, 92)
            continue

        if rule.type in {"taxi_only", "fhv_only"} and not rule.valid:
            blocked_reasons.append(rule.reason or rule.description)
            risk_score = max(risk_score, 93)
            continue

        if rule.type in {"fire_zone", "emergency_access", "official_vehicle_only", "hydrant_proximity"} and not rule.valid:
            blocked_reasons.append(rule.reason or rule.description)
            risk_score = max(risk_score, 97 if rule.type == "hydrant_proximity" else 94)
            continue

        if rule.type == "hydrant_uncertain":
            caution_reasons.append(rule.reason or "Possible hydrant nearby. Check manually.")
            risk_score = max(risk_score, 55)
            continue

        if rule.type in {"no_standing", "no parking"} and not rule.valid:
            blocked_reasons.append(rule.description)
            risk_score = max(risk_score, 90)
            continue

        if rule.type in {"street_cleaning", "no_standing"} and not rule.active_now and rule.time_left:
            caution_reasons.append(rule.reason or f"{rule.type.replace('_', ' ')} starts in {rule.time_left}")
            risk_score = max(risk_score, 60)
            continue

        if rule.type == "metered" and rule.valid:
            caution_reasons.append("Meter payment required")
            risk_score = max(risk_score, 30)
            continue

    if blocked_reasons:
        return {
            "status": "blocked",
            "risk_score": risk_score or 90,
            "primary_reason": blocked_reasons[0],
            "recommended_action": "Do not park here. Move to another spot.",
        }

    if caution_reasons:
        return {
            "status": "caution",
            "risk_score": risk_score or 50,
            "primary_reason": caution_reasons[0],
            "recommended_action": "Parking may be allowed now, but review restrictions.",
        }

    return {
        "status": "safe",
        "risk_score": 10,
        "primary_reason": "No active restrictions detected in current rule set.",
        "recommended_action": "Proceed to park, then verify on-street signage.",
    }
