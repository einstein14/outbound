"""Build the full outdoor report from user location input."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from app.config import GOOGLE_POLLEN_API_KEY, TemperatureUnit
from app.day_summary import summarize_day
from app.forecast_date import (
    forecast_days_for_date,
    today_in_timezone,
    validate_forecast_date,
)
from app.models import (
    CurrentConditions,
    HourlyConditions,
    OutdoorReport,
    PollenReading,
    PollenSource,
    ScoredHour,
)
from app.outdoor_score import compute_hour_score, select_top_windows
from app.services.air_quality import fetch_air_quality
from app.services.daylight import filter_daylight_hours
from app.services.geocoding import geocode_location
from app.services.pollen_google import fetch_google_pollen_for_date
from app.services.weather import fetch_weather_forecast
from app.weather_codes import us_aqi_band


def _merge_air_quality(
    hours: list[HourlyConditions],
    aq_hourly,
) -> tuple[list[HourlyConditions], bool]:
    """Join AQI and pollen onto weather hours by timestamp."""
    any_aqi = False
    merged: list[HourlyConditions] = []
    for hour in hours:
        aqi, pollen = aq_hourly.for_time(hour.time)
        if aqi is not None:
            any_aqi = True
        merged.append(
            hour.model_copy(
                update={
                    "us_aqi": aqi,
                    "pollen": pollen,
                }
            )
        )
    return merged, any_aqi


def _apply_daily_pollen(
    hours: list[HourlyConditions],
    target: date,
    pollen: PollenReading,
) -> list[HourlyConditions]:
    return [
        h.model_copy(update={"pollen": pollen}) if h.time.date() == target else h
        for h in hours
    ]


async def build_report(
    location: str,
    temperature_unit: TemperatureUnit = "celsius",
    forecast_date: date | None = None,
) -> OutdoorReport:
    pollen_source: PollenSource | None = None
    google_pollen_note: str | None = None

    async with httpx.AsyncClient() as client:
        place = await geocode_location(location, client=client)
        today_local = today_in_timezone(place.timezone)
        target = forecast_date or today_local
        validate_forecast_date(target, today_local)
        days = forecast_days_for_date(target, today_local)
        is_today = target == today_local

        hourly, daylight, current = await fetch_weather_forecast(
            place.latitude,
            place.longitude,
            temperature_unit,
            forecast_days=days,
            target_date=target,
            include_current=is_today,
            client=client,
        )
        aq_result = await fetch_air_quality(
            place.latitude,
            place.longitude,
            forecast_days=days,
            include_current=is_today,
            client=client,
        )

        hourly, has_hourly_aqi = _merge_air_quality(hourly, aq_result.hourly)
        has_pollen = aq_result.pollen_available
        if has_pollen:
            pollen_source = "open_meteo"

        google_reading: PollenReading | None = None
        if not has_pollen and GOOGLE_POLLEN_API_KEY:
            google_result = await fetch_google_pollen_for_date(
                place.latitude,
                place.longitude,
                target,
                today_local,
                client=client,
            )
            google_pollen_note = google_result.note
            if google_result.reading:
                google_reading = google_result.reading
                hourly = _apply_daily_pollen(hourly, target, google_reading)
                has_pollen = True
                pollen_source = "google"

    daylight_hours = filter_daylight_hours(hourly, daylight)

    has_air_quality = aq_result.success and (
        has_hourly_aqi or aq_result.current_us_aqi is not None
    )

    scored: list[ScoredHour] = [
        compute_hour_score(
            h,
            daylight,
            temperature_unit,
            location_has_air_quality=has_air_quality,
            location_has_pollen=has_pollen,
        )
        for h in daylight_hours
    ]

    windows = select_top_windows(scored)
    day_summary = summarize_day(scored)

    enriched_current: CurrentConditions | None = None
    if current and is_today:
        aqi = aq_result.current_us_aqi
        pollen = aq_result.current_pollen or google_reading
        outdoor_score = None
        for sh in scored:
            hour_start = sh.hour.time.replace(minute=0, second=0, microsecond=0)
            block_end = hour_start + timedelta(hours=1)
            if hour_start <= current.time < block_end:
                outdoor_score = sh.outdoor_score
                break
        if outdoor_score is None and scored:
            outdoor_score = min(
                scored,
                key=lambda sh: abs((sh.hour.time - current.time).total_seconds()),
            ).outdoor_score

        enriched_current = current.model_copy(
            update={
                "us_aqi": aqi,
                "us_aqi_band": us_aqi_band(aqi) if aqi is not None else None,
                "pollen": pollen,
                "outdoor_score": outdoor_score,
            }
        )

    pollen_note = None
    if has_pollen and pollen_source == "google":
        pollen_note = "Pollen from Google Pollen API (daily index)."
    elif has_pollen and pollen_source == "open_meteo":
        pollen_note = None
    elif GOOGLE_POLLEN_API_KEY:
        pollen_note = google_pollen_note or "Pollen data unavailable for this date."
    else:
        pollen_note = "Pollen forecast is only available in Europe (Open-Meteo). Add GOOGLE_POLLEN_API_KEY for US coverage."

    return OutdoorReport(
        location=place,
        temperature_unit=temperature_unit,
        forecast_date=target,
        is_today=is_today,
        daylight=daylight,
        current=enriched_current,
        day_summary=day_summary,
        hourly_timeline=scored,
        windows=windows,
        pollen_available=has_pollen,
        pollen_source=pollen_source,
        air_quality_available=has_air_quality,
        air_quality_note=aq_result.note,
        pollen_note=pollen_note,
    )


def build_report_sync(
    location: str,
    temperature_unit: TemperatureUnit = "celsius",
    forecast_date: date | None = None,
) -> OutdoorReport:
    import asyncio

    return asyncio.run(
        build_report(
            location,
            temperature_unit=temperature_unit,
            forecast_date=forecast_date,
        )
    )
