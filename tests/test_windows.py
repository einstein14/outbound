from datetime import datetime

from app.models import HourlyConditions, ScoredHour
from app.outdoor_score import select_top_windows


def _scored(hour: int, score: float) -> ScoredHour:
    h = HourlyConditions(
        time=datetime(2026, 10, 1, hour, 0),
        temperature=20.0,
        weather_code=1,
        weather_label="Clear",
        cloud_cover=25.0,
        precipitation_probability=5.0,
        wind_speed_mph=5.0,
        is_day=True,
    )
    return ScoredHour(
        hour=h,
        factor_scores={},
        outdoor_score=score,
        active_weights={},
    )


def test_consecutive_hours_merge():
    hours = [_scored(8, 8.0), _scored(9, 8.5), _scored(10, 8.2)]
    windows = select_top_windows(hours)
    assert len(windows) == 1
    assert windows[0].start.hour == 8
    assert windows[0].end.hour == 11


def test_bad_hour_splits_windows():
    hours = [_scored(8, 8.0), _scored(9, 5.0), _scored(10, 8.0)]
    windows = select_top_windows(hours)
    good_windows = [w for w in windows if not w.is_limited_day]
    assert len(good_windows) == 2


def test_top_three_cap():
    hours = [
        _scored(8, 9.0),
        _scored(10, 8.5),
        _scored(12, 8.0),
        _scored(14, 7.5),
        _scored(16, 7.2),
    ]
    windows = select_top_windows(hours)
    assert len(windows) <= 3
