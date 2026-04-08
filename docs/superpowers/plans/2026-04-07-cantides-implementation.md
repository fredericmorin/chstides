# CHSTides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HACS-installable Home Assistant custom integration that exposes Canadian Hydrographic Service tide data (live water level, tide phase, and multi-day predictions) via the CHS REST API.

**Architecture:** Two `DataUpdateCoordinator`s — one polling observed water level (`wlo`) on a short interval, one fetching predictions (`wlp`) daily. Five sensor entities subscribe to these coordinators. A UI config flow handles station selection (manual code or nearest-to-home) and interval configuration.

**Tech Stack:** Python 3.12, Home Assistant core libraries (aiohttp, DataUpdateCoordinator, ConfigFlow), pytest + pytest-homeassistant-custom-component, ruff

---

## File Map

| File | Responsibility |
|---|---|
| `custom_components/chstides/__init__.py` | Entry setup/unload, coordinator wiring |
| `custom_components/chstides/manifest.json` | HACS + HA integration metadata |
| `custom_components/chstides/const.py` | All constants and config keys |
| `custom_components/chstides/api.py` | CHS API client, data models, pure math helpers |
| `custom_components/chstides/coordinator.py` | `ObservedDataCoordinator`, `PredictionCoordinator` |
| `custom_components/chstides/sensor.py` | 5 sensor entities |
| `custom_components/chstides/config_flow.py` | Config flow + options flow |
| `custom_components/chstides/strings.json` | UI strings |
| `custom_components/chstides/translations/en.json` | English translations |
| `tests/conftest.py` | Shared fixtures |
| `tests/test_api.py` | API client + helper unit tests |
| `tests/test_coordinator.py` | Coordinator unit tests |
| `tests/test_config_flow.py` | Config flow integration tests |
| `tests/test_sensor.py` | Sensor unit tests |
| `Makefile` | Dev lifecycle targets |
| `scripts/dev_instance.sh` | Local HA dev instance launcher |
| `pyproject.toml` | Ruff + pytest config |
| `requirements_test.txt` | Test dependencies |
| `hacs.json` | HACS discovery |
| `CLAUDE.md` | Dev notes for AI collaboration |
| `README.md` | User-facing documentation |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `Makefile`
- Create: `scripts/dev_instance.sh`
- Create: `pyproject.toml`
- Create: `requirements_test.txt`
- Create: `hacs.json`
- Create: `.vscode/settings.json`
- Create: `.vscode/extensions.json`
- Create: `.vscode/launch.json`
- Create: `CLAUDE.md`
- Create: `README.md`

- [ ] **Step 1: Create Makefile**

```makefile
.PHONY: dev test lint format

dev:
	@bash scripts/dev_instance.sh

test:
	pytest tests/ -v

lint:
	ruff check custom_components/ tests/

format:
	ruff format custom_components/ tests/
```

- [ ] **Step 2: Create dev instance script**

```bash
#!/usr/bin/env bash
set -e

DEVCONFIG=".devconfig"

mkdir -p "$DEVCONFIG/custom_components"

if [ ! -L "$DEVCONFIG/custom_components/chstides" ]; then
    ln -s "$(pwd)/custom_components/chstides" "$DEVCONFIG/custom_components/chstides"
fi

pip install homeassistant --quiet
hass -c "$DEVCONFIG"
```

Make it executable: `chmod +x scripts/dev_instance.sh`

- [ ] **Step 3: Create pyproject.toml**

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: Create requirements_test.txt**

```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
aioresponses
```

- [ ] **Step 5: Create hacs.json**

```json
{
  "name": "CHSTides",
  "render_readme": true
}
```

- [ ] **Step 6: Create .vscode/settings.json**

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

- [ ] **Step 7: Create .vscode/extensions.json**

```json
{
  "recommendations": [
    "charliermarsh.ruff",
    "ms-python.python",
    "ms-python.vscode-pylance"
  ]
}
```

- [ ] **Step 8: Create .vscode/launch.json**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Home Assistant Dev",
      "type": "python",
      "request": "launch",
      "module": "homeassistant",
      "args": ["-c", ".devconfig"],
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v"],
      "justMyCode": false
    }
  ]
}
```

- [ ] **Step 9: Create CLAUDE.md**

```markdown
# CHSTides — Dev Notes

## Project
Home Assistant custom integration for Canadian Hydrographic Service tide data.
Distributed via HACS. API: https://api-sine.dfo-mpo.gc.ca

## Dev Commands
- `make dev` — start local HA instance with integration loaded (config in `.devconfig/`)
- `make test` — run pytest suite
- `make lint` — ruff check
- `make format` — ruff format

## Key Files
- `custom_components/chstides/api.py` — CHS API client + data models + pure helpers
- `custom_components/chstides/coordinator.py` — two DataUpdateCoordinators
- `custom_components/chstides/sensor.py` — 5 sensor entities
- `custom_components/chstides/config_flow.py` — UI config + options flow

## API Notes
- Base URL: https://api-sine.dfo-mpo.gc.ca
- Observed water level time-series-code: `wlo`
- Predicted water level time-series-code: `wlp` (verify via /api/v1/time-series-definitions)
- Station field names: id, code, officialName, latitude, longitude
- Data field names: eventDate, value, qcFlagCode

## Testing
Uses `pytest-homeassistant-custom-component` for HA fixtures.
Mock HTTP with `aioresponses`.
```

- [ ] **Step 10: Create README.md**

```markdown
# CHSTides

Home Assistant integration for Canadian Hydrographic Service (CHS) tide data.

