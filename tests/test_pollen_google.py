import json
from datetime import date
from pathlib import Path

import httpx

from app.services.pollen_google import (
    _note_from_google_http_error,
    google_pollen_in_range,
    parse_google_pollen_for_date,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_google_pollen_peak_upi():
    data = json.loads((FIXTURES / "google_pollen_response.json").read_text())
    reading = parse_google_pollen_for_date(data, date(2026, 10, 3))
    assert reading is not None
    assert reading.source == "google"
    assert reading.species == "ragweed"
    assert reading.upi == 3
    assert reading.category == "Moderate"


def test_note_from_google_invalid_api_key():
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": "API key not valid. Please pass a valid API key.",
                "details": [{"reason": "API_KEY_INVALID"}],
            }
        },
    )
    note = _note_from_google_http_error(response)
    assert "rejected GOOGLE_POLLEN_API_KEY" in note
    assert "Pollen API" in note


def test_google_pollen_in_range():
    today = date(2026, 10, 1)
    assert google_pollen_in_range(date(2026, 10, 1), today)
    assert google_pollen_in_range(date(2026, 10, 5), today)
    assert not google_pollen_in_range(date(2026, 10, 6), today)
