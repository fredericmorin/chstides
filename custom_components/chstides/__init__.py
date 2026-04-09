"""CHSTides — Canadian Hydrographic Service tide data for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

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
