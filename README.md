# Outbound

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/OWNER/outbound/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/outbound/actions/workflows/ci.yml)

Outbound is a small Python API mashup that combines location, weather, daylight, air quality, and pollen data to suggest comfortable **outdoor windows** during natural daylight.

Outdoor scores are a transparent application heuristic. They are **not** medical recommendations.

## What it does

1. You enter a city or ZIP code and optionally pick a date (today through 6 days ahead).
2. Open-Meteo Geocoding resolves latitude and longitude.
3. Open-Meteo Forecast returns hourly weather and sunrise/sunset for the selected **local calendar day** at that location.
4. Open-Meteo Air Quality returns US AQI and pollen (pollen mainly in Europe).
5. Outbound computes an **Outdoor Score** for each daylight hour and groups the best stretches into up to three recommended windows.
6. Streamlit shows overview, “right now,” windows, and an hourly chart.

## Quick start

Run all commands from the **project root** (the folder that contains `app/` and `requirements.txt`).

```bash
cd outbound
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # optional: Google Pollen key for US locations
streamlit run app/ui/streamlit_app.py
```

**FastAPI (optional JSON API):**

```bash
uvicorn app.main:app --reload
curl "http://127.0.0.1:8000/outdoor?location=Omaha,%20NE&temperature_unit=celsius"
curl "http://127.0.0.1:8000/outdoor?location=Omaha,%20NE&forecast_date=2026-10-05"
```

**Tests:**

```bash
pytest
```

## APIs

