from datetime import datetime

from app.models import DaylightInfo, HourlyConditions, PollenReading
from app.outdoor_score import (
    active_weights,
    compute_hour_score,
    score_cloud_cover,
    score_pollen,
    score_pollen_upi,
    score_rain,
    score_temperature_celsius,
    score_us_aqi,
    score_wind,
    temperature_to_celsius,
)


def _hour(**kwargs) -> HourlyConditions:
    defaults = {
        "time": datetime(2026, 10, 1, 12, 0),
        "temperature": 20.0,
        "weather_code": 1,
        "weather_label": "Mostly clear",
        "cloud_cover": 30.0,
        "precipitation_probability": 5.0,
        "wind_speed_mph": 6.0,
        "is_day": True,
        "us_aqi": 40.0,
        "pollen": PollenReading(source="open_meteo", species="grass", grains_per_m3=10.0),
    }
    defaults.update(kwargs)
    return HourlyConditions(**defaults)


def _daylight() -> DaylightInfo:
    return DaylightInfo(
        sunrise=datetime(2026, 10, 1, 7, 0),
        sunset=datetime(2026, 10, 1, 19, 0),
        daylight_duration_seconds=12 * 3600,
    )


def test_temperature_comfort_peak():
    assert score_temperature_celsius(20.0) == 10.0


def test_temperature_same_conditions_fahrenheit_celsius():
    c_score = score_temperature_celsius(20.0)
    f_temp = 20.0 * 9 / 5 + 32
    assert score_temperature_celsius(temperature_to_celsius(f_temp, "fahrenheit")) == c_score


def test_rain_scoring():
    assert score_rain(5) == 10.0
    assert score_rain(100) == 0.0


def test_cloud_cover_scoring():
    assert score_cloud_cover(30) == 10.0
    assert score_cloud_cover(90) < score_cloud_cover(30)


def test_wind_scoring():
    assert score_wind(5) == 10.0
    assert score_wind(50) == 0.0


def test_us_aqi_scoring():
    assert score_us_aqi(30) == 10.0
    assert score_us_aqi(250) == 0.0


def test_pollen_scoring():
    assert score_pollen(0) == 10.0
    assert score_pollen(120) == 0.0


def test_pollen_upi_scoring():
    assert score_pollen_upi(0) == 10.0
    assert score_pollen_upi(5) == 0.0
    assert score_pollen_upi(2) == 6.0


def test_google_pollen_in_hour_score():
    hour = _hour(
        pollen=PollenReading(source="google", species="ragweed", upi=2, category="Low"),
    )
    scored = compute_hour_score(
        hour,
        _daylight(),
        "celsius",
        location_has_air_quality=False,
        location_has_pollen=True,
    )
    assert "pollen" in scored.factor_scores


def test_missing_pollen_renormalizes_weights():
    w = active_weights(include_air_quality=True, include_pollen=False)
    assert "pollen" not in w
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_missing_aq_and_pollen_renormalizes():
    w = active_weights(include_air_quality=False, include_pollen=False)
    assert "air_quality" not in w
    assert "pollen" not in w
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_night_hours_not_scored_in_pipeline():
    hour = _hour(is_day=False)
    scored = compute_hour_score(
        hour,
        _daylight(),
        "celsius",
        location_has_air_quality=True,
        location_has_pollen=True,
    )
    assert scored.outdoor_score >= 0
