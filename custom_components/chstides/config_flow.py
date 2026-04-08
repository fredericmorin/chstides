"""Config flow for CHSTides."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
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

_NUM_BOX = NumberSelectorMode.BOX

STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_OBSERVED_INTERVAL, default=DEFAULT_OBSERVED_INTERVAL_MINUTES
        ): NumberSelector(NumberSelectorConfig(min=1, max=60, mode=_NUM_BOX)),
        vol.Required(
            CONF_PREDICTION_DAYS, default=DEFAULT_PREDICTION_DAYS
        ): NumberSelector(NumberSelectorConfig(min=1, max=30, mode=_NUM_BOX)),
        vol.Required(
            CONF_PREDICTION_INTERVAL, default=DEFAULT_PREDICTION_INTERVAL_HOURS
        ): NumberSelector(NumberSelectorConfig(min=1, max=24, mode=_NUM_BOX)),
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
                    default=current.get(
                        CONF_OBSERVED_INTERVAL, DEFAULT_OBSERVED_INTERVAL_MINUTES
                    ),
                ): NumberSelector(NumberSelectorConfig(min=1, max=60, mode=_NUM_BOX)),
                vol.Required(
                    CONF_PREDICTION_DAYS,
                    default=current.get(CONF_PREDICTION_DAYS, DEFAULT_PREDICTION_DAYS),
                ): NumberSelector(NumberSelectorConfig(min=1, max=30, mode=_NUM_BOX)),
                vol.Required(
                    CONF_PREDICTION_INTERVAL,
                    default=current.get(
                        CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL_HOURS
                    ),
                ): NumberSelector(NumberSelectorConfig(min=1, max=24, mode=_NUM_BOX)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