## Features
- Live water level height sensor (observed, updates every 5 min by default)
- Tide phase sensor (Rising / Falling / High / Low)
- Next high tide sensor (time + height)
- Next low tide sensor (time + height)
- 7-day tide forecast sensor (full high/low event list as attribute)

## Installation
Install via HACS as a custom repository. After installation, add the integration
from Settings → Integrations → Add Integration → CHSTides.

## Configuration
- **Station code**: Enter a known CHS station code, or use "Find nearest" to auto-detect
  the closest station to your Home Assistant location
- **Observed poll interval**: How often to fetch live water level (default: 5 min)
- **Prediction days**: How many days of tide predictions to load (default: 7, max: 30)
- **Prediction refresh**: How often to refresh predictions (default: 24 h)

## Data Source
[Fisheries and Oceans Canada — Integrated Water Level System](https://www.dfo-mpo.gc.ca/)
```

- [ ] **Step 11: Commit**

```bash
git add Makefile scripts/ pyproject.toml requirements_test.txt hacs.json .vscode/ CLAUDE.md README.md
git commit -m "chore: project scaffolding, tooling, and docs"
```

---

## Task 2: Constants and Manifest

**Files:**
- Create: `custom_components/chstides/const.py`
- Create: `custom_components/chstides/manifest.json`

- [ ] **Step 1: Create const.py**

```python
DOMAIN = "chstides"
CHS_API_BASE = "https://api-sine.dfo-mpo.gc.ca"

TIME_SERIES_OBSERVED = "wlo"
TIME_SERIES_PREDICTED = "wlp"

DEFAULT_OBSERVED_INTERVAL_MINUTES = 5
DEFAULT_PREDICTION_DAYS = 7
DEFAULT_PREDICTION_INTERVAL_HOURS = 24

CONF_STATION_ID = "station_id"
CONF_STATION_CODE = "station_code"
CONF_STATION_NAME = "station_name"
CONF_OBSERVED_INTERVAL = "observed_interval_minutes"
CONF_PREDICTION_DAYS = "prediction_days"
CONF_PREDICTION_INTERVAL = "prediction_interval_hours"
```

- [ ] **Step 2: Create manifest.json**

```json
{
  "domain": "chstides",
  "name": "CHSTides",
  "version": "0.1.0",
  "documentation": "https://github.com/placeholder/chstides",
  "iot_class": "cloud_polling",
  "config_flow": true,
  "codeowners": [],
  "requirements": []
}
```

- [ ] **Step 3: Create package init (empty for now)**

Create `custom_components/chstides/__init__.py` with just a module docstring:

```python
"""CHSTides — Canadian Hydrographic Service tide data for Home Assistant."""
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/
git commit -m "chore: add integration constants and manifest"
```

---

## Task 3: API Data Models and Station Helpers

**Files:**
- Create: `custom_components/chstides/api.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for data models and find_nearest_station**

Create `tests/__init__.py` (empty).

Create `tests/test_api.py`:

```python
import math
import pytest
from datetime import datetime, timezone
from custom_components.chstides.api import (
    Station,
    ObservedData,
    PredictionPoint,
    TidePhase,
    CHSApiError,
    find_nearest_station,
)


def test_station_dataclass():
    s = Station(id="abc", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22)
    assert s.id == "abc"
    assert s.code == "03580"
    assert s.latitude == 46.81


def test_find_nearest_station_returns_closest():
    stations = [
        Station("1", "A", "Far", 60.0, -80.0),
        Station("2", "B", "Near", 45.5, -73.6),
        Station("3", "C", "Mid", 50.0, -75.0),
    ]
    result = find_nearest_station(stations, 45.4, -73.5)
    assert result.code == "B"


def test_find_nearest_station_single():
    stations = [Station("1", "A", "Only", 46.0, -72.0)]
    result = find_nearest_station(stations, 45.0, -71.0)
    assert result.code == "A"


def test_chs_api_error_stores_status():
    err = CHSApiError("not found", 404)
    assert err.status_code == 404
    assert "not found" in str(err)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py::test_station_dataclass tests/test_api.py::test_find_nearest_station_returns_closest -v
```

Expected: `ImportError: cannot import name 'Station' from 'custom_components.chstides.api'`

- [ ] **Step 3: Implement data models and find_nearest_station in api.py**

```python
"""CHS API client, data models, and tide math helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


class TidePhase:
    RISING = "Rising"
    FALLING = "Falling"
    HIGH = "High"
    LOW = "Low"


class CHSApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
    time_series_code: str


@dataclass
class PredictionPoint:
    timestamp: datetime
    height_m: float
    type: Literal["HIGH", "LOW", "UNKNOWN"]


def find_nearest_station(stations: list[Station], lat: float, lon: float) -> Station:
    """Return the station closest to (lat, lon) using Haversine distance."""

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return min(stations, key=lambda s: haversine(lat, lon, s.latitude, s.longitude))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py::test_station_dataclass tests/test_api.py::test_find_nearest_station_returns_closest tests/test_api.py::test_find_nearest_station_single tests/test_api.py::test_chs_api_error_stores_status -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/
git commit -m "feat: API data models, CHSApiError, find_nearest_station"
```

---

## Task 4: Tide Math Helpers

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for tide math helpers**

Append to `tests/test_api.py`:

```python
from custom_components.chstides.api import derive_tide_phase, find_highs_lows


def _obs(height: float) -> ObservedData:
    return ObservedData("s1", datetime.now(timezone.utc), height, "wlo")


def test_derive_tide_phase_rising():
    assert derive_tide_phase([_obs(1.0), _obs(1.5)]) == TidePhase.RISING


def test_derive_tide_phase_falling():
    assert derive_tide_phase([_obs(1.5), _obs(1.0)]) == TidePhase.FALLING


def test_derive_tide_phase_single_point_defaults_rising():
    assert derive_tide_phase([_obs(1.0)]) == TidePhase.RISING


def test_derive_tide_phase_empty_defaults_rising():
    assert derive_tide_phase([]) == TidePhase.RISING


def test_find_highs_lows_identifies_single_peak_and_valley():
    # heights: low -> peak -> low -> valley -> low
    heights = [0.5, 1.0, 2.0, 1.5, 0.8, 0.3, 0.6]
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in heights]
    result = find_highs_lows(points)
    highs = [p for p in result if p.type == "HIGH"]
    lows = [p for p in result if p.type == "LOW"]
    assert len(highs) == 1
    assert highs[0].height_m == 2.0
    assert len(lows) == 1
    assert lows[0].height_m == 0.3


def test_find_highs_lows_empty_for_short_series():
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in [1.0, 2.0]]
    assert find_highs_lows(points) == []


def test_find_highs_lows_flat_series_returns_empty():
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, 1.0, "UNKNOWN") for _ in range(5)]
    assert find_highs_lows(points) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -k "derive_tide_phase or find_highs_lows" -v
```

Expected: `ImportError: cannot import name 'derive_tide_phase'`

- [ ] **Step 3: Implement derive_tide_phase and find_highs_lows in api.py**

Append to `api.py` (after the dataclasses):

```python
def derive_tide_phase(recent_points: list[ObservedData]) -> str:
    """Derive tide phase from the trend of recent observed water level points."""
    if len(recent_points) < 2:
        return TidePhase.RISING
    diff = recent_points[-1].height_m - recent_points[-2].height_m
    return TidePhase.RISING if diff >= 0 else TidePhase.FALLING


def find_highs_lows(points: list[PredictionPoint]) -> list[PredictionPoint]:
    """Identify local maxima (HIGH) and minima (LOW) in a prediction time series."""
    if len(points) < 3:
        return []
    result = []
    for i in range(1, len(points) - 1):
        prev_h = points[i - 1].height_m
        curr_h = points[i].height_m
        next_h = points[i + 1].height_m
        if curr_h > prev_h and curr_h > next_h:
            result.append(PredictionPoint(points[i].timestamp, curr_h, "HIGH"))
        elif curr_h < prev_h and curr_h < next_h:
            result.append(PredictionPoint(points[i].timestamp, curr_h, "LOW"))
    return result
```

- [ ] **Step 4: Run full test file to verify all pass**

```bash
pytest tests/test_api.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: tide math helpers — derive_tide_phase, find_highs_lows"
```

---

## Task 5: CHS HTTP Client

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for the HTTP client**

Append to `tests/test_api.py`:

```python
import aiohttp
import pytest
from aioresponses import aioresponses
from custom_components.chstides.api import CHSApiClient
from custom_components.chstides.const import CHS_API_BASE


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


@pytest.mark.asyncio
async def test_get_stations_returns_stations(mock_aiohttp):
    mock_aiohttp.get(
        f"{CHS_API_BASE}/api/v1/stations",
        payload=[
            {
                "id": "s001",
                "code": "03580",
                "officialName": "Quebec City",
                "latitude": 46.81,
                "longitude": -71.22,
            }
        ],
    )
    async with aiohttp.ClientSession() as session:
        client = CHSApiClient(session)
        stations = await client.get_stations()
    assert len(stations) == 1
    assert stations[0].code == "03580"
    assert stations[0].name == "Quebec City"


@pytest.mark.asyncio
async def test_get_stations_with_code_filter(mock_aiohttp):
    mock_aiohttp.get(
        f"{CHS_API_BASE}/api/v1/stations?code=03580",
        payload=[
            {
                "id": "s001",
                "code": "03580",
                "officialName": "Quebec City",
                "latitude": 46.81,
                "longitude": -71.22,
            }
        ],
    )
    async with aiohttp.ClientSession() as session:
        client = CHSApiClient(session)
        stations = await client.get_stations(code="03580")
    assert stations[0].code == "03580"


@pytest.mark.asyncio
async def test_get_stations_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(f"{CHS_API_BASE}/api/v1/stations", status=500)
    async with aiohttp.ClientSession() as session:
        client = CHSApiClient(session)
        with pytest.raises(CHSApiError) as exc_info:
            await client.get_stations()
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_observed_water_level(mock_aiohttp):
    mock_aiohttp.get(
        f"{CHS_API_BASE}/api/v1/stations/s001/data",
        payload=[
            {"eventDate": "2026-04-07T12:00:00Z", "value": 1.42, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T12:05:00Z", "value": 1.50, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        client = CHSApiClient(session)
        points = await client.get_observed_water_level("s001")
    assert len(points) == 2
    assert points[0].height_m == 1.42
    assert points[1].height_m == 1.50


@pytest.mark.asyncio
async def test_get_predictions_returns_highs_lows(mock_aiohttp):
    # 5 points forming one peak and one valley
    mock_aiohttp.get(
        f"{CHS_API_BASE}/api/v1/stations/s001/data",
        payload=[
            {"eventDate": "2026-04-07T00:00:00Z", "value": 0.5, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T06:00:00Z", "value": 3.1, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T12:00:00Z", "value": 1.0, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T18:00:00Z", "value": 0.2, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T23:00:00Z", "value": 1.5, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        client = CHSApiClient(session)
        points = await client.get_predictions("s001", days=1)
    highs = [p for p in points if p.type == "HIGH"]
    lows = [p for p in points if p.type == "LOW"]
    assert highs[0].height_m == 3.1
    assert lows[0].height_m == 0.2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -k "get_stations or get_observed or get_predictions" -v
```

Expected: `ImportError` or `AttributeError` — `CHSApiClient` not defined

- [ ] **Step 3: Implement CHSApiClient in api.py**

Add at the top of `api.py`:

```python
import aiohttp
from datetime import datetime, timedelta, timezone
```

Append the client class to `api.py`:

```python
class CHSApiClient:
    """HTTP client for the CHS Integrated Water Level System API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        from .const import CHS_API_BASE

        url = f"{CHS_API_BASE}{path}"
        async with self._session.get(url, params=params) as resp:
            if resp.status >= 400:
                raise CHSApiError(f"CHS API returned {resp.status}", resp.status)
            return await resp.json()

    async def get_stations(self, code: str | None = None) -> list[Station]:
        params: dict[str, str] = {}
        if code:
            params["code"] = code
        data = await self._get("/api/v1/stations", params or None)
        return [
            Station(
                id=s["id"],
                code=s["code"],
                name=s["officialName"],
                latitude=s["latitude"],
                longitude=s["longitude"],
            )
            for s in data
        ]

    async def get_station(self, station_id: str) -> Station:
        data = await self._get(f"/api/v1/stations/{station_id}")
        return Station(
            id=data["id"],
            code=data["code"],
            name=data["officialName"],
            latitude=data["latitude"],
            longitude=data["longitude"],
        )

    async def get_observed_water_level(self, station_id: str) -> list[ObservedData]:
        from .const import TIME_SERIES_OBSERVED

        now = datetime.now(timezone.utc)
        from_dt = now - timedelta(minutes=30)
        params = {
            "time-series-code": TIME_SERIES_OBSERVED,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data = await self._get(f"/api/v1/stations/{station_id}/data", params)
        return [
            ObservedData(
                station_id=station_id,
                timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
                height_m=float(d["value"]),
                time_series_code=TIME_SERIES_OBSERVED,
            )
            for d in data
        ]

    async def get_predictions(self, station_id: str, days: int) -> list[PredictionPoint]:
        from .const import TIME_SERIES_PREDICTED

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = today + timedelta(days=days, hours=23, minutes=59, seconds=59)
        params = {
            "time-series-code": TIME_SERIES_PREDICTED,
            "from": today.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data = await self._get(f"/api/v1/stations/{station_id}/data", params)
        raw = [
            PredictionPoint(
                timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
                height_m=float(d["value"]),
                type="UNKNOWN",
            )
            for d in data
        ]
        return find_highs_lows(raw)
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/test_api.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: CHS HTTP client — get_stations, get_observed_water_level, get_predictions"
```

---

## Task 6: Data Coordinators

**Files:**
- Create: `custom_components/chstides/coordinator.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write failing tests for coordinators**

Create `tests/test_coordinator.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.chstides.api import ObservedData, PredictionPoint, TidePhase, CHSApiError
from custom_components.chstides.coordinator import ObservedDataCoordinator, PredictionCoordinator


@pytest.fixture
def hass(hass):
    return hass


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_observed_coordinator_stores_latest_and_phase(hass, mock_client, now):
    mock_client.get_observed_water_level.return_value = [
        ObservedData("s1", now, 1.0, "wlo"),
        ObservedData("s1", now, 1.5, "wlo"),
    ]
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    await coord.async_refresh()

    assert coord.latest.height_m == 1.5
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_api_error(hass, mock_client):
    mock_client.get_observed_water_level.side_effect = CHSApiError("timeout", None)
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    with pytest.raises(UpdateFailed):
        await coord.async_refresh()


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_empty_data(hass, mock_client):
    mock_client.get_observed_water_level.return_value = []
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    with pytest.raises(UpdateFailed):
        await coord.async_refresh()


@pytest.mark.asyncio
async def test_prediction_coordinator_sets_next_high_and_low(hass, mock_client, now):
    future_high = datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc)
    future_low = datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc)
    mock_client.get_predictions.return_value = [
        PredictionPoint(future_high, 3.1, "HIGH"),
        PredictionPoint(future_low, 0.4, "LOW"),
    ]
    coord = PredictionCoordinator(hass, mock_client, "s1", 7, 24)
    await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
    assert coord.next_low.height_m == 0.4
    assert len(coord.forecast) == 2


