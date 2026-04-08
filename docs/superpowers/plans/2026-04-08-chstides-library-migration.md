# CHSTides Library Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled `CHSApiClient` / direct `aiohttp` calls with `chstides` 0.3.2 (`pychs.CHS_IWLS`), injecting the HA-shared session via subclass and exposing module-level functions as the public API.

**Architecture:** A private `_SessionCHSIWLS(CHS_IWLS)` subclass overrides `_async_get_data` to use an injected `aiohttp.ClientSession` and adds HTTP error handling. Three module-level async functions (`get_stations`, `get_observed_water_level`, `get_predictions`) replace `CHSApiClient` — coordinators and config flow call these directly, passing the HA session. Predictions switch from `wlp` + local peak-detection to the `wlp-hilo` time series (API-native HIGH/LOW events).

**Tech Stack:** Python 3.14, Home Assistant, `chstides==0.3.2` (PyPI), `pychs.CHS_IWLS`, `aiohttp`, `pytest`, `aioresponses`

---

## File Map

| File | Change |
|------|--------|
| `custom_components/chstides/manifest.json` | Add `chstides==0.3.2` to requirements |
| `custom_components/chstides/const.py` | Remove `CHS_API_BASE`; change `TIME_SERIES_PREDICTED` to `"wlp-hilo"` |
| `custom_components/chstides/api.py` | Add `_SessionCHSIWLS`; add 3 module-level functions; remove `CHSApiClient`, `find_highs_lows`; update `PredictionPoint` type annotation |
| `custom_components/chstides/coordinator.py` | Store `session` instead of `client`; call module-level functions |
| `custom_components/chstides/__init__.py` | Remove `CHSApiClient`; pass `session` into coordinators |
| `custom_components/chstides/config_flow.py` | Import and call `get_stations` directly |
| `tests/test_api.py` | New tests for `_SessionCHSIWLS` and 3 functions; remove `CHSApiClient` / `find_highs_lows` tests |
| `tests/test_coordinator.py` | Mock module-level functions instead of `mock_client` |
| `tests/test_config_flow.py` | Patch `get_stations` instead of `CHSApiClient` |

---

## Task 1: Update manifest.json and const.py

**Files:**
- Modify: `custom_components/chstides/manifest.json`
- Modify: `custom_components/chstides/const.py`

No tests needed — these are constants and metadata.

- [ ] **Step 1: Update manifest.json**

Replace the `requirements` array:

```json
{
  "domain": "chstides",
  "name": "CHSTides",
  "version": "0.1.0",
  "documentation": "https://github.com/placeholder/chstides",
  "iot_class": "cloud_polling",
  "config_flow": true,
  "codeowners": [],
  "requirements": ["chstides==0.3.2"]
}
```

- [ ] **Step 2: Update const.py**

Remove `CHS_API_BASE` and change `TIME_SERIES_PREDICTED`:

```python
DOMAIN = "chstides"

TIME_SERIES_OBSERVED = "wlo"
TIME_SERIES_PREDICTED = "wlp-hilo"

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

- [ ] **Step 3: Commit**

```bash
git add custom_components/chstides/manifest.json custom_components/chstides/const.py
git commit -m "chore: add chstides==0.3.2 requirement, update wlp-hilo constant"
```

---

## Task 2: Add `_SessionCHSIWLS` to api.py

**Files:**
- Modify: `custom_components/chstides/api.py` (add class, keep existing code)
- Modify: `tests/test_api.py` (add new tests)

`_SessionCHSIWLS` is a `pychs.CHS_IWLS` subclass that:
1. Overrides `_async_get_data` to use an injected `aiohttp.ClientSession` and raise `CHSApiError` on HTTP >= 400
2. Overrides `_set_station_data` as a no-op — we don't use library-managed state, and this prevents an `IndexError` crash when `stations()` is called with a code that returns empty results

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py` (after existing imports, add `re`; keep all existing tests intact):

```python
import re

from custom_components.chstides.api import _SessionCHSIWLS
```

Then add these test functions:

```python
@pytest.mark.asyncio
async def test_session_chs_iwls_raises_on_http_error(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        client = _SessionCHSIWLS(session)
        with pytest.raises(CHSApiError) as exc_info:
            await client._async_get_data(
                "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations"
            )
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_session_chs_iwls_returns_json(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        payload=[{"id": "s001"}],
    )
    async with aiohttp.ClientSession() as session:
        client = _SessionCHSIWLS(session)
        data = await client._async_get_data(
            "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations"
        )
    assert data == [{"id": "s001"}]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_api.py::test_session_chs_iwls_raises_on_http_error tests/test_api.py::test_session_chs_iwls_returns_json -v
```

