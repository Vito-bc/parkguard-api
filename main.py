from datetime import UTC, datetime, timedelta
from math import cos, radians
from pathlib import Path

import requests
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from rule_engine import evaluate_recurring_window
from schemas import HealthResponse, ParkingRule, ParkingStatusResponse

app = FastAPI(
    title="ParkGuard API",
    description="NYC parking intelligence API prototype for connected vehicles",
    version="0.1.0",
)

REQUEST_TIMEOUT_SECONDS = 5
DEMO_HTML_PATH = Path(__file__).parent / "demo" / "index.html"


def _fetch_json(url: str) -> list[dict]:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
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

    decision = _derive_parking_decision(rules)
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
        rules=rules,
        parking_decision=decision,
        confidence=0.98 if rules else 0.5,
        warning=warning,
        sources={
            "regulations": "NYC Open Data (nfid-uabd)",
            "meters": "NYC Open Data (693u-uax6)",
        },
        next_cleaning=next_cleaning_iso,
    )
