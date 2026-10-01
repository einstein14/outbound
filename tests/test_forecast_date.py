from datetime import date, datetime

import pytest

from app.exceptions import InvalidDateError
from app.forecast_date import (
    daylight_for_date,
    filter_hours_for_date,
    forecast_days_for_date,
    validate_forecast_date,
)
from app.models import HourlyConditions


def _hour(day: int, hour: int = 12) -> HourlyConditions:
    return HourlyConditions(
        time=datetime(2026, 10, day, hour, 0),
        temperature=20.0,
        weather_code=1,
        weather_label="Clear",
        cloud_cover=20.0,
        precipitation_probability=5.0,
        wind_speed_mph=5.0,
        is_day=True,
    )


def test_forecast_days_for_date():
    today = date(2026, 10, 1)
    assert forecast_days_for_date(today, today) == 1
    assert forecast_days_for_date(date(2026, 10, 3), today) == 3
    assert forecast_days_for_date(date(2026, 10, 10), today) == 7


def test_validate_forecast_date_rejects_past():
    today = date(2026, 10, 5)
    with pytest.raises(InvalidDateError):
        validate_forecast_date(date(2026, 10, 4), today)


def test_validate_forecast_date_rejects_too_far():
    today = date(2026, 10, 1)
    with pytest.raises(InvalidDateError):
        validate_forecast_date(date(2026, 10, 15), today)


def test_filter_hours_for_date():
    hours = [_hour(1, 8), _hour(1, 9), _hour(2, 8)]
    filtered = filter_hours_for_date(hours, date(2026, 10, 1))
    assert len(filtered) == 2
    assert all(h.time.day == 1 for h in filtered)


def test_daylight_for_date_picks_index():
    info = daylight_for_date(
        ["2026-10-01", "2026-10-02", "2026-10-03"],
        ["2026-10-01T07:00", "2026-10-02T07:10", "2026-10-03T07:20"],
        ["2026-10-01T19:00", "2026-10-02T19:10", "2026-10-03T19:20"],
        [40000, 41000, 42000],
        date(2026, 10, 2),
    )
    assert info.sunrise == datetime(2026, 10, 2, 7, 10)
    assert info.daylight_duration_seconds == 41000
