import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.exceptions import LocationNotFoundError
from app.services.air_quality import fetch_air_quality
from app.services.geocoding import geocode_location
from app.services.weather import fetch_weather_forecast

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.asyncio
async def test_geocode_parses_first_result():
    data = _load("geocode_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        loc = await geocode_location("Omaha, NE", client=client)
    assert loc.name == "Omaha"
    assert loc.latitude == 41.25


@pytest.mark.asyncio
async def test_geocode_empty_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(LocationNotFoundError):
            await geocode_location("ZZZZ", client=client)


@pytest.mark.asyncio
async def test_forecast_parses_hourly():
    data = _load("forecast_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        hourly, daylight, current = await fetch_weather_forecast(
            41.25, -96.0, "celsius", client=client
        )
    assert len(hourly) == 4
    assert daylight.daylight_duration_seconds == 42300
    assert current is not None


@pytest.mark.asyncio
async def test_forecast_slices_to_target_date():
    data = _load("forecast_multiday_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        hourly, daylight, current = await fetch_weather_forecast(
            41.25,
            -96.0,
            "celsius",
            forecast_days=3,
            target_date=date(2026, 10, 2),
            include_current=False,
            client=client,
        )
    assert len(hourly) == 2
    assert hourly[0].time.date() == date(2026, 10, 2)
    assert daylight.sunrise == __import__("datetime").datetime(2026, 10, 2, 7, 14)
    assert current is None


@pytest.mark.asyncio
async def test_air_quality_join_and_null_pollen():
    data = _load("air_quality_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_air_quality(41.25, -96.0, client=client)
    assert result.success
    assert result.pollen_available is False
    aqi, pollen = result.hourly.for_time(
        __import__("datetime").datetime(2026, 10, 1, 9, 0)
    )
    assert aqi == 50.0
    assert pollen is None
