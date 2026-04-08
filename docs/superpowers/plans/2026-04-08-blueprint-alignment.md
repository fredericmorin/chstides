# Blueprint Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the CHSTides project structure with the official HA integration blueprint, replacing Docker/Makefile/uv with pip-based scripts and adding CI workflows.

**Architecture:** Replace the Docker + Makefile dev setup with three blueprint scripts (`develop`, `lint`, `setup`) that use a `PYTHONPATH` trick for HA discovery and a flat `requirements.txt` for all dependencies. Add CI via GitHub Actions and a `.devcontainer.json` for VS Code.

**Tech Stack:** Bash scripts, pip, ruff, Home Assistant CLI (`hass`), GitHub Actions

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `scripts/develop` | Run HA dev instance via PYTHONPATH |
| Create | `scripts/lint` | Run ruff format + check |
| Create | `scripts/setup` | pip install requirements.txt |
| Create | `config/configuration.yaml` | HA dev config |
| Create | `.ruff.toml` | Ruff configuration |
| Create | `.devcontainer.json` | VS Code devcontainer |
| Create | `.github/workflows/lint.yml` | CI: lint |
| Create | `.github/workflows/validate.yml` | CI: hassfest + HACS |
| Create | `requirements.txt` | All deps (runtime + dev) |
| Modify | `pyproject.toml` | Strip to `[tool.pytest.ini_options]` only |
| Modify | `.gitignore` | Replace `/.devconfig` with `config/` exceptions |
| Delete | `docker-compose.yml` | Replaced by `scripts/develop` |
| Delete | `Makefile` | Replaced by scripts |
| Delete | `scripts/dev_instance.sh` | Replaced by `scripts/develop` |
| Delete | `requirements_test.txt` | Consolidated into `requirements.txt` |

---

### Task 1: Add `requirements.txt`

**Files:**
- Create: `requirements.txt`
- Delete: `requirements_test.txt`

- [ ] **Step 1: Create `requirements.txt`**

```
colorlog==6.10.1
homeassistant>=2026
pip>=21.3.1
ruff>=0.15

# Test dependencies
pytest>=9.0
pytest-asyncio>=0.20.3
pytest-homeassistant-custom-component>=0.13.289
aioresponses>=0.7
coverage>=7.0
```

- [ ] **Step 2: Delete `requirements_test.txt`**

```bash
rm requirements_test.txt
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt requirements_test.txt
git commit -m "chore: consolidate deps into requirements.txt"
```

---

### Task 2: Strip `pyproject.toml` to pytest config only

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace `pyproject.toml` with pytest-only content**

Replace the entire file with:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Verify tests still run**

```bash
python3 -m pytest tests/ -v --co -q 2>&1 | head -20
```

Expected: test collection succeeds (lists test names, no import errors).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: strip pyproject.toml to pytest config only"
```

---

### Task 3: Add `.ruff.toml`

**Files:**
- Create: `.ruff.toml`

- [ ] **Step 1: Create `.ruff.toml`**

```toml
# Based on https://github.com/home-assistant/core/blob/dev/pyproject.toml

target-version = "py314"

[lint]
select = [
    "ALL",
]

ignore = [
    "ANN401", # Dynamically typed expressions (typing.Any) are disallowed
    "D203",   # no-blank-line-before-class (incompatible with formatter)
    "D212",   # multi-line-summary-first-line (incompatible with formatter)
    "COM812", # incompatible with formatter
    "ISC001", # incompatible with formatter
]

[lint.flake8-pytest-style]
fixture-parentheses = false

[lint.pyupgrade]
keep-runtime-typing = true

[lint.mccabe]
max-complexity = 25
```

- [ ] **Step 2: Run ruff to confirm it picks up the config**

```bash
python3 -m ruff check . --no-fix 2>&1 | head -30
```

Expected: ruff runs (may have violations — that's fine, we just want it to load config without errors).

- [ ] **Step 3: Commit**

```bash
git add .ruff.toml
git commit -m "chore: add .ruff.toml from blueprint"
```

---

### Task 4: Add `scripts/develop`, `scripts/lint`, `scripts/setup`

**Files:**
- Create: `scripts/develop`
- Create: `scripts/lint`
- Create: `scripts/setup`
- Delete: `scripts/dev_instance.sh`

- [ ] **Step 1: Create `scripts/develop`**

```bash
#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

# Create config dir if not present
if [[ ! -d "${PWD}/config" ]]; then
    mkdir -p "${PWD}/config"
    hass --config "${PWD}/config" --script ensure_config
fi

# Set the path to custom_components
## This lets us have the structure we want <root>/custom_components/chstides
## while at the same time have Home Assistant configuration inside <root>/config
## without resorting to symlinks.
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Start Home Assistant
hass --config "${PWD}/config" --debug
```

- [ ] **Step 2: Create `scripts/lint`**

```bash
#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

ruff format .
ruff check . --fix
```

- [ ] **Step 3: Create `scripts/setup`**

```bash
#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