| API | Endpoint | Docs |
|-----|----------|------|
| Geocoding | `https://geocoding-api.open-meteo.com/v1/search` | [Geocoding API](https://open-meteo.com/en/docs/geocoding-api) |
| Forecast | `https://api.open-meteo.com/v1/forecast` | [Forecast API](https://open-meteo.com/en/docs) |
| Air quality | `https://air-quality-api.open-meteo.com/v1/air-quality` | [Air Quality API](https://open-meteo.com/en/docs/air-quality-api) |
| Pollen (optional) | `https://pollen.googleapis.com/v1/forecast:lookup` | [Google Pollen API](https://developers.google.com/maps/documentation/pollen/forecast) |

Open-Meteo requires no API key for non-commercial use. Google Pollen is optional (see below).

## Architecture

`build_report` in `app/report.py` geocodes the location, fetches weather and air quality, optionally falls back to Google Pollen, scores daylight hours, and returns an `OutdoorReport` for Streamlit or FastAPI.

Diagrams, sequence flow, and module map: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Project structure

```
outbound/
├── app/
│   ├── main.py              # FastAPI
│   ├── report.py            # build_report orchestration
│   ├── config.py            # env, weights, API URLs
│   ├── models.py
│   ├── outdoor_score.py
│   ├── day_summary.py
│   ├── ui/streamlit_app.py
│   └── services/            # geocoding, weather, air quality, pollen
├── docs/
│   └── ARCHITECTURE.md
├── tests/
├── .env.example
├── requirements.txt         # runtime (Streamlit Cloud)
└── requirements-dev.txt     # + pytest
```

## Configuration

Copy [`.env.example`](.env.example) to `.env` for local development. Variables are loaded automatically from the project root via `python-dotenv`.

| Variable | Required | Description |
|----------|----------|-------------|
| `HTTP_TIMEOUT_SECONDS` | No | HTTP client timeout (default `10`) |
| `GOOGLE_POLLEN_API_KEY_B64` | No | Base64-encoded Google Pollen API key (preferred) |
| `GOOGLE_POLLEN_API_KEY` | No | Plain key if `GOOGLE_POLLEN_API_KEY_B64` is unset |

Never commit `.env`. On Streamlit Cloud, use **Secrets** (see Deploy).

## Pollen data sources

1. **Open-Meteo** (default) — hourly grains/m³ in Europe when CAMS provides data.
2. **Google Pollen API** (optional) — used when Open-Meteo has no pollen (typical US locations). Returns a **daily** Universal Pollen Index (UPI 0–5) applied to all hours that day.

Enable the Pollen API in [Google Cloud](https://developers.google.com/maps/documentation/pollen/get-api-key), attach billing (free tier includes roughly 5,000 calls/month on the Pollen Pro SKU), then configure a key (see [`.env.example`](.env.example)).

**Recommended (Base64 in `.env` or Streamlit Secrets):** encoding is not encryption, but keeps the key out of plain text in the file.

```bash
python3 -c "import base64; print(base64.b64encode(b'YOUR_KEY_HERE').decode())"
```

```env
GOOGLE_POLLEN_API_KEY_B64=paste_output_here
```

**Alternative:** `GOOGLE_POLLEN_API_KEY=your_key_here` (plain text fallback).

Restrict the API key in GCP (Pollen API only). Google forecasts cover up to **5 days** ahead; dates beyond that use weather and air quality only.

### Pollen troubleshooting

- **“Google rejected GOOGLE_POLLEN_API_KEY”** — Create a new key in GCP, enable **Pollen API** (`pollen.googleapis.com`), and update `.env` or Streamlit Secrets; fully restart Streamlit.
- **API not enabled / billing** — Enable the Pollen API on your project and attach billing if Google requires it.
- **Referrer restrictions** — Server-side calls need **no HTTP referrer restriction** or an **IP allowlist**, not browser-only referrers.
- **Still no pollen after fixing the key** — Rotate the key if it was ever committed or pasted in chat; confirm the selected date is within 5 days for Google.
- **Europe** — Open-Meteo pollen may work without Google; US locations usually need a valid Google key.

## Outdoor Score

Weights (in `app/config.py`):

| Factor | Weight |
|--------|--------|
| Daylight | 25% |
| Temperature comfort | 20% |
| Rain probability | 15% |
| Cloud cover | 10% |
| Wind | 10% |
| Air quality (US AQI) | 12% |
| Pollen | 8% |

If pollen or air quality is unavailable for a location or hour, those factors are omitted and the remaining weights are renormalized.

Temperature comfort is scored in Celsius internally so the Outdoor Score does not change when you toggle °C/°F in the UI.

## Forecast dates

- The UI and API support up to **7 days** inclusive (today + 6 days ahead), aligned with Open-Meteo air quality limits.
- After geocoding, “today” and valid date ranges use the location’s **timezone** from Open-Meteo (`timezone=auto`).
- **Right now** and live `current` conditions appear only when the selected date is today at that location.
- Future days use forecast hourly data only.

## Publish to GitHub

Verify secrets are not tracked:

```bash
git check-ignore -v .env    # should match .gitignore
git status --porcelain      # must NOT list .env
```

Initialize and push (replace repo name and `OWNER` as needed):

```bash
git init -b main
git add -A
git commit -m "Initial commit: Outbound outdoor window app"
```

**With GitHub CLI** (after `gh auth login`):

```bash
gh repo create outbound --public --source=. --remote=origin --push
```

**Manual:** Create an empty repository on GitHub, then:

```bash
git remote add origin https://github.com/OWNER/outbound.git
git push -u origin main
```

Update the CI badge URL at the top of this README (`OWNER/outbound`) to match your repository.

## Deploy: Streamlit Community Cloud

1. Push the repo to GitHub (see above).
2. Open [share.streamlit.io](https://share.streamlit.io) → **Create app** → select your repo and branch.
3. **Main file path:** `app/ui/streamlit_app.py`
4. **Advanced settings → Python version:** 3.12 (matches [`.python-version`](.python-version)).
5. **Secrets** (Settings → Secrets), TOML format — same variables as `.env`:

```toml
GOOGLE_POLLEN_API_KEY_B64 = "paste_base64_here"
# or
# GOOGLE_POLLEN_API_KEY = "your_key_here"
```

6. Deploy. Smoke test with a US city (e.g. Omaha, NE): pollen should show Google UPI or a clear error note if the key is misconfigured.

FastAPI is **not** deployed on Streamlit Cloud; run it locally with `uvicorn` or host it separately if you need the JSON API in production.

## Limitations

- Scores rank pleasant outdoor daylight conditions; they do not estimate vitamin D, UV exposure goals, or health outcomes.
- Open-Meteo pollen is limited to Europe; US pollen requires a Google API key (daily index, not grains/m³).
- Air quality and weather are model-based forecasts, not live station readings everywhere.

## Roadmap

Nearby parks or trails via OpenStreetMap / Overpass, using the same coordinates to suggest places during a recommended window.

## License

[MIT](LICENSE)