@pytest.mark.asyncio
async def test_prediction_coordinator_keeps_stale_on_error(hass, mock_client, now):
    future = datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc)
    mock_client.get_predictions.return_value = [PredictionPoint(future, 3.1, "HIGH")]
    coord = PredictionCoordinator(hass, mock_client, "s1", 7, 24)
    await coord.async_refresh()

    # Second call fails — stale data retained
    mock_client.get_predictions.side_effect = CHSApiError("timeout", None)
    await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_coordinator.py -v
```

Expected: `ImportError: cannot import name 'ObservedDataCoordinator'`

- [ ] **Step 3: Implement coordinator.py**

```python
"""DataUpdateCoordinators for observed water level and tide predictions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CHSApiClient, CHSApiError, ObservedData, PredictionPoint, TidePhase, derive_tide_phase
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ObservedDataCoordinator(DataUpdateCoordinator):
    """Polls observed water level (wlo) on a short interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CHSApiClient,
        station_id: str,
        interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_observed_{station_id}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._client = client
        self._station_id = station_id
        self.latest: ObservedData | None = None
        self.phase: str = TidePhase.RISING

    async def _async_update_data(self) -> dict:
        try:
            points = await self._client.get_observed_water_level(self._station_id)
        except CHSApiError as err:
            raise UpdateFailed(f"CHS API error: {err}") from err
        if not points:
            raise UpdateFailed("No observed data returned from CHS API")
        self.latest = points[-1]
        self.phase = derive_tide_phase(points)
        return {"latest": self.latest, "phase": self.phase}


