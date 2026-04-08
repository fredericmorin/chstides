# wlp Fallback + Water Level Source Sensor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fall back to `wlp` (continuous predicted water level) when a station has no live `wlo` sensor, and expose a new sensor indicating whether the current reading is measured or estimated.

**Architecture:** Add a `source` field to `ObservedData` so the data is self-describing. `get_observed_water_level` sets `source="measured"`; a new `get_predicted_water_level` sets `source="estimated"`. The coordinator catches 404 from `wlo` and calls the new function instead. A new `WaterLevelSourceSensor` reads `coordinator.latest.source` directly — no changes to existing sensors.

**Tech Stack:** Python, aiohttp, pytest, pytest-homeassistant-custom-component, aioresponses

---

## File Map

| File | Change |
|---|---|
| `custom_components/chstides/const.py` | Add `TIME_SERIES_PREDICTED_CONTINUOUS = "wlp"` |
| `custom_components/chstides/api.py` | Add `source` field to `ObservedData`; add `get_predicted_water_level` |
| `custom_components/chstides/coordinator.py` | Fallback logic + `_fetch_predicted_fallback` helper; import new api fn |
| `custom_components/chstides/sensor.py` | Add `WaterLevelSourceSensor`; register in `async_setup_entry` |
| `tests/test_api.py` | Assert `source="measured"` on existing test; add `get_predicted_water_level` tests |
| `tests/test_coordinator.py` | Add 404-fallback tests |
| `tests/test_sensor.py` | Add `WaterLevelSourceSensor` tests |

---

## Task 1: Add `source` field to `ObservedData`

**Files:**
- Modify: `custom_components/chstides/api.py:37-42`
- Modify: `tests/test_api.py:172-189`

- [ ] **Step 1: Add `source` field to the dataclass**

In `custom_components/chstides/api.py`, replace the `ObservedData` dataclass:

```python
@dataclass
class ObservedData:
    station_id: str
    timestamp: datetime
    height_m: float
    time_series_code: str
    source: Literal["measured", "estimated"] = "measured"
```

(`Literal` is already imported from `typing` in this file.)

- [ ] **Step 2: Assert `source` on existing `get_observed_water_level` test**

In `tests/test_api.py`, in `test_get_observed_water_level_returns_observed_data`, add two assertions after the existing ones:

