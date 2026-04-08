# Design: `wlp` Fallback for Stations Without Live Measurements

**Date:** 2026-04-08  
**Status:** Approved

## Problem

Some CHS stations have no live sensor and return HTTP 404 for the `wlo` (observed water level) time series. Currently the coordinator logs a warning and leaves the water level sensors unavailable. Users have no tide height data and no way to tell whether a reading is real or estimated.

## Solution

Fall back to `wlp` (continuous predicted water level, 15-min intervals) when `wlo` returns 404. Expose a new sensor that tells the user whether the current reading is measured or estimated.

## Design

### 1. Constants (`const.py`)

Add:

```python
TIME_SERIES_PREDICTED_CONTINUOUS = "wlp"
```

### 2. Data Model (`api.py`)

Add a `source` field to `ObservedData`:

```python
@dataclass
class ObservedData:
    station_id: str
    timestamp: datetime
    height_m: float
    time_series_code: str
    source: Literal["measured", "estimated"] = "measured"
```

`get_observed_water_level` sets `source="measured"` on every point (default, no change required at call sites).

New function:

```python
async def get_predicted_water_level(
    session: aiohttp.ClientSession, station_id: str
) -> list[ObservedData]:
    """Return ~30 min of wlp predictions around now as ObservedData with source='estimated'."""
```

Fetches `wlp` for a ±30-minute window around now. Returns the same `list[ObservedData]` shape so all downstream consumers work unchanged.

### 3. Coordinator (`coordinator.py`)

In `ObservedDataCoordinator._async_update_data`:

- On 404 from `get_observed_water_level`, call `get_predicted_water_level` instead.
- Log a `warning` on the first fallback so the user knows the station has no live sensor.
- If the fallback also fails or returns nothing, return `latest=None` (existing behaviour).
- Phase derivation (`derive_tide_phase`) works unchanged — it only needs multiple `ObservedData` points regardless of source.

### 4. New Sensor (`sensor.py`)

`WaterLevelSourceSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity)`:

| Property | Value |
|---|---|
| Name | `"{station_name} Water Level Source"` |
| Unique ID | `{entry_id}_water_level_source` |
| State | `"measured"` / `"estimated"` / `None` when no data |
| Extra attributes | none |
| Device | same `_device_info` as other observed sensors |

Added to `async_setup_entry` alongside the five existing sensors.

## Data Flow

```
API call → wlo (404?) ──yes──► wlp fetch → ObservedData(source="estimated")
                    │
                    no
                    ▼
             ObservedData(source="measured")
                    │
                    ▼
          ObservedDataCoordinator.latest
          ├── WaterLevelSensor        → height_m
          ├── TidePhaseSensor         → phase
          └── WaterLevelSourceSensor  → source ("measured"/"estimated")
```

## Error Handling

| Scenario | Behaviour |
|---|---|
| `wlo` 404 | Fall back to `wlp`, log warning |
| `wlp` also fails | `latest=None`, sensors unavailable |
| `wlo` returns empty list | `UpdateFailed` (existing behaviour, unchanged) |

## Testing

- Unit test `get_predicted_water_level` with mocked `aioresponses` returning `wlp` data → verify `source="estimated"` on returned points.
- Unit test coordinator fallback: mock `wlo` 404 → coordinator calls `wlp` → `latest.source == "estimated"`.
- Unit test `WaterLevelSourceSensor.native_value` returns `"measured"` / `"estimated"` / `None`.
- Existing tests for `get_observed_water_level` and coordinator 404 path updated to set `source="measured"` where needed.

## Files Changed

| File | Change |
|---|---|
| `custom_components/chstides/const.py` | Add `TIME_SERIES_PREDICTED_CONTINUOUS` |
| `custom_components/chstides/api.py` | Add `source` to `ObservedData`; add `get_predicted_water_level` |
| `custom_components/chstides/coordinator.py` | Fallback logic in `ObservedDataCoordinator` |
| `custom_components/chstides/sensor.py` | Add `WaterLevelSourceSensor`; register in `async_setup_entry` |
| `tests/` | New and updated tests |