class PredictionCoordinator(DataUpdateCoordinator):
    """Polls tide predictions (wlp) daily and caches stale data on failure."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CHSApiClient,
        station_id: str,
        days: int,
        interval_hours: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_predictions_{station_id}",
            update_interval=timedelta(hours=interval_hours),
        )
        self._client = client
        self._station_id = station_id
        self._days = days
        self.forecast: list[PredictionPoint] = []
        self.next_high: PredictionPoint | None = None
        self.next_low: PredictionPoint | None = None

    async def _async_update_data(self) -> dict:
        try:
            points = await self._client.get_predictions(self._station_id, self._days)
        except CHSApiError as err:
            _LOGGER.warning("Failed to fetch predictions, keeping stale data: %s", err)
            return {"forecast": self.forecast, "next_high": self.next_high, "next_low": self.next_low}

        now = datetime.now(timezone.utc)
        self.forecast = points
        future = [p for p in points if p.timestamp > now]
        self.next_high = next((p for p in future if p.type == "HIGH"), None)
        self.next_low = next((p for p in future if p.type == "LOW"), None)
        return {"forecast": self.forecast, "next_high": self.next_high, "next_low": self.next_low}
```

- [ ] **Step 4: Run coordinator tests**

```bash
pytest tests/test_coordinator.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/coordinator.py tests/test_coordinator.py
git commit -m "feat: ObservedDataCoordinator and PredictionCoordinator"
```

---

## Task 7: Integration Setup and Teardown

**Files:**
- Modify: `custom_components/chstides/__init__.py`

- [ ] **Step 1: Implement async_setup_entry and async_unload_entry**

Replace `custom_components/chstides/__init__.py` with:

```python
"""CHSTides — Canadian Hydrographic Service tide data for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CHSApiClient
from .const import (
    CONF_OBSERVED_INTERVAL,
    CONF_PREDICTION_DAYS,
    CONF_PREDICTION_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_OBSERVED_INTERVAL_MINUTES,
    DEFAULT_PREDICTION_DAYS,
    DEFAULT_PREDICTION_INTERVAL_HOURS,
    DOMAIN,
)
from .coordinator import ObservedDataCoordinator, PredictionCoordinator

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CHSTides from a config entry."""
    session = async_get_clientsession(hass)
    client = CHSApiClient(session)
    station_id = entry.data[CONF_STATION_ID]

    def _opt(key: str, default: int) -> int:
        return entry.options.get(key, entry.data.get(key, default))

    observed_coord = ObservedDataCoordinator(
        hass,
        client,
        station_id,
        _opt(CONF_OBSERVED_INTERVAL, DEFAULT_OBSERVED_INTERVAL_MINUTES),
    )
    prediction_coord = PredictionCoordinator(
        hass,
        client,
        station_id,
        _opt(CONF_PREDICTION_DAYS, DEFAULT_PREDICTION_DAYS),
        _opt(CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL_HOURS),
    )

    await observed_coord.async_config_entry_first_refresh()
    await prediction_coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "observed": observed_coord,
        "predictions": prediction_coord,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

- [ ] **Step 2: Lint check**

```bash
ruff check custom_components/chstides/__init__.py
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add custom_components/chstides/__init__.py
git commit -m "feat: integration setup/unload, options reload listener"
```

---

## Task 8: Config Flow — Station Selection (Step 1)

**Files:**
- Create: `custom_components/chstides/config_flow.py`
- Create: `custom_components/chstides/strings.json`
- Create: `custom_components/chstides/translations/en.json`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing tests for step 1 of the config flow**

Create `tests/test_config_flow.py`:

```python
from unittest.mock import AsyncMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.chstides.api import Station
from custom_components.chstides.const import DOMAIN


MOCK_STATION = Station(id="s001", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22)


@pytest.fixture(autouse=True)
def mock_client_setup():
    with patch("custom_components.chstides.config_flow.CHSApiClient") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value = client
        client.get_stations.return_value = [MOCK_STATION]
        yield client


@pytest.mark.asyncio
async def test_step_station_shows_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"


@pytest.mark.asyncio
async def test_step_station_with_valid_code_proceeds(hass: HomeAssistant, mock_client_setup):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "03580", "auto_detect": False},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "options"


@pytest.mark.asyncio
async def test_step_station_with_invalid_code_shows_error(hass: HomeAssistant, mock_client_setup):
    mock_client_setup.get_stations.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "INVALID", "auto_detect": False},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"station_code": "station_not_found"}


@pytest.mark.asyncio
async def test_step_station_auto_detect_prefills_nearest(hass: HomeAssistant, mock_client_setup):
    hass.config.latitude = 46.8
    hass.config.longitude = -71.2
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "", "auto_detect": True},
    )
    # Re-shows the form with station_code pre-filled
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"
    assert result["description_placeholders"]["nearest_station"] == "Quebec City (03580)"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config_flow.py -v
```

Expected: `ImportError` or `FlowNotFound` — config flow not registered

- [ ] **Step 3: Create strings.json**

```json
{
  "config": {
    "step": {
      "station": {
        "title": "Select Tide Station",
        "description": "Enter a CHS station code or find the nearest station to your home location.",
        "data": {
          "station_code": "Station code",
          "auto_detect": "Find nearest station to home location"
        }
      },
      "options": {
        "title": "Polling Options",
        "data": {
          "observed_interval_minutes": "Observed data poll interval (minutes)",
          "prediction_days": "Days of predictions to load",
          "prediction_interval_hours": "Prediction refresh interval (hours)"
        }
      }
    },
    "error": {
      "station_not_found": "No station found for that code. Check and try again.",
      "cannot_connect": "Cannot connect to the CHS API. Check your network."
    },
    "abort": {
      "already_configured": "This station is already configured."
    }
  },
  "options": {
    "step": {
      "options": {
        "title": "CHSTides Options",
        "data": {
          "observed_interval_minutes": "Observed data poll interval (minutes)",
          "prediction_days": "Days of predictions to load",
          "prediction_interval_hours": "Prediction refresh interval (hours)"
        }
      }
    }
  }
}
```

- [ ] **Step 4: Create translations/en.json**

Copy strings.json content verbatim:

```bash
cp custom_components/chstides/strings.json custom_components/chstides/translations/en.json
```

- [ ] **Step 5: Implement config_flow.py (Step 1 — station selection)**

```python
"""Config flow for CHSTides."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import CHSApiClient, CHSApiError, find_nearest_station
from .const import (
    CONF_OBSERVED_INTERVAL,
    CONF_PREDICTION_DAYS,
    CONF_PREDICTION_INTERVAL,
    CONF_STATION_CODE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_OBSERVED_INTERVAL_MINUTES,
    DEFAULT_PREDICTION_DAYS,
    DEFAULT_PREDICTION_INTERVAL_HOURS,
    DOMAIN,
)

