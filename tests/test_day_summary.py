from datetime import datetime

from app.day_summary import summarize_day
from app.models import HourlyConditions, PollenReading, ScoredHour


def _scored(
    temp: float,
    label: str,
    aqi: float | None = None,
    pollen: PollenReading | None = None,
    score: float = 8.0,
) -> ScoredHour:
    hour = HourlyConditions(
        time=datetime(2026, 10, 3, 12, 0),
        temperature=temp,
        weather_code=1,
        weather_label=label,
        cloud_cover=20.0,
        precipitation_probability=5.0,
        wind_speed_mph=5.0,
        is_day=True,
        us_aqi=aqi,
        pollen=pollen,
    )
    return ScoredHour(
        hour=hour,
        factor_scores={},
        outdoor_score=score,
        active_weights={},
    )


def test_summarize_day_empty():
    assert summarize_day([]) is None


def test_summarize_day_aggregates():
    hours = [
        _scored(14.0, "Clear", aqi=40.0, score=8.0),
        _scored(18.0, "Clear", aqi=60.0, score=9.0),
        _scored(16.0, "Partly cloudy", aqi=50.0, score=7.0),
    ]
    summary = summarize_day(hours)
    assert summary is not None
    assert summary.avg_temperature == 16.0
    assert summary.min_temperature == 14.0
    assert summary.max_temperature == 18.0
    assert summary.dominant_weather_label == "Clear"
    assert summary.avg_us_aqi == 50.0
    assert summary.avg_outdoor_score == 8.0


def test_summarize_day_no_aqi():
    summary = summarize_day([_scored(20.0, "Clear", aqi=None)])
    assert summary is not None
    assert summary.avg_us_aqi is None
    assert summary.us_aqi_band is None


def test_summarize_day_peak_pollen():
    low = PollenReading(source="open_meteo", species="grass", grains_per_m3=10.0)
    high = PollenReading(source="open_meteo", species="birch", grains_per_m3=25.0)
    summary = summarize_day(
        [
            _scored(20.0, "Clear", pollen=low),
            _scored(20.0, "Clear", pollen=high),
        ]
    )
    assert summary is not None
    assert summary.peak_pollen is not None
    assert summary.peak_pollen.species == "birch"
    assert summary.peak_pollen.grains_per_m3 == 25.0
