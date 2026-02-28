from __future__ import annotations

from schemas import ParkingRule


def parse_meter_record(meter: dict) -> ParkingRule:
    meter_status = str(meter.get("status", "")).lower()
    meter_valid = meter_status == "active"
    return ParkingRule(
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
