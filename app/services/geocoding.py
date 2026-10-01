"""Open-Meteo Geocoding API: convert user text to latitude/longitude."""

from __future__ import annotations

import httpx

from app.config import GEOCODING_API_URL, HTTP_TIMEOUT_SECONDS
from app.exceptions import (
    DataParseError,
    InvalidLocationError,
    LocationNotFoundError,
    ServiceUnavailableError,
)
from app.models import LocationResult

MIN_QUERY_LENGTH = 2


def _format_display_name(name: str, admin1: str, country: str) -> str:
    parts = [name]
    if admin1:
        parts.append(admin1)
    if country:
        parts.append(country)
    return ", ".join(parts)


async def geocode_location(query: str, client: httpx.AsyncClient | None = None) -> LocationResult:
    """
    Call GET https://geocoding-api.open-meteo.com/v1/search

    Params:
      - name: city, ZIP, or "City, State" from the user
      - count: max results (we use the first match)
      - language: en for consistent labels

    Response fields used:
      - results[0].latitude, longitude, timezone, name, admin1, country
    """
    trimmed = query.strip()
    if len(trimmed) < MIN_QUERY_LENGTH:
        raise InvalidLocationError(
            "We couldn't find that location. Try entering a city and state."
        )

    params = {"name": trimmed, "count": 5, "language": "en"}
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

    try:
        try:
            response = await client.get(GEOCODING_API_URL, params=params)
        except httpx.TimeoutException:
            raise ServiceUnavailableError(
                "Open-Meteo took too long to respond. Please try again in a moment."
            ) from None
        except httpx.HTTPError:
            raise ServiceUnavailableError(
                "We couldn't reach the location service. Please try again later."
            ) from None
    finally:
        if own_client:
            await client.aclose()

    if response.status_code >= 500:
        raise ServiceUnavailableError(
            "The location service is temporarily unavailable. Please try again later."
        )

    try:
        data = response.json()
    except ValueError:
        raise DataParseError("We received an unexpected response from the location service.") from None

    if data.get("error"):
        reason = data.get("reason", "Invalid location search.")
        raise InvalidLocationError(reason)

    results = data.get("results") or []
    if not results:
        raise LocationNotFoundError(
            "We couldn't find that location. Try entering a city and state."
        )

    first = results[0]
    try:
        name = first["name"]
        latitude = float(first["latitude"])
        longitude = float(first["longitude"])
        timezone = first["timezone"]
        admin1 = first.get("admin1") or ""
        country = first.get("country") or ""
    except (KeyError, TypeError, ValueError):
        raise DataParseError("Location data was incomplete. Please try another search.") from None

    return LocationResult(
        name=name,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        display_name=_format_display_name(name, admin1, country),
        country=country,
        admin1=admin1,
    )