STEP_STATION_SCHEMA = vol.Schema(
    {
        vol.Optional("station_code", default=""): TextSelector(),
        vol.Optional("auto_detect", default=False): BooleanSelector(),
    }
)

STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_OBSERVED_INTERVAL, default=DEFAULT_OBSERVED_INTERVAL_MINUTES
        ): NumberSelector(NumberSelectorConfig(min=1, max=60, mode=NumberSelectorMode.BOX)),
        vol.Required(
            CONF_PREDICTION_DAYS, default=DEFAULT_PREDICTION_DAYS
        ): NumberSelector(NumberSelectorConfig(min=1, max=30, mode=NumberSelectorMode.BOX)),
        vol.Required(
            CONF_PREDICTION_INTERVAL, default=DEFAULT_PREDICTION_INTERVAL_HOURS
        ): NumberSelector(NumberSelectorConfig(min=1, max=24, mode=NumberSelectorMode.BOX)),
    }
)


class CHSTidesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the CHSTides config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._station_id: str | None = None
        self._station_code: str | None = None
        self._station_name: str | None = None
        self._nearest_hint: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        return await self.async_step_station(user_input)

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        client = CHSApiClient(session)

        if user_input is not None:
            if user_input.get("auto_detect"):
                try:
                    stations = await client.get_stations()
                    nearest = find_nearest_station(
                        stations,
                        self.hass.config.latitude,
                        self.hass.config.longitude,
                    )
                    self._nearest_hint = f"{nearest.name} ({nearest.code})"
                    return self.async_show_form(
                        step_id="station",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("station_code", default=nearest.code): TextSelector(),
                                vol.Optional("auto_detect", default=False): BooleanSelector(),
                            }
                        ),
                        description_placeholders={"nearest_station": self._nearest_hint},
                    )
                except CHSApiError:
                    errors["base"] = "cannot_connect"
            else:
                code = user_input.get("station_code", "").strip()
                if not code:
                    errors["station_code"] = "station_not_found"
                else:
                    try:
                        stations = await client.get_stations(code=code)
                        if not stations:
                            errors["station_code"] = "station_not_found"
                        else:
                            station = stations[0]
                            await self.async_set_unique_id(station.id)
                            self._abort_if_unique_id_configured()
                            self._station_id = station.id
                            self._station_code = station.code
                            self._station_name = station.name
                            return await self.async_step_options()
                    except CHSApiError:
                        errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="station",
            data_schema=STEP_STATION_SCHEMA,
            errors=errors,
            description_placeholders={"nearest_station": self._nearest_hint or ""},
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            return self.async_create_entry(
                title=self._station_name,
                data={
                    CONF_STATION_ID: self._station_id,
                    CONF_STATION_CODE: self._station_code,
                    CONF_STATION_NAME: self._station_name,
                    CONF_OBSERVED_INTERVAL: int(user_input[CONF_OBSERVED_INTERVAL]),
                    CONF_PREDICTION_DAYS: int(user_input[CONF_PREDICTION_DAYS]),
                    CONF_PREDICTION_INTERVAL: int(user_input[CONF_PREDICTION_INTERVAL]),
                },
            )
        return self.async_show_form(step_id="options", data_schema=STEP_OPTIONS_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CHSTidesOptionsFlow(config_entry)


class CHSTidesOptionsFlow(OptionsFlow):
    """Handle CHSTides options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_OBSERVED_INTERVAL: int(user_input[CONF_OBSERVED_INTERVAL]),
                    CONF_PREDICTION_DAYS: int(user_input[CONF_PREDICTION_DAYS]),
                    CONF_PREDICTION_INTERVAL: int(user_input[CONF_PREDICTION_INTERVAL]),
                },
            )
        current = self._config_entry.options or self._config_entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OBSERVED_INTERVAL,
                    default=current.get(CONF_OBSERVED_INTERVAL, DEFAULT_OBSERVED_INTERVAL_MINUTES),
                ): NumberSelector(NumberSelectorConfig(min=1, max=60, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_PREDICTION_DAYS,
                    default=current.get(CONF_PREDICTION_DAYS, DEFAULT_PREDICTION_DAYS),
                ): NumberSelector(NumberSelectorConfig(min=1, max=30, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_PREDICTION_INTERVAL,
                    default=current.get(CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL_HOURS),
                ): NumberSelector(NumberSelectorConfig(min=1, max=24, mode=NumberSelectorMode.BOX)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
```

- [ ] **Step 6: Run config flow tests**

```bash
pytest tests/test_config_flow.py -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add custom_components/chstides/config_flow.py custom_components/chstides/strings.json custom_components/chstides/translations/ tests/test_config_flow.py
git commit -m "feat: config flow with station lookup, auto-detect nearest, and options flow"
```

---

## Task 9: Observed Sensors

**Files:**
- Create: `custom_components/chstides/sensor.py`
- Create: `tests/test_sensor.py`

- [ ] **Step 1: Write failing tests for observed sensors**

Create `tests/test_sensor.py`:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant

from custom_components.chstides.api import ObservedData, TidePhase
from custom_components.chstides.coordinator import ObservedDataCoordinator, PredictionCoordinator
from custom_components.chstides.sensor import WaterLevelSensor, TidePhaseSensor


@pytest.fixture
def observed_coord(hass):
    coord = MagicMock(spec=ObservedDataCoordinator)
    coord.hass = hass
    coord.latest = ObservedData(
        station_id="s001",
        timestamp=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        height_m=1.42,
        time_series_code="wlo",
    )
    coord.phase = TidePhase.RISING
    return coord


def test_water_level_sensor_state(observed_coord):
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value == 1.42
    assert sensor.native_unit_of_measurement == "m"


def test_water_level_sensor_attributes(observed_coord):
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    attrs = sensor.extra_state_attributes
    assert attrs["station_id"] == "s001"
    assert "timestamp" in attrs


def test_water_level_sensor_none_when_no_data(observed_coord):
    observed_coord.latest = None
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value is None


def test_tide_phase_sensor_state(observed_coord):
    sensor = TidePhaseSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value == TidePhase.RISING


def test_tide_phase_sensor_unique_id(observed_coord):
    sensor = TidePhaseSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.unique_id == "entry1_tide_phase"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sensor.py -k "water_level or tide_phase" -v
```

Expected: `ImportError: cannot import name 'WaterLevelSensor'`

- [ ] **Step 3: Implement sensor.py with observed sensors**

```python
"""Sensor entities for CHSTides."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_STATION_NAME, CONF_STATION_CODE, CONF_STATION_ID
from .coordinator import ObservedDataCoordinator, PredictionCoordinator


def _device_info(station_name: str, station_code: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, station_code)},
        name=station_name,
        manufacturer="DFO-MPO / CHS",
        model="Tide Station",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    observed = data["observed"]
    predictions = data["predictions"]

    station_name = entry.data[CONF_STATION_NAME]
    station_code = entry.data[CONF_STATION_CODE]
    station_id = entry.data[CONF_STATION_ID]

    async_add_entities(
        [
            WaterLevelSensor(observed, station_name, station_code, station_id, entry.entry_id),
            TidePhaseSensor(observed, station_name, station_code, station_id, entry.entry_id),
            NextHighTideSensor(predictions, station_name, station_code, station_id, entry.entry_id),
            NextLowTideSensor(predictions, station_name, station_code, station_id, entry.entry_id),
            TideForecastSensor(predictions, station_name, station_code, station_id, entry.entry_id),
        ]
    )


class WaterLevelSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Current observed water level height."""

    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_name = f"{station_name} Water Level"
        self._attr_unique_id = f"{entry_id}_water_level"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.latest is None:
            return None
        return self.coordinator.latest.height_m

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.latest is None:
            return {}
        return {
            "station_id": self._station_id,
            "timestamp": self.coordinator.latest.timestamp.isoformat(),
        }


class TidePhaseSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Current tide phase derived from recent observed water level trend."""

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Tide Phase"
        self._attr_unique_id = f"{entry_id}_tide_phase"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.latest is None:
            return {}
        return {"timestamp": self.coordinator.latest.timestamp.isoformat()}
```

- [ ] **Step 4: Run observed sensor tests**

```bash
pytest tests/test_sensor.py -k "water_level or tide_phase" -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/sensor.py tests/test_sensor.py
git commit -m "feat: WaterLevelSensor and TidePhaseSensor"
```

---

## Task 10: Prediction Sensors

**Files:**
- Modify: `custom_components/chstides/sensor.py`
- Modify: `tests/test_sensor.py`

- [ ] **Step 1: Write failing tests for prediction sensors**

Append to `tests/test_sensor.py`:

```python
from datetime import datetime, timezone
from custom_components.chstides.api import PredictionPoint
from custom_components.chstides.sensor import NextHighTideSensor, NextLowTideSensor, TideForecastSensor


