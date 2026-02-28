from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from rule_engine import evaluate_recurring_window
from schemas import ParkingRule


@dataclass(frozen=True)
class VehicleContext:
    vehicle_type: str
    commercial_plate: bool
    agency_affiliation: str


def _format_duration_seconds(seconds: float) -> str:
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m"


def _extract_day_spec_from_text(text: str) -> str | None:
    lower = text.lower()
    day_tokens = ("mon-fri", "monday-friday", "weekdays", "daily", "weekends", "sat-sun")
    for token in day_tokens:
        if token in lower:
            if token in {"monday-friday", "weekdays"}:
                return "Mon-Fri"
            if token == "sat-sun":
                return "Sat-Sun"
            return token.title()
    return None


def _extract_time_window_from_text(text: str) -> tuple[str | None, str | None]:
    pattern = re.compile(
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None, None

    def to_24h(hour_str: str, minute_str: str | None, ampm: str) -> str:
        hour = int(hour_str) % 12
        if ampm.lower() == "pm":
            hour += 12
        minute = int(minute_str) if minute_str else 0
        return f"{hour:02d}:{minute:02d}"

    start = to_24h(match.group(1), match.group(2), match.group(3))
    end = to_24h(match.group(4), match.group(5), match.group(6))
    return start, end


def parse_regulation_record(
    reg: dict,
    *,
    now: datetime | None = None,
    vehicle: VehicleContext,
) -> ParkingRule:
    current_time = now or datetime.now(UTC)

    rule_type = str(reg.get("order_type", "unknown")).lower()
    description = reg.get("sign_desc") or reg.get("description") or "No description"
    description_lower = description.lower()
    valid = True

    is_cleaning = "clean" in rule_type or "alternate side" in description_lower
    if is_cleaning:
        start_time = reg.get("time_from", "06:00")
        end_time = reg.get("time_to", "09:00")
        days_spec = reg.get("days", "Mon-Fri")
        eval_result = evaluate_recurring_window(
            now=current_time,
            days_spec=days_spec,
            start_time=start_time,
            end_time=end_time,
        )
        time_left = _format_duration_seconds(eval_result.countdown.total_seconds())
        return ParkingRule(
            type="street_cleaning",
            description=description,
            next_cleaning=eval_result.next_start,
            window=f"{start_time} - {end_time}",
            time_left=time_left,
            active_now=eval_result.active_now,
            severity="high" if eval_result.active_now else "medium",
            valid=not eval_result.active_now,
            reason=(
                f"Street cleaning active now (ends in {time_left})"
                if eval_result.active_now
                else f"Street cleaning starts in {time_left}"
            ),
            source="NYC DOT Sweeping Schedule",
        )

    is_no_standing = rule_type == "no_standing" or "no standing" in description_lower
    if is_no_standing:
        start_time = reg.get("time_from")
        end_time = reg.get("time_to")
        days_spec = reg.get("days")
        if not start_time or not end_time:
            parsed_start, parsed_end = _extract_time_window_from_text(description)
            start_time = start_time or parsed_start
            end_time = end_time or parsed_end
        if not days_spec:
            days_spec = _extract_day_spec_from_text(description) or "Mon-Fri"

        if start_time and end_time:
            eval_result = evaluate_recurring_window(
                now=current_time,
                days_spec=days_spec,
                start_time=start_time,
                end_time=end_time,
            )
            time_left = _format_duration_seconds(eval_result.countdown.total_seconds())
            return ParkingRule(
                type="no_standing",
                description=description,
                window=f"{start_time} - {end_time}",
                time_left=time_left,
                active_now=eval_result.active_now,
                severity="high" if eval_result.active_now else "medium",
                valid=not eval_result.active_now,
                reason=(
                    f"No standing active now (ends in {time_left})"
                    if eval_result.active_now
                    else f"No standing starts in {time_left}"
                ),
                source="NYC DOT Sign",
            )

    is_loading_zone = any(
        token in description_lower
        for token in ("loading", "truck loading", "commercial vehicles only", "trucks only")
    )
    if is_loading_zone:
        allows_truck = "truck" in description_lower or "commercial" in description_lower
        allows_loading = "loading" in description_lower
        can_use_loading_zone = (
            vehicle.vehicle_type == "truck" and vehicle.commercial_plate and (allows_truck or allows_loading)
        )
        return ParkingRule(
            type="truck_loading_only" if "truck" in description_lower else "loading_only",
            description=description,
            severity="high" if not can_use_loading_zone else "medium",
            valid=can_use_loading_zone,
            reason=(
                "Loading/truck-only zone. Requires commercial truck profile."
                if not can_use_loading_zone
                else "Commercial truck profile matches loading/truck-only zone."
            ),
            source="NYC DOT Sign",
        )

    is_taxi_zone = any(
        token in description_lower
        for token in ("taxi stand", "taxi only", "taxicab", "taxi zone")
    )
    is_fhv_zone = any(token in description_lower for token in ("for-hire", "for hire", "fhv", "tlc")) and any(
        token in description_lower
        for token in ("stand", "pickup", "pick-up", "only", "zone")
    )
    if is_taxi_zone or is_fhv_zone:
        if is_taxi_zone:
            allowed = vehicle.vehicle_type == "taxi"
            rule_kind = "taxi_only"
            zone_label = "Taxi-only zone"
        else:
            allowed = vehicle.vehicle_type in {"fhv", "taxi"}
            rule_kind = "fhv_only"
            zone_label = "FHV/TLC zone"
        return ParkingRule(
            type=rule_kind,
            description=description,
            severity="low" if allowed else "high",
            valid=allowed,
            reason=(
                f"{zone_label} matches current vehicle profile."
                if allowed
                else f"{zone_label}. Current vehicle type '{vehicle.vehicle_type}' is not eligible."
            ),
            source="NYC DOT Sign",
        )

    is_fire_zone = any(
        token in description_lower
        for token in ("fire zone", "fire lane", "fire department", "fdny", "emergency access")
    )
    if is_fire_zone:
        allowed = vehicle.agency_affiliation == "fire"
        return ParkingRule(
            type="fire_zone",
            description=description,
            severity="high",
            eligible_vehicle_types=["fire"],
            valid=allowed,
            reason=(
                "Fire/emergency zone reserved for authorized fire access."
                if not allowed
                else "Authorized fire-agency vehicle profile."
            ),
            source="NYC DOT Sign",
        )

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
        if any(token in description_lower for token in ("police", "nypd")):
            eligible = ["police"]
        elif any(token in description_lower for token in ("fire", "fdny")):
            eligible = ["fire"]
        elif "school" in description_lower:
            eligible = ["school"]
        else:
            eligible = ["city", "police", "fire", "school"]

        allowed = vehicle.agency_affiliation in eligible
        return ParkingRule(
            type="official_vehicle_only",
            description=description,
            severity="high" if not allowed else "low",
            eligible_vehicle_types=eligible,
            valid=allowed,
            reason=(
                f"Reserved for {', '.join(eligible)} vehicles."
                if not allowed
                else "Authorized agency profile matches reserved spot."
            ),
            source="NYC DOT Sign",
        )

    fine = 65 if ("standing" in rule_type or "parking" in rule_type) else 0
    return ParkingRule(
        type=rule_type,
        description=description,
        fine=fine,
        severity="high" if fine else "low",
        valid=valid,
        source="NYC DOT Sign",
    )
