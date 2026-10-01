"""Forecast date validation and slicing (location-local timezone)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import MAX_FORECAST_DAYS
from app.exceptions import InvalidDateError
from app.models import DaylightInfo, HourlyConditions


def today_in_timezone(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def validate_forecast_date(target: date, today_local: date) -> None:
    if target < today_local:
        raise InvalidDateError("Please choose today or a future date.")
    max_date = today_local.toordinal() + (MAX_FORECAST_DAYS - 1)
    if target.toordinal() > max_date:
        raise InvalidDateError(
            f"Forecasts are available up to {MAX_FORECAST_DAYS} days ahead "
            f"(through {date.fromordinal(max_date).isoformat()} for this location)."
        )


def forecast_days_for_date(target: date, today_local: date) -> int:
    days = (target - today_local).days + 1
    return min(max(days, 1), MAX_FORECAST_DAYS)


def filter_hours_for_date(
    hours: list[HourlyConditions],
    target: date,
) -> list[HourlyConditions]:
    return [h for h in hours if h.time.date() == target]


def daylight_for_date(
    daily_times: list[str],
    daily_sunrise: list[str],
    daily_sunset: list[str],
    daily_duration: list[int],
    target: date,
) -> DaylightInfo:
    target_iso = target.isoformat()
    index = None
    for i, day_str in enumerate(daily_times):
        if day_str == target_iso or day_str.startswith(target_iso):
            index = i
            break
    if index is None:
        raise InvalidDateError(
            "No forecast is available for that date. Try another day within the next week."
        )
    return DaylightInfo(
        sunrise=datetime.fromisoformat(daily_sunrise[index]),
        sunset=datetime.fromisoformat(daily_sunset[index]),
        daylight_duration_seconds=int(daily_duration[index]),
    )
