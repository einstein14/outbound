"""Open-Meteo Air Quality API: US AQI and pollen by hour."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import AIR_QUALITY_API_URL, HTTP_TIMEOUT_SECONDS
from app.models import PollenReading, PollenSpecies

POLLEN_FIELDS: list[tuple[str, PollenSpecies]] = [
    ("alder_pollen", "alder"),
    ("birch_pollen", "birch"),
    ("grass_pollen", "grass"),
    ("mugwort_pollen", "mugwort"),
    ("olive_pollen", "olive"),
    ("ragweed_pollen", "ragweed"),
]

HOURLY_AQ_VARS = ["us_aqi"] + [f[0] for f in POLLEN_FIELDS]
CURRENT_AQ_VARS = HOURLY_AQ_VARS


def _max_pollen_from_values(values: dict[str, Any]) -> PollenReading | None:
    best: PollenReading | None = None
    for field, species in POLLEN_FIELDS:
        val = values.get(field)
        if val is None:
            continue
        grains = float(val)
        if best is None or grains > best.grains_per_m3:
            best = PollenReading(
                source="open_meteo",
                species=species,
                grains_per_m3=grains,
            )
    return best


def _max_pollen_row(row: dict[str, Any], index: int) -> PollenReading | None:
    values = {field: (row.get(field) or [None])[index] for field, _ in POLLEN_FIELDS}
    return _max_pollen_from_values(values)


class AirQualityHourly:
    """Hourly US AQI and pollen keyed by local ISO timestamp string."""

    def __init__(self, by_time: dict[str, tuple[float | None, PollenReading | None]]) -> None:
        self.by_time = by_time

    def for_time(self, dt: datetime) -> tuple[float | None, PollenReading | None]:
        key = dt.isoformat(timespec="minutes")
        if key in self.by_time:
            return self.by_time[key]
        for stored_key, value in self.by_time.items():
            if stored_key[:16] == key[:16]:
                return value
        return None, None


class AirQualityFetchResult:
    def __init__(
        self,
        hourly: AirQualityHourly,
        current_us_aqi: float | None,
        current_pollen: PollenReading | None,
        pollen_available: bool,
        success: bool,
        note: str | None = None,
    ) -> None:
        self.hourly = hourly
        self.current_us_aqi = current_us_aqi
        self.current_pollen = current_pollen
        self.pollen_available = pollen_available
        self.success = success
        self.note = note


def _empty_result(note: str) -> AirQualityFetchResult:
    return AirQualityFetchResult(
        hourly=AirQualityHourly({}),
        current_us_aqi=None,
        current_pollen=None,
        pollen_available=False,
        success=False,
        note=note,
    )


async def fetch_air_quality(
    latitude: float,
    longitude: float,
    forecast_days: int = 1,
    include_current: bool = True,
    client: httpx.AsyncClient | None = None,
) -> AirQualityFetchResult:
    """
    Call GET https://air-quality-api.open-meteo.com/v1/air-quality

    Same coordinates as the weather forecast. Pollen is often null outside Europe.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "forecast_days": forecast_days,
        "domains": "auto",
        "hourly": ",".join(HOURLY_AQ_VARS),
    }
    if include_current:
        params["current"] = ",".join(CURRENT_AQ_VARS)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

    try:
        try:
            response = await client.get(AIR_QUALITY_API_URL, params=params)
        except (httpx.TimeoutException, httpx.HTTPError):
            return _empty_result(
                "Air quality data could not be loaded. Outdoor scores use weather only."
            )
    finally:
        if own_client:
            await client.aclose()

    if response.status_code >= 500:
        return _empty_result(
            "Air quality data could not be loaded. Outdoor scores use weather only."
        )

    try:
        data = response.json()
    except ValueError:
        return _empty_result(
            "Air quality data could not be loaded. Outdoor scores use weather only."
        )

    if data.get("error"):
        return _empty_result(
            "Air quality data could not be loaded. Outdoor scores use weather only."
        )

    by_time: dict[str, tuple[float | None, PollenReading | None]] = {}
    pollen_seen = False
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    us_aqi_list = hourly.get("us_aqi") or []

    for i, time_str in enumerate(times):
        aqi_val = us_aqi_list[i] if i < len(us_aqi_list) else None
        aqi = float(aqi_val) if aqi_val is not None else None
        pollen = _max_pollen_row(hourly, i)
        if pollen is not None:
            pollen_seen = True
        by_time[time_str] = (aqi, pollen)

    current_us_aqi: float | None = None
    current_pollen: PollenReading | None = None
    current = data.get("current") if include_current else None
    if current:
        if current.get("us_aqi") is not None:
            current_us_aqi = float(current["us_aqi"])
        current_pollen = _max_pollen_from_values(current)
        if current_pollen:
            pollen_seen = True

    return AirQualityFetchResult(
        hourly=AirQualityHourly(by_time),
        current_us_aqi=current_us_aqi,
        current_pollen=current_pollen,
        pollen_available=pollen_seen,
        success=True,
        note=None,
    )
