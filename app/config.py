"""Application configuration: API URLs, timeouts, score weights, thresholds."""

import base64
import binascii
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_env_path = _PROJECT_ROOT / ".env"
if _env_path.is_file():
    load_dotenv(dotenv_path=_env_path)

TemperatureUnit = Literal["celsius", "fahrenheit"]


def load_google_pollen_api_key() -> str | None:
    """Plain GOOGLE_POLLEN_API_KEY, or decode GOOGLE_POLLEN_API_KEY_B64 (encoding only, not encryption)."""
    b64 = os.getenv("GOOGLE_POLLEN_API_KEY_B64")
    if b64:
        try:
            return base64.b64decode(b64.strip(), validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            pass
    plain = os.getenv("GOOGLE_POLLEN_API_KEY")
    return plain if plain else None


# --- Open-Meteo API base URLs (no API key required for non-commercial use) ---
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))

# Optional Google Pollen API (fallback when Open-Meteo pollen is unavailable)
GOOGLE_POLLEN_API_URL = "https://pollen.googleapis.com/v1/forecast:lookup"
GOOGLE_POLLEN_API_KEY = load_google_pollen_api_key()
GOOGLE_POLLEN_MAX_DAYS = 5

# Inclusive of today; Open-Meteo air quality supports up to 7 forecast days.
MAX_FORECAST_DAYS = 7

# --- Outdoor Score weights (must sum to 1.0) ---
SCORE_WEIGHT_DAYLIGHT = 0.25
SCORE_WEIGHT_TEMPERATURE = 0.20
SCORE_WEIGHT_RAIN = 0.15
SCORE_WEIGHT_CLOUD_COVER = 0.10
SCORE_WEIGHT_WIND = 0.10
SCORE_WEIGHT_AIR_QUALITY = 0.12
SCORE_WEIGHT_POLLEN = 0.08

GOOD_HOUR_THRESHOLD = 7.0
MAX_WINDOWS = 3

# Weight groups for renormalization when factors are missing
WEIGHT_POLLEN_ONLY_DROP = 1.0 - SCORE_WEIGHT_POLLEN  # 0.92
WEIGHT_AQ_AND_POLLEN_DROP = 1.0 - SCORE_WEIGHT_AIR_QUALITY - SCORE_WEIGHT_POLLEN  # 0.80
