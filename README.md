# CHSTides

Canadian Hydrographic Service (CHS) tide data integration for Home Assistant (via HACS)

## Supported Entities
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
