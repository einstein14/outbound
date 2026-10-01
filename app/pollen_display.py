"""Format pollen readings for UI."""

from app.models import PollenReading


def format_pollen_reading(reading: PollenReading) -> str:
    if reading.source == "google" and reading.upi is not None:
        category = reading.category or "—"
        return f"{reading.species} — UPI {reading.upi}/5 ({category})"
    if reading.grains_per_m3 is not None:
        return f"{reading.species} — {reading.grains_per_m3:.1f} grains/m³"
    return reading.species
