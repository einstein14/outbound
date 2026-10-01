"""Google Pollen API: daily UPI fallback when Open-Meteo pollen is unavailable."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.config import (
    GOOGLE_POLLEN_API_KEY,
    GOOGLE_POLLEN_API_URL,
    GOOGLE_POLLEN_MAX_DAYS,
    HTTP_TIMEOUT_SECONDS,
)
from app.models import PollenReading, PollenSpecies

# Google plant / type codes mapped to our species labels for scoring display
GOOGLE_CODE_TO_SPECIES: dict[str, PollenSpecies] = {
    "GRAMINALES": "grass",
    "GRASS": "grass",
    "RAGWEED": "ragweed",
    "BIRCH": "birch",
    "ALDER": "alder",
    "MUGWORT": "mugwort",
    "OLIVE": "olive",
    "TREE": "birch",
    "WEED": "ragweed",
}


class GooglePollenResult:
    def __init__(
        self,
        reading: PollenReading | None,
        note: str | None = None,
    ) -> None:
        self.reading = reading
        self.note = note


def _species_for_code(code: str) -> PollenSpecies:
    return GOOGLE_CODE_TO_SPECIES.get(code.upper(), "grass")


def _date_matches(day_info: dict[str, Any], target: date) -> bool:
    day = day_info.get("date") or {}
    try:
        return (
            int(day["year"]) == target.year
            and int(day["month"]) == target.month
            and int(day["day"]) == target.day
        )
    except (KeyError, TypeError, ValueError):
        return False


def _entries_with_index(day_info: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for block in day_info.get("plantInfo") or []:
        code = block.get("code") or "UNKNOWN"
        if block.get("indexInfo"):
            entries.append((code, block["indexInfo"]))
    for block in day_info.get("pollenTypeInfo") or []:
        code = block.get("code") or "UNKNOWN"
        if block.get("indexInfo"):
            entries.append((code, block["indexInfo"]))
    return entries


def parse_google_pollen_for_date(
    data: dict[str, Any],
    target: date,
) -> PollenReading | None:
    """Extract peak UPI pollen reading for a calendar day from forecast:lookup JSON."""
    best_code: str | None = None
    best_index: dict[str, Any] | None = None
    best_value = -1

    for day_info in data.get("dailyInfo") or []:
        if not _date_matches(day_info, target):
            continue
        for code, index_info in _entries_with_index(day_info):
            value = index_info.get("value")
            if value is None:
                continue
            upi = int(value)
            if upi > best_value:
                best_value = upi
                best_code = code
                best_index = index_info

    if best_code is None or best_index is None:
        return None

    return PollenReading(
        source="google",
        species=_species_for_code(best_code),
        upi=int(best_index["value"]),
        category=best_index.get("category"),
    )


def google_pollen_in_range(target: date, today_local: date) -> bool:
    delta = (target - today_local).days
    return 0 <= delta < GOOGLE_POLLEN_MAX_DAYS


def _note_from_google_http_error(response: httpx.Response) -> str:
    """User-facing note from a failed forecast:lookup response (no secrets)."""
    try:
        payload = response.json()
    except ValueError:
        return (
            "Pollen data could not be loaded from Google. "
            "Outdoor scores use other factors only."
        )
    err = payload.get("error") or {}
    message = (err.get("message") or "").strip()
    details = err.get("details") or []
    reason = ""
    for item in details:
        if isinstance(item, dict) and item.get("reason"):
            reason = str(item["reason"])
            break

    if reason == "API_KEY_INVALID" or "API key not valid" in message:
        return (
            "Google rejected GOOGLE_POLLEN_API_KEY (invalid or revoked). "
            "In Google Cloud: enable the Pollen API, create a new key, and update .env — "
            "then restart Streamlit."
        )
    if reason == "SERVICE_DISABLED" or "has not been used" in message or "is disabled" in message:
        return (
            "Pollen API is not enabled for this Google Cloud project. "
            "Enable pollen.googleapis.com, attach billing if required, and try again."
        )
    if "referer" in message.lower() or reason == "API_KEY_HTTP_REFERRER_BLOCKED":
        return (
            "Google API key is restricted to browser referrers; server calls need "
            "no referrer restriction or an IP allowlist. Update key restrictions in GCP."
        )
    if message:
        return f"Pollen data could not be loaded from Google: {message}"
    return (
        "Pollen data could not be loaded from Google. "
        "Outdoor scores use other factors only."
    )


async def fetch_google_pollen_for_date(
    latitude: float,
    longitude: float,
    target: date,
    today_local: date,
    client: httpx.AsyncClient | None = None,
) -> GooglePollenResult:
    """
    Call GET https://pollen.googleapis.com/v1/forecast:lookup

    Requires GOOGLE_POLLEN_API_KEY. Returns daily Universal Pollen Index (UPI) for target.
    """
    if not GOOGLE_POLLEN_API_KEY:
        return GooglePollenResult(None, None)

    if not google_pollen_in_range(target, today_local):
        return GooglePollenResult(
            None,
            "Pollen data from Google is available up to 5 days ahead.",
        )

    days = min(GOOGLE_POLLEN_MAX_DAYS, (target - today_local).days + 1)
    params = {
        "key": GOOGLE_POLLEN_API_KEY,
        "location.latitude": latitude,
        "location.longitude": longitude,
        "days": days,
        "plantsDescription": 0,
    }

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

    try:
        try:
            response = await client.get(GOOGLE_POLLEN_API_URL, params=params)
        except (httpx.TimeoutException, httpx.HTTPError):
            return GooglePollenResult(
                None,
                "Pollen data could not be loaded from Google. Outdoor scores use other factors only.",
            )
    finally:
        if own_client:
            await client.aclose()

    if response.status_code >= 400:
        return GooglePollenResult(None, _note_from_google_http_error(response))

    try:
        data = response.json()
    except ValueError:
        return GooglePollenResult(
            None,
            "Pollen data could not be loaded from Google. Outdoor scores use other factors only.",
        )

    reading = parse_google_pollen_for_date(data, target)
    if reading is None:
        return GooglePollenResult(
            None,
            "Pollen data unavailable for this date.",
        )
    return GooglePollenResult(reading, None)
