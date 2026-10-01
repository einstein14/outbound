"""Day-level summary from scored daylight hours."""

from __future__ import annotations

from collections import Counter
from statistics import mean

from app.models import DaySummary, PollenReading, ScoredHour
from app.weather_codes import us_aqi_band


def _pollen_is_higher(candidate: PollenReading, current: PollenReading | None) -> bool:
    if current is None:
        return True
    if candidate.source == "google" and candidate.upi is not None:
        if current.source == "google" and current.upi is not None:
            return candidate.upi > current.upi
        return True
    if candidate.grains_per_m3 is not None and current.grains_per_m3 is not None:
        return candidate.grains_per_m3 > current.grains_per_m3
    return candidate.grains_per_m3 is not None


def summarize_day(scored_hours: list[ScoredHour]) -> DaySummary | None:
    if not scored_hours:
        return None

    temps = [sh.hour.temperature for sh in scored_hours]
    labels = [sh.hour.weather_label for sh in scored_hours]
    dominant_label = Counter(labels).most_common(1)[0][0]

    aqi_values = [sh.hour.us_aqi for sh in scored_hours if sh.hour.us_aqi is not None]
    avg_aqi = mean(aqi_values) if aqi_values else None

    peak_pollen: PollenReading | None = None
    for sh in scored_hours:
        pollen = sh.hour.pollen
        if pollen is None:
            continue
        if _pollen_is_higher(pollen, peak_pollen):
            peak_pollen = pollen

    return DaySummary(
        avg_temperature=round(mean(temps), 1),
        min_temperature=round(min(temps), 1),
        max_temperature=round(max(temps), 1),
        dominant_weather_label=dominant_label,
        avg_us_aqi=round(avg_aqi, 0) if avg_aqi is not None else None,
        us_aqi_band=us_aqi_band(avg_aqi) if avg_aqi is not None else None,
        avg_outdoor_score=round(mean(sh.outdoor_score for sh in scored_hours), 1),
        peak_pollen=peak_pollen,
    )
