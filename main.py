from datetime import UTC, datetime, timedelta
from math import cos, radians
from pathlib import Path

import requests
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from cache_store import http_json_cache
from hydrant_lookup import find_nearest_hydrant_distance_ft
from proximity_engine import evaluate_hydrant_clearance
from rule_engine import evaluate_recurring_window
from schemas import HealthResponse, ParkingRule, ParkingStatusResponse
from violations import estimate_violation_for_rule, summarize_violations

app = FastAPI(
    title="ParkGuard API",
    description="NYC parking intelligence API prototype for connected vehicles",
    version="0.1.0",
)

REQUEST_TIMEOUT_SECONDS = 5
HTTP_JSON_CACHE_TTL_SECONDS = 60
DEMO_HTML_PATH = Path(__file__).parent / "demo" / "index.html"


def _fetch_json(url: str) -> list[dict]:
    cached = http_json_cache.get(url)
    if isinstance(cached, list):
        return cached

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        rows = data if isinstance(data, list) else []
        http_json_cache.set(url, rows, ttl_seconds=HTTP_JSON_CACHE_TTL_SECONDS)
        return rows
    except (requests.RequestException, ValueError):
        return []


def _format_duration(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m"


def _derive_parking_decision(rules: list[ParkingRule]) -> dict:
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

        if rule.type in {"no_standing", "no parking"} and not rule.valid:
            blocked_reasons.append(rule.description)
            risk_score = max(risk_score, 90)
            continue

        if rule.type == "street_cleaning" and not rule.active_now and rule.time_left:
            caution_reasons.append(rule.reason or f"Street cleaning starts in {rule.time_left}")
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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/demo", include_in_schema=False, response_model=None, response_class=HTMLResponse)
def demo_page() -> Response:
    if DEMO_HTML_PATH.exists():
        return FileResponse(DEMO_HTML_PATH)
    return HTMLResponse("<h1>Demo page not found</h1>", status_code=404)


@app.get("/parking-status", response_model=ParkingStatusResponse)
def get_parking_status(
    lat: float = Query(40.7128, description="Latitude"),
    lon: float = Query(-74.0060, description="Longitude"),
    radius: int = Query(50, ge=1, le=500, description="Search radius in meters"),
    vehicle_type: str = Query(
        "passenger",
        pattern="^(passenger|truck|taxi|fhv)$",
        description="Vehicle class",
    ),
    commercial_plate: bool = Query(False, description="Commercial plate status"),
    agency_affiliation: str = Query(
        "none",
        pattern="^(none|police|fire|city|school)$",
        description="Agency affiliation",
    ),
    hydrant_distance_ft: float | None = Query(
        None,
        ge=0,
        le=200,
        description="Optional nearest hydrant distance override for demo/scaffold",
    ),
) -> ParkingStatusResponse:
    current_time = datetime.now(UTC)

    rules: list[ParkingRule] = []
    next_cleaning_iso = None
    time_left_str = None

    regulations_url = (
        "https://data.cityofnewyork.us/resource/nfid-uabd.json"
        f"?$where=within_circle(the_geom, {lat}, {lon}, {radius})&$limit=50"
    )
    regs_data = _fetch_json(regulations_url)

    for reg in regs_data:
        rule_type = str(reg.get("order_type", "unknown")).lower()
        description = reg.get("sign_desc") or reg.get("description") or "No description"
        valid = True
        description_lower = description.lower()

        is_cleaning = "clean" in rule_type or "alternate side" in description.lower()
        if is_cleaning:
            start_time = reg.get("time_from", "06:00")
            end_time = reg.get("time_to", "09:00")
            days_spec = reg.get("days", "Mon-Fri")
            window = f"{start_time} - {end_time}"

            evaluation = evaluate_recurring_window(
                now=current_time,
                days_spec=days_spec,
                start_time=start_time,
                end_time=end_time,
            )
            next_cleaning = evaluation.next_start
            next_cleaning_iso = next_cleaning.isoformat()
            time_left_str = _format_duration(evaluation.countdown)
            can_park_now = not evaluation.active_now
            severity = "high" if evaluation.active_now else "medium"
            reason = (
                f"Street cleaning active now (ends in {time_left_str})"
                if evaluation.active_now
                else f"Street cleaning starts in {time_left_str}"
            )

            rules.append(
                ParkingRule(
                    type="street_cleaning",
                    description=description,
                    next_cleaning=next_cleaning,
                    window=window,
                    time_left=time_left_str,
                    active_now=evaluation.active_now,
                    severity=severity,
                    valid=can_park_now,
                    reason=reason,
                    source="NYC DOT Sweeping Schedule",
                )
            )
            continue

        is_loading_zone = any(
            token in description_lower
            for token in ("loading", "truck loading", "commercial vehicles only", "trucks only")
        )
        if is_loading_zone:
            allows_truck = "truck" in description_lower or "commercial" in description_lower
            allows_loading = "loading" in description_lower
            can_use_loading_zone = (
                vehicle_type == "truck"
                and commercial_plate
                and (allows_truck or allows_loading)
            )
            reason = None
            severity = "medium"
            if not can_use_loading_zone:
                reason = (
                    "Loading/truck-only zone. Requires commercial truck profile."
                )
                severity = "high"
            else:
                reason = "Commercial truck profile matches loading/truck-only zone."

            rules.append(
                ParkingRule(
                    type="truck_loading_only" if "truck" in description_lower else "loading_only",
                    description=description,
                    severity=severity,
                    valid=can_use_loading_zone,
                    reason=reason,
                    source="NYC DOT Sign",
                )
            )
            continue

        is_taxi_zone = any(
            token in description_lower
            for token in ("taxi stand", "taxi only", "taxicab", "taxi zone")
        )
        is_fhv_zone = any(
            token in description_lower
            for token in ("for-hire", "for hire", "fhv", "tlc")
        ) and any(
            token in description_lower
            for token in ("stand", "pickup", "pick-up", "only", "zone")
        )

        if is_taxi_zone or is_fhv_zone:
            if is_taxi_zone:
                allowed = vehicle_type == "taxi"
                rule_kind = "taxi_only"
                zone_label = "Taxi-only zone"
            else:
                allowed = vehicle_type in {"fhv", "taxi"}
                rule_kind = "fhv_only"
                zone_label = "FHV/TLC zone"

            severity = "low" if allowed else "high"
            reason = (
                f"{zone_label} matches current vehicle profile."
                if allowed
                else f"{zone_label}. Current vehicle type '{vehicle_type}' is not eligible."
            )
            rules.append(
                ParkingRule(
                    type=rule_kind,
                    description=description,
                    severity=severity,
                    valid=allowed,
                    reason=reason,
                    source="NYC DOT Sign",
                )
            )
            continue

        is_fire_zone = any(
            token in description_lower
            for token in ("fire zone", "fire lane", "fire department", "fdny", "emergency access")
        )
        if is_fire_zone:
            eligible_agencies = ["fire"]
            allowed = agency_affiliation == "fire"
            rules.append(
                ParkingRule(
                    type="fire_zone",
                    description=description,
                    severity="high",
                    eligible_vehicle_types=eligible_agencies,
                    valid=allowed,
                    reason=(
                        "Fire/emergency zone reserved for authorized fire access."
                        if not allowed
                        else "Authorized fire-agency vehicle profile."
                    ),
                    source="NYC DOT Sign",
                )
            )
            continue

        is_official_zone = any(
            token in description_lower
            for token in (
                "police only",
                "nypd",
                "department vehicles only",
                "official vehicles only",
                "authorized vehicles only",
                "government vehicles only",
                "agency vehicles only",
            )
        )
        if is_official_zone:
            eligible_agencies: list[str] = []
            if any(token in description_lower for token in ("police", "nypd")):
                eligible_agencies = ["police"]
            elif any(token in description_lower for token in ("fire", "fdny")):
                eligible_agencies = ["fire"]
            elif "school" in description_lower:
                eligible_agencies = ["school"]
            else:
                eligible_agencies = ["city", "police", "fire", "school"]

            allowed = agency_affiliation in eligible_agencies
            rules.append(
                ParkingRule(
                    type="official_vehicle_only",
                    description=description,
                    severity="high" if not allowed else "low",
                    eligible_vehicle_types=eligible_agencies,
                    valid=allowed,
                    reason=(
                        f"Reserved for {', '.join(eligible_agencies)} vehicles."
                        if not allowed
                        else "Authorized agency profile matches reserved spot."
                    ),
                    source="NYC DOT Sign",
                )
            )
            continue

        fine = 65 if ("standing" in rule_type or "parking" in rule_type) else 0
        rules.append(
            ParkingRule(
                type=rule_type,
                description=description,
                fine=fine,
                severity="high" if fine else "low",
                valid=valid,
                source="NYC DOT Sign",
            )
        )

    lat_delta = radius / 111_000
    lon_scale = max(cos(radians(lat)), 0.1)
    lon_delta = radius / (111_000 * lon_scale)
    min_lat, max_lat = lat - lat_delta, lat + lat_delta
    min_lon, max_lon = lon - lon_delta, lon + lon_delta

    meters_url = (
        "https://data.cityofnewyork.us/resource/693u-uax6.json"
        f"?$where=lat between {min_lat} and {max_lat} and long between {min_lon} and {max_lon}"
        "&$limit=10"
    )
    meters_data = _fetch_json(meters_url)

    for meter in meters_data:
        meter_status = str(meter.get("status", "")).lower()
        meter_valid = meter_status == "active"
        rules.append(
            ParkingRule(
                type="metered",
                description=meter.get("meter_hours", "Pay & Display"),
                rate="3.50 USD/hour",
                max_time=meter.get("max_time", "2 hours"),
                hours=meter.get("hours", "08:00 - 20:00 Mon-Fri"),
                active_now=meter_valid,
                severity="low" if meter_valid else "info",
                valid=meter_valid,
                reason=None if meter_valid else "Inactive or outside operating hours",
                source="NYC Parking Meters",
            )
        )

    if not rules:
        fallback_eval = evaluate_recurring_window(
            now=current_time,
            days_spec="Mon-Fri",
            start_time="06:00",
            end_time="09:00",
        )
        rules = [
            ParkingRule(
                type="street_cleaning",
                description="Alternate Side Parking (demo fallback)",
                next_cleaning=fallback_eval.next_start,
                window="06:00 - 09:00",
                time_left=_format_duration(fallback_eval.countdown),
                active_now=fallback_eval.active_now,
                severity="medium",
                valid=not fallback_eval.active_now,
                reason="Demo fallback rule",
                source="ParkGuard Demo",
            )
        ]
        next_cleaning_iso = rules[0].next_cleaning.isoformat() if rules[0].next_cleaning else None
        time_left_str = rules[0].time_left

    resolved_hydrant_distance_ft = hydrant_distance_ft
    hydrant_source = "ParkGuard Hydrant Proximity (demo scaffold)"
    if resolved_hydrant_distance_ft is None:
        resolved_hydrant_distance_ft, hydrant_dataset_id = find_nearest_hydrant_distance_ft(
            lat=lat,
            lon=lon,
            search_radius_m=max(radius, 75),
        )
        if hydrant_dataset_id:
            hydrant_source = f"NYC Open Data Hydrants ({hydrant_dataset_id})"

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

    enriched_rules: list[ParkingRule] = []
    for rule in rules:
        estimate = estimate_violation_for_rule(rule)
        if estimate is None:
            enriched_rules.append(rule)
            continue
        enriched_rules.append(rule.model_copy(update={"violation_estimate": estimate}))

    rules = enriched_rules

    decision = _derive_parking_decision(rules)
    violation_summary = summarize_violations(rules)
    warning = None
    street_cleaning_rule = next(
        (rule for rule in rules if rule.type == "street_cleaning"),
        None,
    )
    if decision["status"] == "blocked":
        warning = decision["primary_reason"]
    elif street_cleaning_rule and street_cleaning_rule.active_now:
        warning = street_cleaning_rule.reason or "Cannot park here - street cleaning active"
    elif time_left_str:
        warning = f"Caution: street cleaning starts in {time_left_str}"

    return ParkingStatusResponse(
        location={
            "lat": lat,
            "lon": lon,
            "radius_m": radius,
            "address": "NYC address lookup not implemented yet",
            "timestamp": current_time,
        },
        vehicle_profile={
            "vehicle_type": vehicle_type,
            "commercial_plate": commercial_plate,
            "agency_affiliation": agency_affiliation,
        },
        rules=rules,
        parking_decision=decision,
        violation_summary=violation_summary,
        confidence=0.98 if rules else 0.5,
        warning=warning,
        sources={
            "regulations": "NYC Open Data (nfid-uabd)",
            "meters": "NYC Open Data (693u-uax6)",
        },
        next_cleaning=next_cleaning_iso,
    )