Expected: `ImportError` or `FAILED` — `_SessionCHSIWLS` does not exist yet.

- [ ] **Step 3: Add `_SessionCHSIWLS` to api.py**

At the top of `custom_components/chstides/api.py`, add the import:

```python
from pychs import CHS_IWLS
```

Then add the class after the existing imports, before `TidePhase`:

```python
class _SessionCHSIWLS(CHS_IWLS):
    """CHS_IWLS subclass that uses an injected aiohttp session."""

    def __init__(self, session: aiohttp.ClientSession, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._ha_session = session

    async def _async_get_data(self, url: str) -> Any:
        async with self._ha_session.get(url) as resp:
            if resp.status >= 400:
                raise CHSApiError(f"CHS API returned {resp.status}", resp.status)
            return await resp.json()

    async def _set_station_data(self, data: dict) -> None:
        pass  # We create fresh instances per call; discard library-managed state.
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_api.py::test_session_chs_iwls_raises_on_http_error tests/test_api.py::test_session_chs_iwls_returns_json -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add _SessionCHSIWLS with injected session and error handling"
```

---

## Task 3: Add `get_stations` function

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
from custom_components.chstides.api import get_stations
```

Add at end of test file:

```python
@pytest.mark.asyncio
async def test_get_stations_returns_all_stations(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
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
        stations = await get_stations(session)
    assert len(stations) == 1
    assert stations[0].code == "03580"
    assert stations[0].name == "Quebec City"


@pytest.mark.asyncio
async def test_get_stations_with_code_filter(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations\?code=03580"),
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
        stations = await get_stations(session, code="03580")
    assert stations[0].code == "03580"


@pytest.mark.asyncio
async def test_get_stations_empty_returns_empty_list(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations\?code=NOPE"),
        payload=[],
    )
    async with aiohttp.ClientSession() as session:
        stations = await get_stations(session, code="NOPE")
    assert stations == []


@pytest.mark.asyncio
async def test_get_stations_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        status=500,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError) as exc_info:
            await get_stations(session)
    assert exc_info.value.status_code == 500
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_api.py::test_get_stations_returns_all_stations tests/test_api.py::test_get_stations_with_code_filter tests/test_api.py::test_get_stations_empty_returns_empty_list tests/test_api.py::test_get_stations_raises_on_error -v
```

Expected: `ImportError` or `FAILED`.

- [ ] **Step 3: Add `get_stations` to api.py**

Add after `_SessionCHSIWLS`, before `TidePhase`:

```python
async def get_stations(
    session: aiohttp.ClientSession, code: str | None = None
) -> list[Station]:
    """Return all stations, or those matching station code."""
    chs = _SessionCHSIWLS(session, station_code=code)
    data = await chs.stations()
    if not isinstance(data, list):
        return []
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_api.py::test_get_stations_returns_all_stations tests/test_api.py::test_get_stations_with_code_filter tests/test_api.py::test_get_stations_empty_returns_empty_list tests/test_api.py::test_get_stations_raises_on_error -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add get_stations module-level function"
```

---

## Task 4: Add `get_observed_water_level` function

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

**Note on datetime formatting:** The library's `_validate_query_parameters` calls `datetime.isoformat()[:-7] + "Z"` to format dates. This only works correctly when the datetime has non-zero microseconds (e.g. a naive `datetime.now()` result). Pass naive UTC datetimes — `datetime.now(UTC).replace(tzinfo=None)` — which always have microseconds from the system clock.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
from custom_components.chstides.api import get_observed_water_level
```

Add at end of file:

```python
@pytest.mark.asyncio
async def test_get_observed_water_level_returns_observed_data(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlo"
        ),
        payload=[
            {"eventDate": "2026-04-07T12:00:00Z", "value": 1.42, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T12:05:00Z", "value": 1.50, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_observed_water_level(session, "s001")
    assert len(points) == 2
    assert points[0].height_m == 1.42
    assert points[1].height_m == 1.50
    assert points[0].station_id == "s001"
    assert points[0].time_series_code == "wlo"


@pytest.mark.asyncio
async def test_get_observed_water_level_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_observed_water_level(session, "s001")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_api.py::test_get_observed_water_level_returns_observed_data tests/test_api.py::test_get_observed_water_level_raises_on_error -v
```

Expected: `ImportError` or `FAILED`.

- [ ] **Step 3: Add `get_observed_water_level` to api.py**

Add after `get_stations`:

```python
async def get_observed_water_level(
    session: aiohttp.ClientSession, station_id: str
) -> list[ObservedData]:
    """Return the last 30 minutes of observed water level readings."""
    from .const import TIME_SERIES_OBSERVED

    now = datetime.now(UTC).replace(tzinfo=None)
    from_dt = now - timedelta(minutes=30)
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(**{
        "time-series-code": TIME_SERIES_OBSERVED,
        "from": from_dt,
        "to": now,
    })
    return [
        ObservedData(
            station_id=station_id,
            timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
            height_m=float(d["value"]),
            time_series_code=TIME_SERIES_OBSERVED,
        )
        for d in data
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_api.py::test_get_observed_water_level_returns_observed_data tests/test_api.py::test_get_observed_water_level_raises_on_error -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add get_observed_water_level using pychs station_data"
```

---

## Task 5: Add `get_predictions` function

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

This task also:
- Adds the private `_classify_hilo` helper
- Updates `PredictionPoint.type` to remove `"UNKNOWN"` from the `Literal`

The `wlp-hilo` time series returns pre-identified HIGH/LOW turning-point events. They arrive in chronological order, strictly alternating. `_classify_hilo` labels each by comparing height to its neighbor.

**Note on midnight datetime:** `today` is built with `microsecond=1` to satisfy the library's `isoformat()[:-7]` formatting (which requires a microseconds component to strip).

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
from custom_components.chstides.api import get_predictions
```

Add at end of file:

```python
@pytest.mark.asyncio
async def test_get_predictions_classifies_high_low(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlp-hilo"
        ),
        payload=[
            {"eventDate": "2026-04-08T06:00:00Z", "value": 3.1, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T12:00:00Z", "value": 0.4, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T18:00:00Z", "value": 2.9, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert len(points) == 3
    assert points[0].type == "HIGH"
    assert points[0].height_m == 3.1
    assert points[1].type == "LOW"
    assert points[1].height_m == 0.4
    assert points[2].type == "HIGH"
    assert points[2].height_m == 2.9


@pytest.mark.asyncio
async def test_get_predictions_single_event_defaults_high(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        payload=[
            {"eventDate": "2026-04-08T06:00:00Z", "value": 3.1, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert len(points) == 1
    assert points[0].type == "HIGH"


@pytest.mark.asyncio
async def test_get_predictions_empty_returns_empty(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        payload=[],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert points == []


@pytest.mark.asyncio
async def test_get_predictions_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=500,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_predictions(session, "s001", days=1)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_api.py::test_get_predictions_classifies_high_low tests/test_api.py::test_get_predictions_single_event_defaults_high tests/test_api.py::test_get_predictions_empty_returns_empty tests/test_api.py::test_get_predictions_raises_on_error -v
```

Expected: `ImportError` or `FAILED`.

- [ ] **Step 3: Update `PredictionPoint` type annotation in api.py**

Change:
```python
type: Literal["HIGH", "LOW", "UNKNOWN"]
```
to:
```python
type: Literal["HIGH", "LOW"]
```

- [ ] **Step 4: Add `_classify_hilo` and `get_predictions` to api.py**

Add `_classify_hilo` after the existing `find_highs_lows` function (still present for now):

```python
def _classify_hilo(points: list[PredictionPoint]) -> list[PredictionPoint]:
    """Label wlp-hilo events HIGH or LOW by comparing adjacent heights."""
    if not points:
        return []
    if len(points) == 1:
        return [PredictionPoint(points[0].timestamp, points[0].height_m, "HIGH")]
    result = []
    for i, p in enumerate(points):
        if i < len(points) - 1:
            tide_type: Literal["HIGH", "LOW"] = (
                "HIGH" if p.height_m > points[i + 1].height_m else "LOW"
            )
        else:
            tide_type = "HIGH" if p.height_m > points[i - 1].height_m else "LOW"
        result.append(PredictionPoint(p.timestamp, p.height_m, tide_type))
    return result
```

Add `get_predictions` after `get_observed_water_level`:

```python
async def get_predictions(
    session: aiohttp.ClientSession, station_id: str, days: int
) -> list[PredictionPoint]:
    """Return HIGH/LOW tide events for the next N days using wlp-hilo."""
    from .const import TIME_SERIES_PREDICTED

    # microsecond=1 ensures the library's isoformat()[:-7] strips correctly
    today = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=1, tzinfo=None
    )
    to_dt = today + timedelta(days=days, hours=23, minutes=59, seconds=59)
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(**{
        "time-series-code": TIME_SERIES_PREDICTED,
        "from": today,
        "to": to_dt,
    })
    raw = [
        PredictionPoint(
            timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
            height_m=float(d["value"]),
            type="HIGH",
        )
        for d in data
    ]
    return _classify_hilo(raw)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_api.py::test_get_predictions_classifies_high_low tests/test_api.py::test_get_predictions_single_event_defaults_high tests/test_api.py::test_get_predictions_empty_returns_empty tests/test_api.py::test_get_predictions_raises_on_error -v
```

Expected: all PASS.

- [ ] **Step 6: Run the full test suite to confirm nothing broken**

```bash
python3 -m pytest tests/ -v
```

Expected: all existing tests still pass alongside new ones.

- [ ] **Step 7: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add get_predictions with wlp-hilo and _classify_hilo"
```

---

## Task 6: Remove `CHSApiClient`, `find_highs_lows`, and old tests

**Files:**
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

Remove the old code now that the new functions are in place. The coordinator and config_flow still reference `CHSApiClient` — those will break and be fixed in Tasks 7–9.

- [ ] **Step 1: Delete `CHSApiClient` and `find_highs_lows` from api.py**

Remove the entire `CHSApiClient` class (lines 67–174 in the original file — everything from `class CHSApiClient:` through the end of `get_predictions`).

Remove the `find_highs_lows` function.

Remove the `_classify_hilo` function's import of `Literal` if it was only used for `"UNKNOWN"` — double-check `Literal` is still imported (it's used by `PredictionPoint.type`).

Also remove the import of `math` if it was only used by `find_highs_lows`. Check: `math` was used only inside `find_nearest_station` (via `math.radians`, `math.sin`, etc.) — keep it.

The final `api.py` imports section should look like:

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import aiohttp
from pychs import CHS_IWLS
```

- [ ] **Step 2: Remove old tests from test_api.py**

Delete these test functions (they cover removed code):
- `test_find_highs_lows_identifies_single_peak_and_valley`
- `test_find_highs_lows_empty_for_short_series`
- `test_find_highs_lows_flat_series_returns_empty`
- `test_get_stations_returns_stations` (the old one mocking `CHS_API_BASE`)
- `test_get_stations_with_code_filter` (old one)
- `test_get_stations_raises_on_error` (old one)
- `test_get_observed_water_level` (old one)
- `test_get_predictions_returns_highs_lows` (old one)

Also remove:
```python
from custom_components.chstides.api import (
    ...
    CHSApiClient,
    ...
    find_highs_lows,
    ...
)
from custom_components.chstides.const import CHS_API_BASE
```

Replace with the imports already added in Tasks 2–5. The final import block at the top of `test_api.py` should be:

```python
import re
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    Station,
    TidePhase,
    _SessionCHSIWLS,
    derive_tide_phase,
    find_nearest_station,
    get_observed_water_level,
    get_predictions,
    get_stations,
)
```

- [ ] **Step 3: Run the api tests to confirm they pass**

```bash
python3 -m pytest tests/test_api.py -v
```

Expected: all PASS. (Coordinator/config_flow tests will fail — fix next.)

- [ ] **Step 4: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "refactor: remove CHSApiClient and find_highs_lows, clean up old tests"
```

---

## Task 7: Update coordinator.py and test_coordinator.py

**Files:**
- Modify: `custom_components/chstides/coordinator.py`
- Modify: `tests/test_coordinator.py`

Coordinators store `session` instead of `client` and call module-level functions.

- [ ] **Step 1: Rewrite coordinator.py**

```python
"""DataUpdateCoordinators for observed water level and tide predictions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import aiohttp

from .api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
    derive_tide_phase,
    get_observed_water_level,
    get_predictions,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ObservedDataCoordinator(DataUpdateCoordinator):
    """Polls observed water level (wlo) on a short interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        station_id: str,
        interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_observed_{station_id}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._session = session
        self._station_id = station_id
        self.latest: ObservedData | None = None
        self.phase: str = TidePhase.RISING

    async def _async_update_data(self) -> dict:
        try:
            points = await get_observed_water_level(self._session, self._station_id)
        except CHSApiError as err:
            raise UpdateFailed(f"CHS API error: {err}") from err
        if not points:
            raise UpdateFailed("No observed data returned from CHS API")
        self.latest = points[-1]
        self.phase = derive_tide_phase(points)
        return {"latest": self.latest, "phase": self.phase}


class PredictionCoordinator(DataUpdateCoordinator):
    """Polls tide predictions (wlp-hilo) daily and caches stale data on failure."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
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
        self._session = session
        self._station_id = station_id
        self._days = days
        self.forecast: list[PredictionPoint] = []
        self.next_high: PredictionPoint | None = None
        self.next_low: PredictionPoint | None = None

    async def _async_update_data(self) -> dict:
        try:
            points = await get_predictions(self._session, self._station_id, self._days)
        except CHSApiError as err:
            _LOGGER.warning("Failed to fetch predictions, keeping stale data: %s", err)
            return {
                "forecast": self.forecast,
                "next_high": self.next_high,
                "next_low": self.next_low,
            }

        now = datetime.now(UTC)
        self.forecast = points
        future = [p for p in points if p.timestamp > now]
        self.next_high = next((p for p in future if p.type == "HIGH"), None)
        self.next_low = next((p for p in future if p.type == "LOW"), None)
        return {
            "forecast": self.forecast,
            "next_high": self.next_high,
            "next_low": self.next_low,
        }
```

- [ ] **Step 2: Rewrite test_coordinator.py**

```python
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
)
from custom_components.chstides.coordinator import (
    ObservedDataCoordinator,
    PredictionCoordinator,
)


@pytest.fixture
def hass(hass):
    return hass


@pytest.fixture
def mock_session():
    return AsyncMock(spec=aiohttp.ClientSession)


@pytest.fixture
def now():
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_observed_coordinator_stores_latest_and_phase(hass, mock_session, now):
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(
            return_value=[
                ObservedData("s1", now, 1.0, "wlo"),
                ObservedData("s1", now, 1.5, "wlo"),
            ]
        ),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        await coord.async_refresh()

    assert coord.latest.height_m == 1.5
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_api_error(hass, mock_session):
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(side_effect=CHSApiError("timeout", None)),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_empty_data(hass, mock_session):
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(return_value=[]),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_prediction_coordinator_sets_next_high_and_low(hass, mock_session, now):
    future_high = datetime(2026, 4, 8, 14, 30, tzinfo=UTC)
    future_low = datetime(2026, 4, 8, 20, 0, tzinfo=UTC)
    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=AsyncMock(
            return_value=[
                PredictionPoint(future_high, 3.1, "HIGH"),
                PredictionPoint(future_low, 0.4, "LOW"),
            ]
        ),
    ):
        coord = PredictionCoordinator(hass, mock_session, "s1", 7, 24)
        await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
    assert coord.next_low.height_m == 0.4
    assert len(coord.forecast) == 2


@pytest.mark.asyncio
async def test_prediction_coordinator_keeps_stale_on_error(hass, mock_session, now):
    future = datetime(2026, 4, 8, 14, 30, tzinfo=UTC)
    first_call = AsyncMock(return_value=[PredictionPoint(future, 3.1, "HIGH")])
    second_call = AsyncMock(side_effect=CHSApiError("timeout", None))

    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=first_call,
    ):
        coord = PredictionCoordinator(hass, mock_session, "s1", 7, 24)
        await coord.async_refresh()

    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=second_call,
    ):
        await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
```

- [ ] **Step 3: Run coordinator tests**

```bash
python3 -m pytest tests/test_coordinator.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add custom_components/chstides/coordinator.py tests/test_coordinator.py
git commit -m "refactor: coordinator stores session, calls module-level api functions"
```

---

## Task 8: Update `__init__.py`

**Files:**
- Modify: `custom_components/chstides/__init__.py`

- [ ] **Step 1: Rewrite __init__.py**

```python
"""CHSTides — Canadian Hydrographic Service tide data for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    station_id = entry.data[CONF_STATION_ID]

    def _opt(key: str, default: int) -> int:
        return entry.options.get(key, entry.data.get(key, default))

    observed_coord = ObservedDataCoordinator(
        hass,
        session,
        station_id,
        _opt(CONF_OBSERVED_INTERVAL, DEFAULT_OBSERVED_INTERVAL_MINUTES),
    )
    prediction_coord = PredictionCoordinator(
        hass,
        session,
        station_id,
        _opt(CONF_PREDICTION_DAYS, DEFAULT_PREDICTION_DAYS),
        _opt(CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL_HOURS),
    )

    await observed_coord.async_config_entry_first_refresh()
    await prediction_coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "observed": observed_coord,
        "predictions": prediction_coord,
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

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass except `test_config_flow.py` (fixed next).

- [ ] **Step 3: Commit**

```bash
git add custom_components/chstides/__init__.py
git commit -m "refactor: __init__ passes session to coordinators, removes CHSApiClient"
```

---

## Task 9: Update config_flow.py and test_config_flow.py

**Files:**
- Modify: `custom_components/chstides/config_flow.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Update imports and call sites in config_flow.py**

Replace the import:
```python
from .api import CHSApiClient, CHSApiError, find_nearest_station
```
with:
```python
from .api import CHSApiError, find_nearest_station, get_stations
```

In `async_step_station`, replace all occurrences of:
```python
session = async_get_clientsession(self.hass)
client = CHSApiClient(session)
```
with:
```python
session = async_get_clientsession(self.hass)
```

Replace:
```python
stations = await client.get_stations()
```
with:
```python
stations = await get_stations(session)
```

Replace:
```python
stations = await client.get_stations(code=code)
```
with:
```python
stations = await get_stations(session, code=code)
```

The final `async_step_station` method should look like:

```python
async def async_step_station(self, user_input: dict[str, Any] | None = None) -> Any:
    errors: dict[str, str] = {}
    session = async_get_clientsession(self.hass)

    if user_input is not None:
        if user_input.get("auto_detect"):
            try:
                stations = await get_stations(session)
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
                            vol.Optional(
                                "station_code", default=nearest.code
                            ): TextSelector(),
                            vol.Optional(
                                "auto_detect", default=False
                            ): BooleanSelector(),
                        }
                    ),
                    description_placeholders={
                        "nearest_station": self._nearest_hint
                    },
                )
            except CHSApiError:
                errors["base"] = "cannot_connect"
        else:
            code = user_input.get("station_code", "").strip()
            if not code:
                errors["station_code"] = "station_not_found"
            else:
                try:
                    stations = await get_stations(session, code=code)
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
```

- [ ] **Step 2: Update test_config_flow.py**

Replace the `mock_client_setup` fixture and update tests that reference it:

```python
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.chstides.api import Station
from custom_components.chstides.const import DOMAIN

MOCK_STATION = Station(
    id="s001", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22
)


@pytest.fixture(autouse=True)
def mock_get_stations():
    with patch("custom_components.chstides.config_flow.get_stations") as mock_fn:
        mock_fn.return_value = [MOCK_STATION]
        yield mock_fn


@pytest.mark.asyncio
async def test_step_station_shows_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"


@pytest.mark.asyncio
async def test_step_station_with_valid_code_proceeds(
    hass: HomeAssistant, mock_get_stations
):
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
async def test_step_station_with_invalid_code_shows_error(
    hass: HomeAssistant, mock_get_stations
):
    mock_get_stations.return_value = []
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
async def test_step_station_auto_detect_prefills_nearest(
    hass: HomeAssistant, mock_get_stations
):
    hass.config.latitude = 46.8
    hass.config.longitude = -71.2
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "", "auto_detect": True},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"
    assert (
        result["description_placeholders"]["nearest_station"] == "Quebec City (03580)"
    )
```

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Run linter**

```bash
scripts/lint
```

Fix any issues reported.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chstides/config_flow.py tests/test_config_flow.py
git commit -m "refactor: config_flow calls get_stations directly, removes CHSApiClient"
```

---

## Final Verification

- [ ] Run full test suite one more time: `python3 -m pytest tests/ -v`
- [ ] Confirm `CHSApiClient` no longer appears anywhere: `grep -r "CHSApiClient" custom_components/ tests/`
- [ ] Confirm `find_highs_lows` no longer appears anywhere: `grep -r "find_highs_lows" custom_components/ tests/`
- [ ] Confirm `CHS_API_BASE` no longer appears anywhere: `grep -r "CHS_API_BASE" custom_components/ tests/`
- [ ] Confirm `api-sine` no longer appears anywhere: `grep -r "api-sine" custom_components/ tests/`
