from datetime import UTC, datetime, timedelta
from math import cos, radians
from pathlib import Path

import requests
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from cache_store import http_json_cache
from decision_engine import derive_parking_decision
from hydrant_lookup import find_nearest_hydrant_distance_ft
from proximity_engine import evaluate_hydrant_clearance
from rule_engine import evaluate_recurring_window
from schemas import HealthResponse, ParkingRule, ParkingStatusResponse
from sign_parser import VehicleContext, parse_regulation_record
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
    gps_accuracy_m: float = Query(
        8.0,
        ge=1,
        le=50,
        description="Estimated GPS accuracy in meters; fallback warnings trigger at >=10m",
    ),
) -> ParkingStatusResponse:
    current_time = datetime.now(UTC)
    vehicle_ctx = VehicleContext(
        vehicle_type=vehicle_type,
        commercial_plate=commercial_plate,
        agency_affiliation=agency_affiliation,
    )

    rules: list[ParkingRule] = []
    next_cleaning_dt = None
    time_left_str = None

    regulations_url = (
        "https://data.cityofnewyork.us/resource/nfid-uabd.json"
        f"?$where=within_circle(the_geom, {lat}, {lon}, {radius})&$limit=50"
    )
    regs_data = _fetch_json(regulations_url)

    for reg in regs_data:
        parsed = parse_regulation_record(reg, now=current_time, vehicle=vehicle_ctx)
        rules.append(parsed)
        if parsed.type == "street_cleaning":
            if next_cleaning_dt is None and parsed.next_cleaning is not None:
                next_cleaning_dt = parsed.next_cleaning
            if time_left_str is None and parsed.time_left:
                time_left_str = parsed.time_left

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
        next_cleaning_dt = rules[0].next_cleaning
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
    elif gps_accuracy_m >= 10:
        rules.append(
            ParkingRule(
                type="hydrant_uncertain",
                description="Hydrant proximity uncertain due to GPS accuracy",
                severity="medium",
                valid=True,
                reason=f"Possible hydrant nearby (GPS accuracy ±{gps_accuracy_m:.0f}m). Check manually.",
                source="ParkGuard GPS Fallback",
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

    decision = derive_parking_decision(rules)
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
        next_cleaning=next_cleaning_dt,
    )
