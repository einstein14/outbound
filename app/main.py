"""FastAPI entrypoint for Outbound."""

from datetime import date

from fastapi import FastAPI, HTTPException, Query

from app.config import TemperatureUnit
from app.exceptions import OutboundError
from app.models import OutdoorReport
from app.report import build_report

app = FastAPI(title="Outbound", description="Outdoor window recommendations API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/outdoor", response_model=OutdoorReport)
async def outdoor_report(
    location: str = Query(..., min_length=1, description="City, ZIP, or place name"),
    temperature_unit: TemperatureUnit = Query(
        "celsius",
        description="Temperature unit for forecast and display",
    ),
    forecast_date: date | None = Query(
        None,
        description="Local calendar date for the location (YYYY-MM-DD); defaults to today",
    ),
) -> OutdoorReport:
    try:
        return await build_report(location, temperature_unit, forecast_date)
    except OutboundError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
