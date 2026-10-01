"""Daylight helpers: duration formatting and daylight-hour filtering."""

from __future__ import annotations

from datetime import datetime

from app.models import DaylightInfo, HourlyConditions


def format_daylight_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if minutes:
        return f"{hours} h {minutes} min"
    return f"{hours} h"


def filter_daylight_hours(
    hours: list[HourlyConditions],
    daylight: DaylightInfo,
) -> list[HourlyConditions]:
    """Keep hours marked as daylight by the forecast (`is_day == 1`)."""
    return [h for h in hours if h.is_day]


def daylight_fraction(hour_time: datetime, daylight: DaylightInfo) -> float:
    """0 at sunrise, 1 at sunset — position within today's daylight span."""
    start = daylight.sunrise
    end = daylight.sunset
    total = (end - start).total_seconds()
    if total <= 0:
        return 0.5
    elapsed = (hour_time - start).total_seconds()
    return max(0.0, min(1.0, elapsed / total))
