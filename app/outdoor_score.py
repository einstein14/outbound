"""Outdoor Score heuristic and window selection."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from statistics import mean

from app.config import (
    GOOD_HOUR_THRESHOLD,
    MAX_WINDOWS,
    SCORE_WEIGHT_AIR_QUALITY,
    SCORE_WEIGHT_CLOUD_COVER,
    SCORE_WEIGHT_DAYLIGHT,
    SCORE_WEIGHT_POLLEN,
    SCORE_WEIGHT_RAIN,
    SCORE_WEIGHT_TEMPERATURE,
    SCORE_WEIGHT_WIND,
)
from app.models import DaylightInfo, HourlyConditions, OutdoorWindow, PollenSpecies, ScoredHour
from app.services.daylight import daylight_fraction


def fahrenheit_to_celsius(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def temperature_to_celsius(temp: float, unit: str) -> float:
    if unit == "fahrenheit":
        return fahrenheit_to_celsius(temp)
    return temp


def score_daylight(fraction: float) -> float:
    if fraction < 0.15 or fraction > 0.85:
        return 7.0
    return 10.0


def score_temperature_celsius(temp_c: float) -> float:
    if 15.5 <= temp_c <= 25.5:
        return 10.0
    if temp_c < -7:
        return 0.0
    if temp_c > 38:
        return 0.0
    if temp_c < 15.5:
        return max(0.0, 10.0 * (temp_c + 7) / (15.5 + 7))
    return max(0.0, 10.0 * (38 - temp_c) / (38 - 25.5))


def score_rain(probability: float) -> float:
    if probability <= 10:
        return 10.0
    if probability >= 100:
        return 0.0
    return max(0.0, 10.0 - (probability - 10) * 10.0 / 90.0)


def score_cloud_cover(percent: float) -> float:
    if 20 <= percent <= 45:
        return 10.0
    if percent <= 10:
        return 8.0
    if percent <= 20:
        return 8.0 + (percent - 10) * 0.2
    if percent <= 70:
        return max(2.0, 10.0 - (percent - 45) * 8.0 / 25.0)
    return max(0.0, 2.0 - (percent - 70) * 2.0 / 30.0)


def score_wind(mph: float) -> float:
    if mph <= 8:
        return 10.0
    if mph >= 40:
        return 0.0
    return max(0.0, 10.0 - (mph - 8) * 10.0 / 32.0)


def score_us_aqi(aqi: float) -> float:
    if aqi <= 50:
        return 10.0
    if aqi <= 100:
        return 10.0 - (aqi - 50) * 4.0 / 50.0
    if aqi <= 150:
        return 6.0 - (aqi - 100) * 3.0 / 50.0
    if aqi <= 200:
        return 3.0 - (aqi - 150) * 2.0 / 50.0
    return 0.0


def score_pollen_upi(upi: int) -> float:
    """Google Universal Pollen Index 0–5; lower is better for outdoor comfort."""
    if upi <= 0:
        return 10.0
    if upi >= 5:
        return 0.0
    return max(0.0, 10.0 - upi * 2.0)


def score_pollen(grains: float) -> float:
    if grains <= 0:
        return 10.0
    if grains <= 20:
        return 10.0 - grains * 2.0 / 20.0
    if grains <= 50:
        return 8.0 - (grains - 20) * 3.0 / 30.0
    if grains <= 100:
        return 5.0 - (grains - 50) * 3.0 / 50.0
    return 0.0


def _base_weights() -> dict[str, float]:
    return {
        "daylight": SCORE_WEIGHT_DAYLIGHT,
        "temperature": SCORE_WEIGHT_TEMPERATURE,
        "rain": SCORE_WEIGHT_RAIN,
        "cloud_cover": SCORE_WEIGHT_CLOUD_COVER,
        "wind": SCORE_WEIGHT_WIND,
        "air_quality": SCORE_WEIGHT_AIR_QUALITY,
        "pollen": SCORE_WEIGHT_POLLEN,
    }


def active_weights(
    include_air_quality: bool,
    include_pollen: bool,
) -> dict[str, float]:
    weights = _base_weights()
    if not include_pollen:
        weights.pop("pollen", None)
    if not include_air_quality:
        weights.pop("air_quality", None)
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def compute_hour_score(
    hour: HourlyConditions,
    daylight: DaylightInfo,
    temperature_unit: str,
    location_has_air_quality: bool,
    location_has_pollen: bool,
) -> ScoredHour:
    include_aq = location_has_air_quality and hour.us_aqi is not None
    include_pollen = location_has_pollen and hour.pollen is not None
    weights = active_weights(include_aq, include_pollen)
    temp_c = temperature_to_celsius(hour.temperature, temperature_unit)
    fraction = daylight_fraction(hour.time, daylight)

    factors: dict[str, float] = {
        "daylight": score_daylight(fraction),
        "temperature": score_temperature_celsius(temp_c),
        "rain": score_rain(hour.precipitation_probability),
        "cloud_cover": score_cloud_cover(hour.cloud_cover),
        "wind": score_wind(hour.wind_speed_mph),
    }
    if include_aq:
        factors["air_quality"] = score_us_aqi(hour.us_aqi)
    if include_pollen and hour.pollen is not None:
        pollen = hour.pollen
        if pollen.source == "google" and pollen.upi is not None:
            factors["pollen"] = score_pollen_upi(pollen.upi)
        elif pollen.grains_per_m3 is not None:
            factors["pollen"] = score_pollen(pollen.grains_per_m3)

    total = sum(factors[k] * weights[k] for k in factors if k in weights)
    return ScoredHour(
        hour=hour,
        factor_scores=factors,
        outdoor_score=round(total, 1),
        active_weights=weights,
    )


def format_time_range(start: datetime, end: datetime) -> str:
    """End is exclusive (start of hour after the window)."""
    def fmt(d: datetime) -> str:
        s = d.strftime("%I:%M %p")
        if s.startswith("0"):
            s = s[1:]
        return s

    return f"{fmt(start)}–{fmt(end)}"


def _window_explanation(
    avg_cloud: float,
    avg_rain: float,
    avg_aqi: float | None,
    avg_pollen: float | None,
    weather_label: str,
) -> str:
    parts: list[str] = []
    if avg_cloud <= 35 and avg_rain <= 15:
        parts.append("Bright and comfortable conditions")
    elif avg_rain <= 25:
        parts.append("Mostly comfortable outdoor conditions")
    else:
        parts.append("Mixed conditions")

    if avg_rain <= 15:
        parts.append("with low rain probability")
    elif avg_rain <= 40:
        parts.append("with moderate rain chance")
    else:
        parts.append("with higher rain chance")

    if avg_aqi is not None and avg_aqi <= 50:
        parts.append("and good air quality")
    elif avg_aqi is not None and avg_aqi <= 100:
        parts.append("and moderate air quality")

    if avg_pollen is not None and avg_pollen <= 20:
        parts.append("and low pollen")
    elif avg_pollen is not None and avg_pollen > 50:
        parts.append("with elevated pollen")

    text = " ".join(parts)
    if not text.endswith("."):
        text += "."
    return text.capitalize()


def group_windows(scored_hours: list[ScoredHour]) -> list[tuple[list[ScoredHour], bool]]:
    """Group consecutive hours at or above threshold; also collect sub-threshold stretches."""
    if not scored_hours:
        return []

    good_groups: list[list[ScoredHour]] = []
    current: list[ScoredHour] = []
    for sh in scored_hours:
        if sh.outdoor_score >= GOOD_HOUR_THRESHOLD:
            current.append(sh)
        else:
            if current:
                good_groups.append(current)
                current = []
    if current:
        good_groups.append(current)

    all_groups: list[tuple[list[ScoredHour], bool]] = [
        (g, False) for g in good_groups
    ]

    if len(good_groups) < MAX_WINDOWS:
        sub_threshold: list[ScoredHour] = []
        for sh in scored_hours:
            if sh.outdoor_score < GOOD_HOUR_THRESHOLD:
                sub_threshold.append(sh)
            else:
                if sub_threshold:
                    all_groups.append((sub_threshold, True))
                    sub_threshold = []
        if sub_threshold:
            all_groups.append((sub_threshold, True))

    return all_groups


def _group_to_window(group: list[ScoredHour], limited: bool) -> OutdoorWindow:
    start = group[0].hour.time
    end = group[-1].hour.time + timedelta(hours=1)
    avg_temp = mean(h.hour.temperature for h in group)
    avg_cloud = mean(h.hour.cloud_cover for h in group)
    avg_rain = mean(h.hour.precipitation_probability for h in group)
    avg_wind = mean(h.hour.wind_speed_mph for h in group)
    avg_score = mean(h.outdoor_score for h in group)

    aqi_values = [h.hour.us_aqi for h in group if h.hour.us_aqi is not None]
    avg_aqi = mean(aqi_values) if aqi_values else None

    pollen_readings = [h.hour.pollen for h in group if h.hour.pollen is not None]
    avg_pollen = None
    dominant_species: PollenSpecies | None = None
    avg_pollen_upi: int | None = None
    pollen_category: str | None = None
    if pollen_readings:
        if pollen_readings[0].source == "google":
            upi_values = [p.upi for p in pollen_readings if p.upi is not None]
            if upi_values:
                avg_pollen_upi = round(mean(upi_values))
                pollen_category = pollen_readings[0].category
        else:
            grain_values = [p.grains_per_m3 for p in pollen_readings if p.grains_per_m3 is not None]
            if grain_values:
                avg_pollen = mean(grain_values)
        species_counts = Counter(p.species for p in pollen_readings)
        dominant_species = species_counts.most_common(1)[0][0]

    labels = [h.hour.weather_label for h in group]
    dominant_label = Counter(labels).most_common(1)[0][0]

    return OutdoorWindow(
        start=start,
        end=end,
        avg_temperature=round(avg_temp, 1),
        avg_cloud_cover=round(avg_cloud, 0),
        avg_precipitation_probability=round(avg_rain, 0),
        avg_wind_speed_mph=round(avg_wind, 1),
        avg_us_aqi=round(avg_aqi, 0) if avg_aqi is not None else None,
        avg_pollen_grains=round(avg_pollen, 1) if avg_pollen is not None else None,
        avg_pollen_upi=avg_pollen_upi,
        pollen_category=pollen_category,
        dominant_pollen_species=dominant_species,
        dominant_weather_label=dominant_label,
        outdoor_score=round(avg_score, 1),
        explanation=_window_explanation(avg_cloud, avg_rain, avg_aqi, avg_pollen, dominant_label),
        is_limited_day=limited,
    )


def select_top_windows(scored_hours: list[ScoredHour]) -> list[OutdoorWindow]:
    groups = group_windows(scored_hours)
    windows = [_group_to_window(g, limited) for g, limited in groups]
    windows.sort(key=lambda w: w.outdoor_score, reverse=True)
    return windows[:MAX_WINDOWS]
