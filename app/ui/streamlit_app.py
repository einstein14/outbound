"""Streamlit UI for Outbound."""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Streamlit runs this file as a script; ensure the repo root is on sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import importlib

import streamlit as st

from app.config import TemperatureUnit
from app.exceptions import OutboundError
from app.outdoor_score import format_time_range
from app.pollen_display import format_pollen_reading
import app.report as report_module
from app.services.daylight import format_daylight_duration

# Streamlit keeps imported modules in sys.modules across reruns; reload so
# backend signature changes (e.g. forecast_date) are picked up without a full server restart.
importlib.reload(report_module)
build_report = report_module.build_report


def _temp_suffix(unit: TemperatureUnit) -> str:
    return "°F" if unit == "fahrenheit" else "°C"


def _run_report(location: str, unit: TemperatureUnit, forecast_date: date):
    return asyncio.run(
        build_report(
            location,
            temperature_unit=unit,
            forecast_date=forecast_date,
        )
    )


def _format_report_date(d: date) -> str:
    return d.strftime("%A, %B %d, %Y").replace(" 0", " ")


st.set_page_config(page_title="Outbound", page_icon="☀️", layout="wide")

st.title("☀️ Outbound")
st.markdown(
    "Find a good time to get natural light and spend time outdoors."
)

if "temperature_unit" not in st.session_state:
    st.session_state.temperature_unit = "celsius"
if "last_forecast_date" not in st.session_state:
    st.session_state.last_forecast_date = date.today()

with st.sidebar:
    st.header("Search")
    unit_label = st.radio(
        "Temperature",
        options=["celsius", "fahrenheit"],
        format_func=lambda u: "Celsius" if u == "celsius" else "Fahrenheit",
        horizontal=True,
        key="temperature_unit",
    )
    with st.form("search_form", clear_on_submit=False):
        location = st.text_input("Enter your city or ZIP code", placeholder="Omaha, NE")
        forecast_date = st.date_input(
            "Date",
            value=st.session_state.last_forecast_date,
            min_value=date.today(),
            max_value=date.today() + timedelta(days=6),
            help="After search, dates follow the location's local timezone from Open-Meteo.",
        )
        submitted = st.form_submit_button("Check outdoor windows", type="primary")

if submitted:
    if not location.strip():
        st.error("Please enter a city or ZIP code.")
    else:
        with st.spinner("Fetching weather, daylight, and air quality..."):
            try:
                report = _run_report(location.strip(), unit_label, forecast_date)
                st.session_state["report"] = report
                st.session_state["last_location"] = location.strip()
                st.session_state["last_forecast_date"] = forecast_date
            except OutboundError as exc:
                st.error(exc.message)
                st.session_state.pop("report", None)

report = st.session_state.get("report")
last_location = st.session_state.get("last_location", "")
last_date = st.session_state.get("last_forecast_date", date.today())

if (
    report
    and last_location
    and report.temperature_unit != unit_label
    and not submitted
):
    with st.spinner("Updating temperature unit..."):
        try:
            report = _run_report(last_location, unit_label, last_date)
            st.session_state["report"] = report
        except OutboundError as exc:
            st.error(exc.message)

if not report:
    st.info(
        "Enter a location and optional date in the sidebar, then click "
        "**Check outdoor windows**. You can plan up to 6 days ahead."
    )
