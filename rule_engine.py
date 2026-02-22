from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/New_York"

DAY_TO_INDEX = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "weds": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass
class RestrictionWindowEvaluation:
    active_now: bool
    next_start: datetime
    current_start: datetime | None
    current_end: datetime | None
    countdown: timedelta
    countdown_mode: str  # until_start | until_end
    timezone: str


def parse_days_spec(days_spec: str | None) -> set[int]:
    if not days_spec:
        return {0, 1, 2, 3, 4}

    raw = days_spec.strip().lower()
    if raw in {"daily", "everyday", "all", "all days"}:
        return set(range(7))
    if raw in {"weekdays", "mon-fri"}:
        return {0, 1, 2, 3, 4}
    if raw in {"weekends", "sat-sun"}:
        return {5, 6}

    normalized = (
        raw.replace("&", ",")
        .replace("/", ",")
        .replace(" and ", ",")
        .replace(";", ",")
    )
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    result: set[int] = set()

    for part in parts:
        if "-" in part:
            start_token, end_token = [p.strip() for p in part.split("-", 1)]
            if start_token in DAY_TO_INDEX and end_token in DAY_TO_INDEX:
                start_idx = DAY_TO_INDEX[start_token]
                end_idx = DAY_TO_INDEX[end_token]
                if start_idx <= end_idx:
                    result.update(range(start_idx, end_idx + 1))
                else:
                    result.update(range(start_idx, 7))
                    result.update(range(0, end_idx + 1))
            continue

        if part in DAY_TO_INDEX:
            result.add(DAY_TO_INDEX[part])

    return result or {0, 1, 2, 3, 4}


def parse_time_value(value: str | None, fallback: time) -> time:
    if not value:
        return fallback

    candidate = value.strip().upper()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(candidate, fmt).time()
        except ValueError:
            continue
    return fallback


def evaluate_recurring_window(
    *,
    now: datetime,
    days_spec: str | None,
    start_time: str | None,
    end_time: str | None,
    timezone_name: str = DEFAULT_TZ,
) -> RestrictionWindowEvaluation:
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)

    active_days = parse_days_spec(days_spec)
    start_t = parse_time_value(start_time, fallback=time(6, 0))
    end_t = parse_time_value(end_time, fallback=time(9, 0))

    def build_window(anchor: datetime) -> tuple[datetime, datetime]:
        start_dt = anchor.replace(
            hour=start_t.hour,
            minute=start_t.minute,
            second=start_t.second,
            microsecond=0,
        )
        end_dt = anchor.replace(
            hour=end_t.hour,
            minute=end_t.minute,
            second=end_t.second,
            microsecond=0,
        )
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return start_dt, end_dt

    # Check active state today.
    current_start = None
    current_end = None
    active_now = False
    if local_now.weekday() in active_days:
        today_start, today_end = build_window(local_now)
        if today_start <= local_now < today_end:
            active_now = True
            current_start, current_end = today_start, today_end

    # Find next start (today in the future or upcoming day).
    next_start = None
    for offset in range(0, 8):
        day_anchor = local_now + timedelta(days=offset)
        if day_anchor.weekday() not in active_days:
            continue
        start_dt, _ = build_window(day_anchor)
        if start_dt >= local_now:
            next_start = start_dt
            break

    # If active now and today's start is in the past, "next_start" should be the next occurrence.
    if next_start is None:
        # Defensive fallback for degenerate parsing outcomes.
        next_start = (local_now + timedelta(days=1)).replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)

    if active_now and current_end is not None:
        countdown = current_end - local_now
        countdown_mode = "until_end"
    else:
        countdown = next_start - local_now
        countdown_mode = "until_start"

    return RestrictionWindowEvaluation(
        active_now=active_now,
        next_start=next_start,
        current_start=current_start,
        current_end=current_end,
        countdown=countdown,
        countdown_mode=countdown_mode,
        timezone=timezone_name,
    )
