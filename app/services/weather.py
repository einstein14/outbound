"""Open-Meteo Forecast API: hourly weather and daily sunrise/sunset."""

from __future__ import annotations

from datetime import date, datetime

import httpx

from app.config import FORECAST_API_URL, HTTP_TIMEOUT_SECONDS, TemperatureUnit
from app.exceptions import DataParseError, ServiceUnavailableError
from app.forecast_date import daylight_for_date, filter_hours_for_date
from app.models import CurrentConditions, DaylightInfo, HourlyConditions
from app.weather_codes import weather_label

HOURLY_VARS = [
    "temperature_2m",
    "cloud_cover",
    "precipitation_probability",
    "wind_speed_10m",
    "weather_code",
    "is_day",
]

CURRENT_VARS = [
    "temperature_2m",
    "weather_code",
    "cloud_cover",
    "precipitation_probability",
    "wind_speed_10m",
    "is_day",
]

DAILY_VARS = ["sunrise", "sunset", "daylight_duration"]


def _parse_iso_local(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


async def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    temperature_unit: TemperatureUnit,
    forecast_days: int = 1,
    target_date: date | None = None,
    include_current: bool = True,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[HourlyConditions], DaylightInfo, CurrentConditions | None]:
    """
    Call GET https://api.open-meteo.com/v1/forecast

    Params:
      - latitude, longitude from geocoding
      - timezone=auto for local timestamps
      - forecast_days: number of days from today in the location timezone
      - target_date: slice hourly data and daily sunrise/sunset to this local date
      - include_current: request Open-Meteo `current` block (only for today)

    Hourly arrays are zipped by index with the parallel `time` array.
    """
    params: dict[str, str | int] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "forecast_days": forecast_days,
        "temperature_unit": temperature_unit,
        "wind_speed_unit": "mph",
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
    }
    if include_current:
        params["current"] = ",".join(CURRENT_VARS)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

    try:
        try:
            response = await client.get(FORECAST_API_URL, params=params)
        except httpx.TimeoutException:
            raise ServiceUnavailableError(
                "Open-Meteo took too long to respond. Please try again in a moment."
            ) from None
        except httpx.HTTPError:
            raise ServiceUnavailableError(
                "We couldn't reach the weather service. Please try again later."
            ) from None
    finally:
        if own_client:
            await client.aclose()

    if response.status_code >= 500:
        raise ServiceUnavailableError(
            "The weather service is temporarily unavailable. Please try again later."
        )

    try:
        data = response.json()
    except ValueError:
        raise DataParseError("We received an unexpected response from the weather service.") from None

    if data.get("error"):
        raise DataParseError(data.get("reason", "Weather data could not be loaded."))

    try:
        hourly = data["hourly"]
        daily = data["daily"]
        times = hourly["time"]
        hourly_rows: list[HourlyConditions] = []
        for i, time_str in enumerate(times):
            code = int(hourly["weather_code"][i])
            hourly_rows.append(
                HourlyConditions(
                    time=_parse_iso_local(time_str),
                    temperature=float(hourly["temperature_2m"][i]),
                    weather_code=code,
                    weather_label=weather_label(code),
                    cloud_cover=float(hourly["cloud_cover"][i]),
                    precipitation_probability=float(hourly["precipitation_probability"][i]),
                    wind_speed_mph=float(hourly["wind_speed_10m"][i]),
                    is_day=bool(hourly["is_day"][i]),
                )
            )

        slice_date = target_date or hourly_rows[0].time.date()
        hourly_rows = filter_hours_for_date(hourly_rows, slice_date)

        daylight = daylight_for_date(
            daily["time"],
            daily["sunrise"],
            daily["sunset"],
            daily["daylight_duration"],
            slice_date,
        )
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise DataParseError("Weather data was incomplete. Please try again.") from exc

    current: CurrentConditions | None = None
    if include_current:
        current_block = data.get("current")
        if current_block:
            try:
                code = int(current_block["weather_code"])
                current = CurrentConditions(
                    time=_parse_iso_local(current_block["time"]),
                    temperature=float(current_block["temperature_2m"]),
                    weather_code=code,
                    weather_label=weather_label(code),
                    cloud_cover=float(current_block["cloud_cover"]),
                    precipitation_probability=float(current_block["precipitation_probability"]),
                    wind_speed_mph=float(current_block["wind_speed_10m"]),
                    is_day=bool(current_block["is_day"]),
                )
            except (KeyError, TypeError, ValueError):
                current = None

    return hourly_rows, daylight, current


__all__ = ["fetch_weather_forecast"]