else:
    suffix = _temp_suffix(report.temperature_unit)
    st.subheader(f"Overview for {_format_report_date(report.forecast_date)}")
    st.markdown(f"**Location:** {report.location.display_name}")

    if not report.is_today:
        st.caption("Forecast for a future day — conditions may change.")

    cols = st.columns(3)
    summary = report.day_summary
    if report.current:
        cols[0].metric("Current temp", f"{report.current.temperature:.0f}{suffix}")
        cols[1].metric("Conditions", report.current.weather_label)
        if report.current.us_aqi is not None:
            cols[2].metric(
                "US AQI",
                f"{report.current.us_aqi:.0f}",
                help=report.current.us_aqi_band or "",
            )
        else:
            cols[2].metric("US AQI", "—")
    elif summary:
        cols[0].metric("Daytime avg", f"{summary.avg_temperature:.0f}{suffix}")
        cols[1].metric("Typical", summary.dominant_weather_label)
        if summary.avg_us_aqi is not None:
            cols[2].metric(
                "Avg US AQI",
                f"{summary.avg_us_aqi:.0f}",
                help=summary.us_aqi_band or "",
            )
        else:
            cols[2].metric("Avg US AQI", "—")
        st.caption(
            f"Daytime range: {summary.min_temperature:.0f}{suffix}–"
            f"{summary.max_temperature:.0f}{suffix} · "
            f"Avg outdoor score: {summary.avg_outdoor_score:.1f}/10"
        )
    else:
        cols[0].metric("Daytime avg", "—")
        cols[1].metric("Typical", "—")
        cols[2].metric("Avg US AQI", "—")

    st.markdown(
        f"**Sunrise:** {report.daylight.sunrise.strftime('%I:%M %p').lstrip('0')} · "
        f"**Sunset:** {report.daylight.sunset.strftime('%I:%M %p').lstrip('0')} · "
        f"**Daylight:** {format_daylight_duration(report.daylight.daylight_duration_seconds)}"
    )

    if report.current and report.current.us_aqi_band:
        st.caption(f"Air quality: {report.current.us_aqi_band}")
    elif summary and summary.us_aqi_band:
        st.caption(f"Air quality: {summary.us_aqi_band} (daytime average)")

    if report.pollen_available and report.current and report.current.pollen:
        st.caption(f"Pollen: {format_pollen_reading(report.current.pollen)}")
    elif report.pollen_available and summary and summary.peak_pollen:
        st.caption(f"Pollen (peak): {format_pollen_reading(summary.peak_pollen)}")
    elif not report.pollen_available:
        if report.pollen_note:
            st.caption(f"Pollen: {report.pollen_note}")
        else:
            st.caption("Pollen: not available for this location")

    if report.air_quality_note:
        st.info(report.air_quality_note)
    elif report.pollen_note and report.pollen_available:
        st.caption(report.pollen_note)

    if (
        report.is_today
        and report.current
        and report.current.is_day
        and report.current.outdoor_score is not None
    ):
        st.subheader("Right now")
        st.markdown(
            f"🌤️ **Comfortable outdoor conditions** — "
            f"{report.current.temperature:.0f}{suffix} · {report.current.weather_label}"
        )
        st.markdown(f"**Outdoor Score: {report.current.outdoor_score:.1f}/10**")
        if report.current.us_aqi is not None:
            st.caption(f"US AQI: {report.current.us_aqi:.0f} ({report.current.us_aqi_band})")

    st.subheader("Best outdoor windows")
    if not report.windows:
        st.write("No daylight outdoor windows found for this day.")
    for i, window in enumerate(report.windows, start=1):
        with st.container(border=True):
            title = format_time_range(window.start, window.end)
            st.markdown(f"### ☀️ {title}")
            st.caption(f"#{i} recommended")
            if window.is_limited_day:
                st.caption(
                    "Conditions are limited this day; this is among the better stretches."
                )
            st.markdown(
                f"**{window.avg_temperature:.0f}{suffix} · {window.dominant_weather_label}**"
            )
            st.markdown(
                f"Rain: {window.avg_precipitation_probability:.0f}% · "
                f"Cloud cover: {window.avg_cloud_cover:.0f}% · "
                f"Wind: {window.avg_wind_speed_mph:.0f} mph"
            )
            if window.avg_us_aqi is not None:
                st.markdown(f"US AQI: {window.avg_us_aqi:.0f}")
            if window.avg_pollen_upi is not None and window.dominant_pollen_species:
                category = window.pollen_category or "—"
                st.markdown(
                    f"Pollen ({window.dominant_pollen_species}): "
                    f"UPI {window.avg_pollen_upi}/5 ({category})"
                )
            elif window.avg_pollen_grains is not None and window.dominant_pollen_species:
                st.markdown(
                    f"Pollen ({window.dominant_pollen_species}): "
                    f"{window.avg_pollen_grains:.1f} grains/m³"
                )
            st.markdown(f"**Outdoor Score: {window.outdoor_score:.1f}/10**")
            st.progress(min(window.outdoor_score / 10.0, 1.0))
            st.markdown(f"> {window.explanation}")

    st.subheader("Hourly timeline")
    if report.hourly_timeline:
        chart_data = {
            "Hour": [sh.hour.time.strftime("%H:%M") for sh in report.hourly_timeline],
            "Outdoor Score": [sh.outdoor_score for sh in report.hourly_timeline],
            "Good threshold": [7.0] * len(report.hourly_timeline),
        }
        st.line_chart(chart_data, x="Hour", height=320)
        st.caption("Scores at or above 7.0 are treated as good hours.")
    else:
        st.write("No scored daylight hours for this day.")

    disclaimer = (
        "Outdoor scores are based on daylight, weather, air quality, and pollen "
        "conditions and are not medical recommendations."
    )
    if report.pollen_source == "google":
        disclaimer += " Pollen may be supplied by Google Pollen API (daily index)."
    st.caption(disclaimer)