@pytest.fixture
def prediction_coord(hass):
    future_high = datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc)
    future_low = datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc)
    coord = MagicMock(spec=PredictionCoordinator)
    coord.hass = hass
    coord.next_high = PredictionPoint(future_high, 3.1, "HIGH")
    coord.next_low = PredictionPoint(future_low, 0.4, "LOW")
    coord.forecast = [
        PredictionPoint(future_high, 3.1, "HIGH"),
        PredictionPoint(future_low, 0.4, "LOW"),
    ]
    return coord


def test_next_high_tide_sensor_state(prediction_coord):
    sensor = NextHighTideSensor(prediction_coord, "Quebec City", "03580", "s001", "entry1")
    assert "14:30" in sensor.native_value


def test_next_high_tide_sensor_attributes(prediction_coord):
    sensor = NextHighTideSensor(prediction_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.extra_state_attributes["height_m"] == 3.1
    assert "datetime_iso" in sensor.extra_state_attributes


def test_next_low_tide_sensor_state(prediction_coord):
    sensor = NextLowTideSensor(prediction_coord, "Quebec City", "03580", "s001", "entry1")
    assert "20:00" in sensor.native_value


def test_tide_forecast_sensor_state_is_count(prediction_coord):
    sensor = TideForecastSensor(prediction_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value == 2


def test_tide_forecast_sensor_forecast_attribute(prediction_coord):
    sensor = TideForecastSensor(prediction_coord, "Quebec City", "03580", "s001", "entry1")
    forecast = sensor.extra_state_attributes["forecast"]
    assert len(forecast) == 2
    assert forecast[0]["type"] == "HIGH"
    assert forecast[0]["height_m"] == 3.1
    assert "datetime" in forecast[0]


def test_next_high_tide_none_when_no_data(hass):
    coord = MagicMock(spec=PredictionCoordinator)
    coord.hass = hass
    coord.next_high = None
    sensor = NextHighTideSensor(coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sensor.py -k "next_high or next_low or forecast" -v
```

Expected: `ImportError: cannot import name 'NextHighTideSensor'`

- [ ] **Step 3: Append prediction sensor classes to sensor.py**

```python
class NextHighTideSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Next predicted high tide — time as state, height and ISO datetime as attributes."""

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Next High Tide"
        self._attr_unique_id = f"{entry_id}_next_high_tide"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.next_high is None:
            return None
        local_dt = self.coordinator.next_high.timestamp.astimezone()
        return local_dt.strftime("%H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.next_high is None:
            return {}
        return {
            "height_m": self.coordinator.next_high.height_m,
            "datetime_iso": self.coordinator.next_high.timestamp.isoformat(),
        }


class NextLowTideSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Next predicted low tide — time as state, height and ISO datetime as attributes."""

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Next Low Tide"
        self._attr_unique_id = f"{entry_id}_next_low_tide"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.next_low is None:
            return None
        local_dt = self.coordinator.next_low.timestamp.astimezone()
        return local_dt.strftime("%H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.next_low is None:
            return {}
        return {
            "height_m": self.coordinator.next_low.height_m,
            "datetime_iso": self.coordinator.next_low.timestamp.isoformat(),
        }


class TideForecastSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Full N-day tide forecast — event count as state, list of highs/lows as attribute."""

    _attr_native_unit_of_measurement = "events"

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Tide Forecast"
        self._attr_unique_id = f"{entry_id}_tide_forecast"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.forecast)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "forecast": [
                {
                    "datetime": p.timestamp.astimezone().isoformat(),
                    "type": p.type,
                    "height_m": p.height_m,
                }
                for p in self.coordinator.forecast
            ]
        }
```

- [ ] **Step 4: Run full sensor test suite**

```bash
pytest tests/test_sensor.py -v
```

Expected: all tests pass

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Lint everything**

```bash
ruff check custom_components/ tests/
```

Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add custom_components/chstides/sensor.py tests/test_sensor.py
git commit -m "feat: NextHighTideSensor, NextLowTideSensor, TideForecastSensor"
```

---

## Task 11: Dev Environment Smoke Test

**Files:**
- No code changes — this task validates `make dev` works end-to-end

- [ ] **Step 1: Install test dependencies**

```bash
pip install -r requirements_test.txt
```

Expected: installs without errors

- [ ] **Step 2: Run the full test suite once more cleanly**

```bash
make test
```

Expected: all tests pass, 0 failures

- [ ] **Step 3: Run lint**

```bash
make lint
```

Expected: no ruff errors

- [ ] **Step 4: Verify make dev starts HA**

```bash
make dev
```

Expected:
- HA starts and logs appear in terminal
- Browse to `http://localhost:8123` — onboarding screen appears
- Navigate to Settings → Integrations → Add Integration — "CHSTides" appears in the list

If "CHSTides" does not appear: check that `.devconfig/custom_components/chstides` symlink points to `custom_components/chstides/` and that `manifest.json` is valid JSON with `"config_flow": true`.

- [ ] **Step 5: Walk through config flow manually**

1. Click CHSTides → Add
2. Click "Find nearest station to home location" checkbox → Submit → verify station code is pre-filled
3. Clear and type a known station code (e.g., `03580`) → Submit
4. Set options to defaults → Submit
5. Verify 5 entities appear under the new device in Integrations

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: verify dev environment and integration smoke test"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec requirement | Covered by |
|---|---|
| Live water level sensor | Task 9: `WaterLevelSensor` |
| Tide phase sensor (Rising/Falling/High/Low) | Task 9: `TidePhaseSensor` + Task 4: `derive_tide_phase` |
| Next high tide sensor | Task 10: `NextHighTideSensor` |
| Next low tide sensor | Task 10: `NextLowTideSensor` |
| Full N-day forecast sensor with attribute | Task 10: `TideForecastSensor` |
| Two independent coordinators | Task 6 |
| Configurable poll intervals with defaults | Task 7 (`__init__.py`) + Task 8 (config flow) |
| Config flow — station code entry | Task 8 |
| Config flow — "Find nearest" auto-detect | Task 8 |
| Config flow — options flow for post-setup changes | Task 8 |
| HACS metadata | Task 2: `manifest.json`, `hacs.json` |
| Makefile with dev/test/lint/format | Task 1 |
| `make dev` starts HA with integration loaded | Task 1 + Task 11 |
| .vscode config | Task 1 |
| CLAUDE.md | Task 1 |
| README.md | Task 1 |
| TDD throughout | Every task follows write-test → fail → implement → pass |

All spec requirements covered.