python3 -m pip install --requirement requirements.txt
```

- [ ] **Step 4: Make all scripts executable**

```bash
chmod +x scripts/develop scripts/lint scripts/setup
```

- [ ] **Step 5: Delete `scripts/dev_instance.sh`**

```bash
rm scripts/dev_instance.sh
```

- [ ] **Step 6: Verify scripts are executable**

```bash
ls -la scripts/
```

Expected: `develop`, `lint`, `setup` all have `-rwxr-xr-x` permissions.

- [ ] **Step 7: Commit**

```bash
git add scripts/develop scripts/lint scripts/setup scripts/dev_instance.sh
git commit -m "chore: replace dev_instance.sh with blueprint scripts"
```

---

### Task 5: Add `config/configuration.yaml`

**Files:**
- Create: `config/configuration.yaml`

- [ ] **Step 1: Create `config/configuration.yaml`**

```yaml
# https://www.home-assistant.io/integrations/default_config/
default_config:

# https://www.home-assistant.io/integrations/homeassistant/
homeassistant:
  debug: true

# https://www.home-assistant.io/integrations/logger/
logger:
  default: info
  logs:
    custom_components.chstides: debug
```

- [ ] **Step 2: Update `.gitignore` to track only `configuration.yaml`, ignore the rest of `config/`**

Replace the line `/.devconfig` in `.gitignore` with:

```
/config/*
!/config/configuration.yaml
```

- [ ] **Step 3: Verify only `configuration.yaml` would be tracked**

```bash
git status config/
```

Expected: `config/configuration.yaml` shows as untracked (new file). No other `config/` files listed.

- [ ] **Step 4: Commit**

```bash
git add config/configuration.yaml .gitignore
git commit -m "chore: add config/configuration.yaml and update .gitignore"
```

---

### Task 6: Remove `docker-compose.yml` and `Makefile`

**Files:**
- Delete: `docker-compose.yml`
- Delete: `Makefile`

- [ ] **Step 1: Delete both files**

```bash
rm docker-compose.yml Makefile
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml Makefile
git commit -m "chore: remove Makefile and docker-compose in favor of blueprint scripts"
```

---

### Task 7: Add `.devcontainer.json`

**Files:**
- Create: `.devcontainer.json`

- [ ] **Step 1: Create `.devcontainer.json`**

```json
{
    "name": "chstides",
    "image": "mcr.microsoft.com/devcontainers/base:debian",
    "postCreateCommand": "scripts/setup",
    "forwardPorts": [
        8123
    ],
    "portsAttributes": {
        "8123": {
            "label": "Home Assistant",
            "onAutoForward": "notify"
        }
    },
    "customizations": {
        "vscode": {
            "extensions": [
                "charliermarsh.ruff",
                "github.vscode-pull-request-github",
                "ms-python.python",
                "ms-python.vscode-pylance",
                "ryanluker.vscode-coverage-gutters"
            ],
            "settings": {
                "files.eol": "\n",
                "editor.tabSize": 4,
                "editor.formatOnPaste": true,
                "editor.formatOnSave": true,
                "editor.formatOnType": false,
                "files.trimTrailingWhitespace": true,
                "python.analysis.typeCheckingMode": "basic",
                "python.analysis.autoImportCompletions": true,
                "[python]": {
                    "editor.defaultFormatter": "charliermarsh.ruff"
                }
            }
        }
    },
    "remoteUser": "vscode",
    "features": {
        "ghcr.io/devcontainers/features/python:1": {
            "version": "3.14"
        },
        "ghcr.io/devcontainers-extra/features/apt-packages:1": {
            "packages": "ffmpeg,libturbojpeg0,libpcap-dev"
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add .devcontainer.json
git commit -m "chore: add .devcontainer.json from blueprint"
```

---

### Task 8: Add GitHub Actions CI workflows

**Files:**
- Create: `.github/workflows/lint.yml`
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Create `.github/workflows/` directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create `.github/workflows/lint.yml`**

```yaml
name: Lint

on:
  push:
    branches:
      - "main"
  pull_request:
    branches:
      - "main"

permissions: {}

jobs:
  ruff:
    name: "Ruff"
    runs-on: "ubuntu-latest"
    steps:
      - name: Checkout the repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: "pip"

      - name: Install requirements
        run: python3 -m pip install -r requirements.txt

      - name: Lint
        run: python3 -m ruff check .

      - name: Format
        run: python3 -m ruff format . --check
```

- [ ] **Step 3: Create `.github/workflows/validate.yml`**

```yaml
name: Validate

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

permissions: {}

jobs:
  hassfest:
    name: Hassfest validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout the repository
        uses: actions/checkout@v4

      - name: Run hassfest validation
        uses: home-assistant/actions/hassfest@master

  hacs:
    name: HACS validation
    runs-on: ubuntu-latest
    steps:
      - name: Run HACS validation
        uses: hacs/action@main
        with:
          category: integration
          # Remove 'ignore' once brand images are added
          # https://developers.home-assistant.io/docs/creating_integration_file_structure#local-brand-images-for-custom-integrations
          ignore: brands
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/lint.yml .github/workflows/validate.yml
git commit -m "ci: add lint and validate workflows from blueprint"
```

---

### Task 9: Update `CLAUDE.md` dev commands

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Dev Commands section in `CLAUDE.md`**

Replace the existing Dev Commands section:

```markdown
## Dev Commands
- `scripts/setup` — install all dependencies
- `scripts/develop` — start local HA instance with integration loaded (config in `config/`)
- `scripts/lint` — ruff format + check
- `python3 -m pytest tests/ -v` — run pytest suite
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md dev commands for blueprint scripts"
```
