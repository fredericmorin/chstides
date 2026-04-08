---
title: Blueprint Alignment Design
date: 2026-04-08
status: approved
---

# CHSTides — Blueprint Alignment

Align the project structure with the [official HA integration blueprint](https://github.com/ludeeus/integration_blueprint).

## Goal

Replace the Docker/Makefile/uv dev setup with the blueprint's pip-based scripts approach. Add CI workflows. No changes to integration logic.

## File Changes

### Add

| File | Purpose |
|------|---------|
| `scripts/develop` | Runs HA via PYTHONPATH trick, no Docker or symlinks needed |
| `scripts/lint` | `ruff format . && ruff check . --fix` |
| `scripts/setup` | `python3 -m pip install --requirement requirements.txt` |
| `config/configuration.yaml` | HA dev config (default_config + debug logger for chstides) |
| `.ruff.toml` | Blueprint ruff config: ALL rules, standard ignores, py314 target |
| `.devcontainer.json` | Blueprint devcontainer: Python 3.14, VSCode extensions |
| `.github/workflows/lint.yml` | CI: ruff check + format on push/PR to main |
| `.github/workflows/validate.yml` | CI: hassfest + HACS validation |
| `requirements.txt` | All deps: homeassistant, colorlog, pip, ruff, pytest, pytest-asyncio, pytest-homeassistant-custom-component, aioresponses, coverage |

### Remove

| File | Reason |
|------|--------|
| `docker-compose.yml` | Replaced by `scripts/develop` |
| `Makefile` | Replaced by `scripts/` |
| `scripts/dev_instance.sh` | Replaced by `scripts/develop` |
| `requirements_test.txt` | Consolidated into `requirements.txt` |

### Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Strip to `[tool.pytest.ini_options]` only; remove `[project]`, `[project.optional-dependencies]`, `[tool.ruff]` |
| `.gitignore` | Replace `.devconfig` ignore with `config/` (HA writes secrets, auth, DB there at runtime; `config/configuration.yaml` is tracked, everything else is not) |

## `scripts/develop` Behavior

Uses `PYTHONPATH="${PWD}"` so HA discovers `custom_components/chstides` directly from the repo root — no symlinks, no Docker volume mounts. Config dir is `config/` (replaces `.devconfig/`). On first run, creates config via `hass --script ensure_config`. Runs `hass --config config --debug`.

## `config/configuration.yaml`

```yaml
default_config:

homeassistant:
  debug: true

logger:
  default: info
  logs:
    custom_components.chstides: debug
```

## `.ruff.toml`

Copied from blueprint:
- `target-version = "py314"`
- `select = ["ALL"]`
- Standard ignores: ANN401, D203, D212, COM812, ISC001
- `fixture-parentheses = false` for pytest style
- `keep-runtime-typing = true`
- `max-complexity = 25`

## CI Workflows

### `lint.yml`
- Triggers: push + PR to `main`
- Steps: checkout → Python 3.14 setup → `pip install -r requirements.txt` → `ruff check .` → `ruff format . --check`

### `validate.yml`
- Triggers: push + PR to `main`, daily schedule, manual dispatch
- Jobs:
  - `hassfest`: uses `home-assistant/actions/hassfest`
  - `hacs`: uses `hacs/action` with `category: integration` and `ignore: brands`

## Out of Scope

- No test CI job (requires HA's full test deps; add separately later)
- No changes to `custom_components/chstides/` code
- No changes to `tests/`
