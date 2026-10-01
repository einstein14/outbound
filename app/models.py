"""Pydantic models for locations, API data, scores, and reports."""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import TemperatureUnit

PollenSpecies = Literal[
    "alder",
    "birch",
    "grass",
    "mugwort",
    "olive",
    "ragweed",
]

PollenSource = Literal["open_meteo", "google"]


class LocationResult(BaseModel):
    """Resolved place from the Geocoding API."""

    name: str
    latitude: float
    longitude: float
    timezone: str
    display_name: str
    country: str = ""
    admin1: str = ""


class DaylightInfo(BaseModel):
    sunrise: datetime
    sunset: datetime
    daylight_duration_seconds: int


class PollenReading(BaseModel):
    source: PollenSource = "open_meteo"
    species: PollenSpecies
    grains_per_m3: Optional[float] = None
    upi: Optional[int] = None
    category: Optional[str] = None


class CurrentConditions(BaseModel):
    time: datetime
    temperature: float
    weather_code: int
    weather_label: str
    cloud_cover: float
    precipitation_probability: float
    wind_speed_mph: float
    is_day: bool
    us_aqi: Optional[float] = None
    us_aqi_band: Optional[str] = None
    pollen: Optional[PollenReading] = None
    outdoor_score: Optional[float] = None


class HourlyConditions(BaseModel):
    time: datetime
    temperature: float
    weather_code: int
    weather_label: str
    cloud_cover: float
    precipitation_probability: float
    wind_speed_mph: float
    is_day: bool
    us_aqi: Optional[float] = None
    pollen: Optional[PollenReading] = None


class ScoredHour(BaseModel):
    hour: HourlyConditions
    factor_scores: dict[str, float]
    outdoor_score: float
    active_weights: dict[str, float]


class DaySummary(BaseModel):
    """Aggregated forecast for one daylight day (from hourly timeline)."""

    avg_temperature: float
    min_temperature: float
    max_temperature: float
    dominant_weather_label: str
    avg_us_aqi: Optional[float] = None
    us_aqi_band: Optional[str] = None
    avg_outdoor_score: float
    peak_pollen: Optional[PollenReading] = None


class OutdoorWindow(BaseModel):
    start: datetime
    end: datetime
    avg_temperature: float
    avg_cloud_cover: float
    avg_precipitation_probability: float
    avg_wind_speed_mph: float
    avg_us_aqi: Optional[float] = None
    avg_pollen_grains: Optional[float] = None
    avg_pollen_upi: Optional[int] = None
    pollen_category: Optional[str] = None
    dominant_pollen_species: Optional[PollenSpecies] = None
    dominant_weather_label: str
    outdoor_score: float
    explanation: str
    is_limited_day: bool = False


class OutdoorReport(BaseModel):
    location: LocationResult
    temperature_unit: TemperatureUnit
    forecast_date: date
    is_today: bool = True
    daylight: DaylightInfo
    current: Optional[CurrentConditions] = None
    day_summary: Optional[DaySummary] = None
    hourly_timeline: list[ScoredHour] = Field(default_factory=list)
    windows: list[OutdoorWindow] = Field(default_factory=list)
    pollen_available: bool = False
    pollen_source: Optional[PollenSource] = None
    air_quality_available: bool = True
    air_quality_note: Optional[str] = None
    pollen_note: Optional[str] = None