```python
    assert points[0].source == "measured"
    assert points[1].source == "measured"
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

```bash
python3 -m pytest tests/ -v
```

Expected: all existing tests pass (default value means no constructor calls break).

- [ ] **Step 4: Commit**

```bash
git add custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add source field to ObservedData"
```

---

## Task 2: Add `TIME_SERIES_PREDICTED_CONTINUOUS` constant and `get_predicted_water_level`

**Files:**
- Modify: `custom_components/chstides/const.py`
- Modify: `custom_components/chstides/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py`, add after the existing imports (add `get_predicted_water_level` to the import block from `custom_components.chstides.api`):

```python
from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    Station,
    TidePhase,
    _SessionCHSIWLS,
    derive_tide_phase,
    find_nearest_station,
    get_observed_water_level,
    get_predicted_water_level,
    get_predictions,
    get_stations,
)
```

Then add these tests at the bottom of the file:

```python
@pytest.mark.asyncio
async def test_get_predicted_water_level_returns_estimated_data(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlp"
        ),
        payload=[
            {"eventDate": "2026-04-08T12:00:00Z", "value": 1.80, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T12:15:00Z", "value": 1.85, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predicted_water_level(session, "s001")
    assert len(points) == 2
    assert points[0].height_m == 1.80
    assert points[1].height_m == 1.85
    assert points[0].source == "estimated"
    assert points[1].source == "estimated"
    assert points[0].time_series_code == "wlp"
    assert points[0].station_id == "s001"


@pytest.mark.asyncio
async def test_get_predicted_water_level_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_predicted_water_level(session, "s001")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_api.py::test_get_predicted_water_level_returns_estimated_data tests/test_api.py::test_get_predicted_water_level_raises_on_error -v
```

Expected: `ImportError` or `AttributeError` — `get_predicted_water_level` does not exist yet.

- [ ] **Step 3: Add the constant**

In `custom_components/chstides/const.py`, add after `TIME_SERIES_PREDICTED`:

```python
TIME_SERIES_PREDICTED_CONTINUOUS = "wlp"
```

- [ ] **Step 4: Add `get_predicted_water_level` to `api.py`**

In `custom_components/chstides/api.py`, add this function after `get_observed_water_level`:

```python
async def get_predicted_water_level(
    session: aiohttp.ClientSession, station_id: str
) -> list[ObservedData]:
    """Return ~30 min of wlp predictions around now as ObservedData with source='estimated'."""
    from .const import TIME_SERIES_PREDICTED_CONTINUOUS

    now = datetime.now(UTC).replace(tzinfo=None)
    from_dt = now - timedelta(minutes=30)
    to_dt = now + timedelta(minutes=30)
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(
        **{
            "time-series-code": TIME_SERIES_PREDICTED_CONTINUOUS,
            "from": from_dt,
            "to": to_dt,
        }
    )
    return [
        ObservedData(
            station_id=station_id,
            timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
            height_m=float(d["value"]),
            time_series_code=TIME_SERIES_PREDICTED_CONTINUOUS,
            source="estimated",
        )
        for d in data
    ]
```

- [ ] **Step 5: Run the new tests to verify they pass**

```bash
python3 -m pytest tests/test_api.py::test_get_predicted_water_level_returns_estimated_data tests/test_api.py::test_get_predicted_water_level_raises_on_error -v
```

Expected: both PASS.

- [ ] **Step 6: Run full suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add custom_components/chstides/const.py custom_components/chstides/api.py tests/test_api.py
git commit -m "feat: add get_predicted_water_level with wlp time series"
```

---

## Task 3: Coordinator fallback logic

**Files:**
- Modify: `custom_components/chstides/coordinator.py`
- Modify: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_coordinator.py`, add `get_predicted_water_level` to the api imports:

```python
from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
)
```

Then add these tests at the bottom of the file:

```python
@pytest.mark.asyncio
async def test_observed_coordinator_falls_back_to_wlp_on_404(hass, mock_session, now):
    predicted_points = [
        ObservedData("s1", now, 1.8, "wlp", source="estimated"),
        ObservedData("s1", now, 1.85, "wlp", source="estimated"),
    ]
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(side_effect=CHSApiError("not found", 404)),
    ), patch(
        "custom_components.chstides.coordinator.get_predicted_water_level",
        new=AsyncMock(return_value=predicted_points),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        await coord.async_refresh()

    assert coord.latest.height_m == 1.85
    assert coord.latest.source == "estimated"
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_returns_none_when_wlp_also_fails(
    hass, mock_session
):
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(side_effect=CHSApiError("not found", 404)),
    ), patch(
        "custom_components.chstides.coordinator.get_predicted_water_level",
        new=AsyncMock(side_effect=CHSApiError("wlp error", 500)),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        result = await coord._async_update_data()

    assert result["latest"] is None


@pytest.mark.asyncio
async def test_observed_coordinator_returns_none_when_wlp_empty(hass, mock_session):
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(side_effect=CHSApiError("not found", 404)),
    ), patch(
        "custom_components.chstides.coordinator.get_predicted_water_level",
        new=AsyncMock(return_value=[]),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        result = await coord._async_update_data()

    assert result["latest"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_coordinator.py::test_observed_coordinator_falls_back_to_wlp_on_404 tests/test_coordinator.py::test_observed_coordinator_returns_none_when_wlp_also_fails tests/test_coordinator.py::test_observed_coordinator_returns_none_when_wlp_empty -v
```

Expected: FAIL — `get_predicted_water_level` is not imported in coordinator yet.

- [ ] **Step 3: Update coordinator imports and implement fallback**

In `custom_components/chstides/coordinator.py`, update the api import block to add `get_predicted_water_level`:

```python
from .api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
    derive_tide_phase,
    get_observed_water_level,
    get_predicted_water_level,
    get_predictions,
)
```

Then replace `_async_update_data` in `ObservedDataCoordinator` with:

```python
async def _async_update_data(self) -> dict:
    try:
        points = await get_observed_water_level(self._session, self._station_id)
    except CHSApiError as err:
        if err.status_code == 404:
            _LOGGER.warning(
                "Station %s has no observed water level data (wlo); "
                "falling back to predicted water level (wlp).",
                self._station_id,
            )
            return await self._fetch_predicted_fallback()
        raise UpdateFailed(f"CHS API error: {err}") from err
    if not points:
        raise UpdateFailed("No observed data returned from CHS API")
    self.latest = points[-1]
    self.phase = derive_tide_phase(points)
    return {"latest": self.latest, "phase": self.phase}

async def _fetch_predicted_fallback(self) -> dict:
    try:
        points = await get_predicted_water_level(self._session, self._station_id)
    except CHSApiError as err:
        _LOGGER.warning(
            "Failed to fetch predicted fallback for station %s: %s",
            self._station_id,
            err,
        )
        return {"latest": None, "phase": self.phase}
    if not points:
        return {"latest": None, "phase": self.phase}
    self.latest = points[-1]
    self.phase = derive_tide_phase(points)
    return {"latest": self.latest, "phase": self.phase}
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
python3 -m pytest tests/test_coordinator.py::test_observed_coordinator_falls_back_to_wlp_on_404 tests/test_coordinator.py::test_observed_coordinator_returns_none_when_wlp_also_fails tests/test_coordinator.py::test_observed_coordinator_returns_none_when_wlp_empty -v
```

Expected: all three PASS.

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add custom_components/chstides/coordinator.py tests/test_coordinator.py
git commit -m "feat: fall back to wlp predictions when wlo returns 404"
```

---

## Task 4: `WaterLevelSourceSensor`

**Files:**
- Modify: `custom_components/chstides/sensor.py`
- Modify: `tests/test_sensor.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_sensor.py`, add `WaterLevelSourceSensor` to the sensor imports:

```python
from custom_components.chstides.sensor import (
    NextHighTideSensor,
    NextLowTideSensor,
    TideForecastSensor,
    TidePhaseSensor,
    WaterLevelSensor,
    WaterLevelSourceSensor,
)
```

Then add these tests at the bottom of the file:

```python
def test_water_level_source_sensor_measured(observed_coord):
    sensor = WaterLevelSourceSensor(
        observed_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.native_value == "measured"


def test_water_level_source_sensor_estimated(observed_coord):
    observed_coord.latest = ObservedData(
        station_id="s001",
        timestamp=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        height_m=1.80,
        time_series_code="wlp",
        source="estimated",
    )
    sensor = WaterLevelSourceSensor(
        observed_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.native_value == "estimated"


def test_water_level_source_sensor_none_when_no_data(observed_coord):
    observed_coord.latest = None
    sensor = WaterLevelSourceSensor(
        observed_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.native_value is None


def test_water_level_source_sensor_unique_id(observed_coord):
    sensor = WaterLevelSourceSensor(
        observed_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.unique_id == "entry1_water_level_source"


def test_water_level_source_sensor_name(observed_coord):
    sensor = WaterLevelSourceSensor(
        observed_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.name == "Quebec City Water Level Source"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_sensor.py::test_water_level_source_sensor_measured tests/test_sensor.py::test_water_level_source_sensor_estimated tests/test_sensor.py::test_water_level_source_sensor_none_when_no_data tests/test_sensor.py::test_water_level_source_sensor_unique_id tests/test_sensor.py::test_water_level_source_sensor_name -v
```

Expected: `ImportError` — `WaterLevelSourceSensor` does not exist yet.

- [ ] **Step 3: Add `WaterLevelSourceSensor` to `sensor.py`**

In `custom_components/chstides/sensor.py`, add this class after `TidePhaseSensor`:

```python
class WaterLevelSourceSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Indicates whether the current water level reading is measured or estimated."""

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Water Level Source"
        self._attr_unique_id = f"{entry_id}_water_level_source"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.latest is None:
            return None
        return self.coordinator.latest.source
```

- [ ] **Step 4: Register `WaterLevelSourceSensor` in `async_setup_entry`**

In `custom_components/chstides/sensor.py`, in `async_setup_entry`, update `async_add_entities` to include the new sensor:

```python
    async_add_entities(
        [
            WaterLevelSensor(observed, station_name, station_code, station_id, eid),
            TidePhaseSensor(observed, station_name, station_code, station_id, eid),
            WaterLevelSourceSensor(observed, station_name, station_code, station_id, eid),
            NextHighTideSensor(
                predictions, station_name, station_code, station_id, eid
            ),
            NextLowTideSensor(predictions, station_name, station_code, station_id, eid),
            TideForecastSensor(
                predictions, station_name, station_code, station_id, eid
            ),
        ]
    )
```

- [ ] **Step 5: Run the new sensor tests**

```bash
python3 -m pytest tests/test_sensor.py::test_water_level_source_sensor_measured tests/test_sensor.py::test_water_level_source_sensor_estimated tests/test_sensor.py::test_water_level_source_sensor_none_when_no_data tests/test_sensor.py::test_water_level_source_sensor_unique_id tests/test_sensor.py::test_water_level_source_sensor_name -v
```

Expected: all five PASS.

- [ ] **Step 6: Run full suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add custom_components/chstides/sensor.py tests/test_sensor.py
git commit -m "feat: add WaterLevelSourceSensor showing measured vs estimated"
```
