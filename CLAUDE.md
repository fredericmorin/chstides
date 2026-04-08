# CHSTides — Dev Notes

## Project
Home Assistant custom integration for Canadian Hydrographic Service tide data.
Distributed via HACS. API: https://api-sine.dfo-mpo.gc.ca

## Dev Commands
- `scripts/setup` — install all dependencies
- `scripts/develop` — start local HA instance with integration loaded (config in `config/`)
- `scripts/lint` — ruff format + check
- `python3 -m pytest tests/ -v` — run pytest suite

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

## README
README.md documents features, stack, content workflow, Makefile targets, and output naming. It must be kept in sync with the code — update it in the same commit as the feature change.

## Git
- Feature branches: `claude/<description>-<id>`
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, etc.)
