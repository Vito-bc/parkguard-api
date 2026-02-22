from datetime import UTC, datetime, timedelta
from math import cos, radians

import requests
from fastapi import FastAPI, Query

from schemas import HealthResponse, ParkingRule, ParkingStatusResponse

app = FastAPI(
    title="ParkGuard API",
    description="NYC parking intelligence API prototype for connected vehicles",
    version="0.1.0",
)

REQUEST_TIMEOUT_SECONDS = 5


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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


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
            window = f"{reg.get('time_from', '06:00')} - {reg.get('time_to', '09:00')}"

            # Placeholder schedule logic for MVP demo.
            next_cleaning = current_time + timedelta(days=1)
            next_cleaning_iso = next_cleaning.isoformat()
            time_left_str = _format_duration(next_cleaning - current_time)

            rules.append(
                ParkingRule(
                    type="street_cleaning",
                    description=description,
                    next_cleaning=next_cleaning,
                    window=window,
                    time_left=time_left_str,
                    valid=valid,
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
                valid=meter_valid,
                reason=None if meter_valid else "Inactive or outside operating hours",
                source="NYC Parking Meters",
            )
        )

    if not rules:
        rules = [
            ParkingRule(
                type="street_cleaning",
                description="Alternate Side Parking (demo fallback)",
                next_cleaning=current_time + timedelta(days=1),
                window="06:00 - 09:00",
                time_left="24h 0m",
                valid=True,
                source="ParkGuard Demo",
            )
        ]
        next_cleaning_iso = rules[0].next_cleaning.isoformat() if rules[0].next_cleaning else None
        time_left_str = rules[0].time_left

    warning = None
    if time_left_str:
        warning = f"Cannot park here - street cleaning in {time_left_str}"

    return ParkingStatusResponse(
        location={
            "lat": lat,
            "lon": lon,
            "radius_m": radius,
            "address": "NYC address lookup not implemented yet",
            "timestamp": current_time,
        },
        rules=rules,
        confidence=0.98 if rules else 0.5,
        warning=warning,
        sources={
            "regulations": "NYC Open Data (nfid-uabd)",
            "meters": "NYC Open Data (693u-uax6)",
        },
        next_cleaning=next_cleaning_iso,
    )
