# CanTides — Home Assistant Integration Design

**Date:** 2026-04-07  
**Status:** Approved  
**API:** Canadian Hydrographic Service (CHS) — [api-sine.dfo-mpo.gc.ca](https://api-sine.dfo-mpo.gc.ca)

---

## Overview

CanTides is a Home Assistant custom integration that exposes Canadian tide station data via the CHS Integrated Water Level System API. It is distributed via HACS, with a path to inclusion in the official HA integration list as it matures.

It provides:
- Live observed water level height and derived tide phase (rising/falling/high/low)
- Tide predictions for a user-configured number of days (1–30), surfaced as next-high, next-low, and full forecast sensors

---

## Project Structure

```
cantides/
├── CLAUDE.md
├── README.md
├── Makefile                         # dev, test, lint, format targets
├── .vscode/
│   ├── settings.json
│   ├── extensions.json
│   └── launch.json
├── custom_components/
│   └── cantides/
│       ├── __init__.py              # Integration setup/unload
│       ├── manifest.json            # HACS metadata
│       ├── config_flow.py           # UI config flow + options flow
│       ├── const.py                 # Constants and defaults
│       ├── coordinator.py           # ObservedDataCoordinator + PredictionCoordinator
│       ├── api.py                   # CHS API client + tide math helpers
│       ├── sensor.py                # All sensor entities
│       ├── strings.json             # UI strings (en)
│       └── translations/
│           └── en.json
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_coordinator.py
│   ├── test_config_flow.py
│   └── test_sensor.py
└── scripts/
    └── dev_instance.sh              # Used by `make dev`
```

### Tooling

| Tool | Purpose |
|---|---|
| `ruff` | Lint + format (HA-standard, replaces flake8/black/isort) |
| `pytest` | Test runner |
| `pytest-homeassistant-custom-component` | HA test fixtures |
| `aiohttp` | HTTP client (already in HA environment, no extra dependency) |

### Makefile Targets

| Target | Action |
|---|---|
| `make dev` | Start a local HA dev instance with the integration loaded (config in `.devconfig/`) |
| `make test` | Run the full test suite |
| `make lint` | Run `ruff check` |
| `make format` | Run `ruff format` |

---

## CHS API Client (`api.py`)

**Base URL:** `https://api-sine.dfo-mpo.gc.ca`  
**HTTP client:** `aiohttp.ClientSession` (injected, not owned by the client)

### Data Models (dataclasses)

```python
@dataclass
class Station:
    id: str
    code: str
    name: str
    latitude: float
    longitude: float

@dataclass
class ObservedData:
    station_id: str
    timestamp: datetime
    height_m: float
    time_series_code: str  # "wlo"

@dataclass
class PredictionPoint:
    timestamp: datetime
    height_m: float
    type: Literal["HIGH", "LOW", "UNKNOWN"]
```

### API Methods

```python
class CHSApiClient:
    async def get_stations(self, code: str | None = None) -> list[Station]
    async def get_station(self, station_id: str) -> Station
    async def get_observed_water_level(self, station_id: str) -> list[ObservedData]
        # Fetches last 30 minutes of wlo data
    async def get_predictions(self, station_id: str, days: int) -> list[PredictionPoint]
        # Fetches from today 00:00 UTC to today + days 23:59 UTC using wlp time-series
```

### Pure Helper Functions

- `find_nearest_station(stations: list[Station], lat: float, lon: float) -> Station`  
  Uses Haversine distance. No external library.

- `derive_tide_phase(recent_points: list[ObservedData]) -> TidePhase`  
  Compares the last two observed heights. Returns `RISING | FALLING | HIGH | LOW`.

- `find_highs_lows(points: list[PredictionPoint]) -> list[PredictionPoint]`  
  Identifies local minima/maxima in the prediction time series, tagging each as `HIGH` or `LOW`.

### Error Handling

- All non-2xx responses and network failures raise `CHSApiError(message, status_code)`
- The client does not retry — coordinators delegate that to HA's built-in backoff

---

## Data Coordinators (`coordinator.py`)

### `ObservedDataCoordinator(DataUpdateCoordinator)`

- **Polls:** `GET /api/v1/stations/{stationId}/data` with `time-series-code=wlo`
- **Interval:** User-configured (default: 5 minutes)
- **Fetches:** Last 30 minutes of data to have enough points for phase derivation
- **Stores:**
  - `latest: ObservedData` — most recent point
  - `phase: TidePhase` — derived from last two points
- **On failure:** Sensors go `unavailable`; HA coordinator handles retry/backoff

### `PredictionCoordinator(DataUpdateCoordinator)`

- **Polls:** `GET /api/v1/stations/{stationId}/data` with `time-series-code=wlp`
- **Interval:** User-configured (default: 24 hours)
- **Fetches:** Today 00:00 UTC → today + N days 23:59 UTC
- **Post-processes:** Raw time series → list of `PredictionPoint` (HIGH/LOW tagged)
- **Stores:**
  - `forecast: list[PredictionPoint]` — full N-day list of highs and lows
  - `next_high: PredictionPoint | None` — first HIGH after now
  - `next_low: PredictionPoint | None` — first LOW after now
- **On failure:** Retains last known data (stale forecast is preferable to unavailable)

### Coordinator Lifecycle

- Both coordinators created in `async_setup_entry`, stored in `hass.data[DOMAIN][entry.entry_id]`
- Both perform an initial refresh before sensors are registered
- Both shut down cleanly in `async_unload_entry`

---

## Sensors (`sensor.py`)

All sensors are grouped under a single HA **Device** per configured station:

| Field | Value |
|---|---|
| Manufacturer | `DFO-MPO / CHS` |
| Model | `Tide Station` |
| Identifier | Station code (e.g., `03580`) |
| Name | Station name from API (e.g., `Quebec City`) |

### Observed Sensors (subscribe to `ObservedDataCoordinator`)

| Entity ID | State | Unit | Attributes |
|---|---|---|---|
| `sensor.{station}_water_level` | e.g. `1.42` | `m` | `timestamp`, `station_id`, `qc_flag` |
| `sensor.{station}_tide_phase` | e.g. `Rising` | — | `timestamp`, `previous_height_m` |

`TidePhase` values: `Rising`, `Falling`, `High`, `Low`

### Prediction Sensors (subscribe to `PredictionCoordinator`)

| Entity ID | State | Unit | Attributes |
|---|---|---|---|
| `sensor.{station}_next_high_tide` | e.g. `14:32` | — | `height_m`, `datetime_iso` |
| `sensor.{station}_next_low_tide` | e.g. `19:05` | — | `height_m`, `datetime_iso` |
| `sensor.{station}_tide_forecast` | count of events | `events` | `forecast` array |

### Forecast Attribute Format

```json
{
  "forecast": [
    {"datetime": "2026-04-07T14:32:00-04:00", "type": "HIGH", "height_m": 3.1},
    {"datetime": "2026-04-07T19:05:00-04:00", "type": "LOW",  "height_m": 0.4}
  ]
}
```

Times are expressed in the local timezone of the HA installation.

---

## Config Flow (`config_flow.py`)

Fully UI-driven. No `configuration.yaml` support.

### Step 1 — Station Selection

A single form containing:
- **Station code** text field (e.g., `03580`)
- **Find nearest** button — reads `hass.config.latitude/longitude`, fetches full station list, computes Haversine distance, pre-fills the station code field
- **Resolved station name + region** shown read-only once a valid code is entered or auto-filled

Validation: code is validated live against `GET /api/v1/stations?code=...`. Invalid code shows inline error; user cannot proceed.

### Step 2 — Options

| Field | Default | Min | Max | Unit |
|---|---|---|---|---|
| Observed data poll interval | `5` | `1` | `60` | minutes |
| Prediction days | `7` | `1` | `30` | days |
| Prediction refresh interval | `24` | `1` | `24` | hours |

The max prediction days (`30`) will be validated against `allowedPeriodInDays` from `GET /api/v1/time-series-definitions` during setup.

### Options Flow

Step 2 is also exposed as an **Options flow**, allowing users to change intervals and prediction days after initial setup without re-adding the integration.

### Stored Config Entry Data

```python
{
    "station_id": str,                   # internal CHS API id
    "station_code": str,                 # e.g. "03580"
    "station_name": str,                 # e.g. "Quebec City"
    "observed_interval_minutes": int,    # default: 5
    "prediction_days": int,              # default: 7
    "prediction_interval_hours": int,    # default: 24
}
```

---

## Testing Strategy

| Layer | Approach |
|---|---|
| `api.py` | Unit tests with mocked `aiohttp` responses; cover happy path, 4xx, 5xx, network error |
| Tide math helpers | Pure function unit tests — no mocking needed |
| Coordinators | Unit tests using HA test fixtures; verify data shape and failure behaviour |
| Config flow | HA config flow test helpers; cover station lookup, nearest-station, validation errors, options flow |
| Sensors | Unit tests via coordinator fixture; verify state, unit, attributes for each sensor |

---

## HACS & Distribution

- `manifest.json` includes `"iot_class": "cloud_polling"`, `"version"`, `"domain": "cantides"`, `"requirements": []` (no extra pip deps)
- `hacs.json` at repo root for HACS discovery
- Initial release targets HACS custom repository; future goal is HA core integration list once the integration meets quality scale requirements

---

## Future Considerations (out of scope for v1)

- Bilingual support (French translations)
- Alert automations (e.g., notify when tide exceeds threshold)
- Historical data charting via long-term statistics
- Support for multiple stations per config entry
