# Design: Migrate to `chstides` 0.3.2 Library

**Date:** 2026-04-08  
**Status:** Approved

## Summary

Replace the hand-rolled `CHSApiClient` (direct `aiohttp` calls to `api-sine.dfo-mpo.gc.ca`) with the `chstides` 0.3.2 PyPI library (`pychs.CHS_IWLS`), injecting the HA-shared session so the integration stays idiomatic. The public interface shrinks to module-level functions; `CHSApiClient` is deleted. Predictions switch from `wlp` + local peak-detection to the `wlp-hilo` time series (API-native HIGH/LOW events).

## Architecture

```
coordinator.py / config_flow.py
        │  (calls module-level functions; no client object)
        ▼
api.py — async functions: get_stations, get_observed_water_level, get_predictions
        │
        ▼
_SessionCHSIWLS   (private; pychs.CHS_IWLS subclass; overrides _async_get_data)
        │
        ▼
pychs.CHS_IWLS    (URL construction, param validation, endpoint constants)
        │
        ▼
aiohttp.ClientSession (HA-shared, injected)
```

All changes are contained in `api.py`, `const.py`, `manifest.json`, and the test files. `coordinator.py`, `sensor.py`, and `config_flow.py` have only minor mechanical updates (swap `self._client.get_x(...)` for `get_x(self._session, ...)`).

## Components

### `_SessionCHSIWLS` (private, `api.py`)

Subclass of `pychs.CHS_IWLS`. Overrides `_async_get_data(url)` to:
- Use the injected `aiohttp.ClientSession` instead of creating a new one per call
- Raise `CHSApiError` on HTTP status >= 400 (the library silently returns `'0'` on non-JSON and has no error detection)

Instantiated per-call inside each public function with the appropriate `station_id` or `station_code`.

### Public API functions (`api.py`)

```python
async def get_stations(session, code=None) -> list[Station]
async def get_observed_water_level(session, station_id) -> list[ObservedData]
async def get_predictions(session, station_id, days) -> list[PredictionPoint]
```

Each function creates a `_SessionCHSIWLS` instance, calls the relevant library method, and maps raw JSON to our data models.

**`get_observed_water_level`:** Calls `station_data(time-series-code='wlo', from=now-30min, to=now)`. Maps `eventDate`/`value` to `ObservedData`.

**`get_predictions`:** Calls `station_data(time-series-code='wlp-hilo', from=today, to=today+days)`. The API returns only HIGH/LOW turning-point events. Classifies each event as HIGH or LOW: if `point.height_m > next.height_m` (or `> prev.height_m` for the last point), label HIGH; otherwise LOW. Single-point result defaults to HIGH. Returns `list[PredictionPoint]` with type always `"HIGH"` or `"LOW"`.

### Data models & helpers (unchanged)

`Station`, `ObservedData`, `PredictionPoint`, `TidePhase`, `CHSApiError`, `derive_tide_phase`, `find_nearest_station` — all kept as-is.

**Removed:** `find_highs_lows` — no longer needed; the API provides HIGH/LOW events directly via `wlp-hilo`.

**`PredictionPoint.type`:** The `"UNKNOWN"` literal is removed from the type annotation; type is always `"HIGH"` or `"LOW"`.

### Caller changes

**`__init__.py`:** Remove `CHSApiClient` instantiation. Pass `session` into both coordinators.

**`coordinator.py`:** Store `self._session` instead of `self._client`. Replace `await self._client.get_x(...)` with `await get_x(self._session, ...)`. Error handling (`CHSApiError`) unchanged.

**`config_flow.py`:** Same one-line swap per call site. `find_nearest_station` import unchanged.

## `const.py`

- Remove `CHS_API_BASE` — the library owns the endpoint (`https://api-iwls.dfo-mpo.gc.ca/api/v1/`)
- Keep `TIME_SERIES_OBSERVED = "wlo"`
- Change `TIME_SERIES_PREDICTED = "wlp"` → `TIME_SERIES_PREDICTED = "wlp-hilo"`

## `manifest.json`

Add `"chstides==0.3.2"` to `requirements`.

## Data flow

```
ObservedDataCoordinator._async_update_data()
  → get_observed_water_level(session, station_id)
      → _SessionCHSIWLS(session, station_id=station_id).station_data(wlo, -30min..now)
      → [ObservedData, ...]
  → derive_tide_phase(points)  [unchanged]

PredictionCoordinator._async_update_data()
  → get_predictions(session, station_id, days)
      → _SessionCHSIWLS(session, station_id=station_id).station_data(wlp-hilo, today..today+days)
      → classify HIGH/LOW by adjacent comparison
      → [PredictionPoint(HIGH|LOW), ...]
  → filter future, find next_high / next_low  [unchanged]
```

## Error handling

`_SessionCHSIWLS._async_get_data` raises `CHSApiError(message, status_code)` on HTTP >= 400. Coordinators catch `CHSApiError` and raise `UpdateFailed` as before. Config flow catches `CHSApiError` and sets `errors["base"] = "cannot_connect"` as before.

## Testing

**`test_api.py`:**
- Mock URL base: `api-sine.dfo-mpo.gc.ca` → `api-iwls.dfo-mpo.gc.ca/api/v1`
- Remove `find_highs_lows` tests
- Add tests for `wlp-hilo` → HIGH/LOW classification
- `_SessionCHSIWLS` tested implicitly through the public function tests

**`test_coordinator.py`, `test_config_flow.py`:** Minimal updates — mock `get_x` functions instead of `CHSApiClient` methods. Session fixture replaces client fixture.

**`test_sensor.py`:** No changes expected.
