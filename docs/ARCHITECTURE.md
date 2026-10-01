# Outbound architecture

Outbound is a stateless Python application: no database, no auth. A single orchestration function (`build_report`) fetches external APIs, scores daylight hours, and returns a typed `OutdoorReport` consumed by Streamlit and FastAPI.

## System context

```mermaid
flowchart TB
  subgraph clients [Clients]
    StreamlitUI[Streamlit_UI]
    FastAPI[FastAPI_JSON]
  end
  subgraph outbound [Outbound_app]
    BuildReport[build_report]
    Score[outdoor_score_and_windows]
    Models[Pydantic_models]
  end
  subgraph external [External_APIs]
    Geo[OpenMeteo_Geocoding]
    Wx[OpenMeteo_Forecast]
    AQ[OpenMeteo_Air_Quality]
    GPollen[Google_Pollen_optional]
  end
  StreamlitUI --> BuildReport
  FastAPI --> BuildReport
  BuildReport --> Geo
  BuildReport --> Wx
  BuildReport --> AQ
  BuildReport --> GPollen
  BuildReport --> Score
  Score --> Models
```

## Request flow

Both entry points call `build_report(location, temperature_unit, forecast_date)` in [`app/report.py`](../app/report.py).

```mermaid
sequenceDiagram
  participant User
  participant Client as Streamlit_or_FastAPI
  participant BR as build_report
  participant Geo as OpenMeteo_Geocoding
  participant Wx as OpenMeteo_Forecast
  participant AQ as OpenMeteo_Air_Quality
  participant GP as Google_Pollen

  User->>Client: location date unit
  Client->>BR: build_report
  BR->>Geo: geocode
  Geo-->>BR: lat lon timezone
  BR->>Wx: hourly weather sunrise sunset
  BR->>AQ: US AQI pollen hourly
  Wx-->>BR: HourlyConditions daylight
  AQ-->>BR: AQI pollen merge
  alt OpenMeteo has no pollen and API key set
    BR->>GP: forecast lookup
    GP-->>BR: daily UPI or error note
  end
  BR->>BR: filter_daylight_hours
  BR->>BR: compute_hour_score per hour
  BR->>BR: select_top_windows summarize_day
  BR-->>Client: OutdoorReport
  Client-->>User: UI or JSON
```

Shared HTTP client: one `httpx.AsyncClient` per report for geocoding, forecast, air quality, and optional Google pollen.

## Pollen resolution

Pollen affects scoring via [`app/outdoor_score.py`](../app/outdoor_score.py) (UPI 0–5 for Google, grains/m³ for Open-Meteo). Weights renormalize when pollen is missing.

```mermaid
flowchart TD
  Start[After air quality fetch] --> HasOM{OpenMeteo pollen available?}
  HasOM -->|yes| UseOM[pollen_source open_meteo]
  HasOM -->|no| HasKey{GOOGLE_POLLEN_API_KEY set?}
  HasKey -->|no| NoPollen[has_pollen false Europe-only note]
  HasKey -->|yes| InRange{target within 5 days?}
  InRange -->|no| RangeNote[pollen_note 5 day limit]
  InRange -->|yes| GoogleCall[GET forecast lookup]
  GoogleCall --> HttpOk{HTTP 2xx?}
  HttpOk -->|no| ErrNote[user note from API error]
  HttpOk -->|yes| Parsed{parse daily UPI?}
  Parsed -->|yes| UseGoogle[apply daily pollen to hours pollen_source google]
  Parsed -->|no| DateNote[pollen unavailable for date]
```

Google error handling lives in [`app/services/pollen_google.py`](../app/services/pollen_google.py) (`_note_from_google_http_error`).

## Module map

| Layer | Responsibility | Paths |
|-------|----------------|-------|
| Entry | HTTP UI and JSON API | [`app/ui/streamlit_app.py`](../app/ui/streamlit_app.py), [`app/main.py`](../app/main.py) |
| Orchestration | Fetch, merge, score, assemble report | [`app/report.py`](../app/report.py) |
| Domain | Scoring, windows, day summary, dates | [`app/outdoor_score.py`](../app/outdoor_score.py), [`app/day_summary.py`](../app/day_summary.py), [`app/forecast_date.py`](../app/forecast_date.py) |
| Integrations | External APIs | [`app/services/geocoding.py`](../app/services/geocoding.py), [`app/services/weather.py`](../app/services/weather.py), [`app/services/air_quality.py`](../app/services/air_quality.py), [`app/services/pollen_google.py`](../app/services/pollen_google.py), [`app/services/daylight.py`](../app/services/daylight.py) |
| Config | URLs, weights, env, dotenv | [`app/config.py`](../app/config.py) |
| Models | Pydantic schemas | [`app/models.py`](../app/models.py) |

## Configuration loading

On import, [`app/config.py`](../app/config.py) loads `.env` from the project root (if present). Streamlit Community Cloud uses **Secrets** instead; the same variable names apply. See [README](../README.md#configuration).

## Deployment topology

```mermaid
flowchart LR
  Dev[Local_dev] --> GitHub[GitHub_repo]
  GitHub --> StCloud[Streamlit_Community_Cloud]
  StCloud --> Users[Users]
```

FastAPI is intended for local use or a separate host; Streamlit Cloud runs only the Streamlit entry point.
