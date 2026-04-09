"""Sensor entities for CHSTides."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_STATION_CODE, CONF_STATION_ID, CONF_STATION_NAME, DOMAIN
from .coordinator import ObservedDataCoordinator, PredictionCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


def _device_info(station_name: str, station_code: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, station_code)},
        name=station_name,
        manufacturer="DFO-MPO / CHS",
        model="Tide Station",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CHSTides sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    observed = data["observed"]
    predictions = data["predictions"]

    station_name = entry.data[CONF_STATION_NAME]
    station_code = entry.data[CONF_STATION_CODE]
    station_id = entry.data[CONF_STATION_ID]

    eid = entry.entry_id
    async_add_entities(
        [
            WaterLevelSensor(observed, station_name, station_code, station_id, eid),
            TidePhaseSensor(observed, station_name, station_code, eid),
            WaterLevelSourceSensor(observed, station_name, station_code, eid),
            NextHighTideSensor(predictions, station_name, station_code, eid),
            NextLowTideSensor(predictions, station_name, station_code, eid),
            TideForecastSensor(predictions, station_name, station_code, eid),
        ]
    )


class WaterLevelSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Current observed water level height."""

    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        station_id: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_name = f"{station_name} Water Level"
        self._attr_unique_id = f"{entry_id}_water_level"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> float | None:
        """Return the current water level in metres."""
        if self.coordinator.latest is None:
            return None
        return round(self.coordinator.latest.height_m, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return station ID and timestamp of the latest reading."""
        if self.coordinator.latest is None:
            return {}
        return {
            "station_id": self._station_id,
            "timestamp": self.coordinator.latest.timestamp.isoformat(),
        }


class TidePhaseSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Current tide phase derived from recent observed water level trend."""

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Tide Phase"
        self._attr_unique_id = f"{entry_id}_tide_phase"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        """Return the current tide phase string."""
        return self.coordinator.phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return timestamp of the latest reading."""
        if self.coordinator.latest is None:
            return {}
        return {"timestamp": self.coordinator.latest.timestamp.isoformat()}


class WaterLevelSourceSensor(CoordinatorEntity[ObservedDataCoordinator], SensorEntity):
    """Indicates whether the current water level reading is measured or estimated."""

    def __init__(
        self,
        coordinator: ObservedDataCoordinator,
        station_name: str,
        station_code: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Water Level Source"
        self._attr_unique_id = f"{entry_id}_water_level_source"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        """Return 'measured' or 'estimated' depending on the data source."""
        if self.coordinator.latest is None:
            return None
        return self.coordinator.latest.source


class NextHighTideSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Next predicted high tide — time as state, height + ISO datetime as attributes."""

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Next High Tide"
        self._attr_unique_id = f"{entry_id}_next_high_tide"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        """Return the local time of the next high tide as HH:MM."""
        if self.coordinator.next_high is None:
            return None
        return dt_util.as_local(self.coordinator.next_high.timestamp).strftime("%H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return height and ISO datetime of the next high tide."""
        if self.coordinator.next_high is None:
            return {}
        return {
            "height_m": self.coordinator.next_high.height_m,
            "datetime_iso": self.coordinator.next_high.timestamp.isoformat(),
        }


class NextLowTideSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Next predicted low tide — time as state, height + ISO datetime as attributes."""

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Next Low Tide"
        self._attr_unique_id = f"{entry_id}_next_low_tide"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> str | None:
        """Return the local time of the next low tide as HH:MM."""
        if self.coordinator.next_low is None:
            return None
        return dt_util.as_local(self.coordinator.next_low.timestamp).strftime("%H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return height and ISO datetime of the next low tide."""
        if self.coordinator.next_low is None:
            return {}
        return {
            "height_m": self.coordinator.next_low.height_m,
            "datetime_iso": self.coordinator.next_low.timestamp.isoformat(),
        }


class TideForecastSensor(CoordinatorEntity[PredictionCoordinator], SensorEntity):
    """Full N-day tide forecast — event count as state, highs/lows as attribute."""

    _attr_native_unit_of_measurement = "events"

    def __init__(
        self,
        coordinator: PredictionCoordinator,
        station_name: str,
        station_code: str,
        entry_id: str,
    ) -> None:
        """Initialise with coordinator and station identifiers."""
        super().__init__(coordinator)
        self._attr_name = f"{station_name} Tide Forecast"
        self._attr_unique_id = f"{entry_id}_tide_forecast"
        self._attr_device_info = _device_info(station_name, station_code)

    @property
    def native_value(self) -> int:
        """Return the total number of forecast tide events."""
        return len(self.coordinator.forecast)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full list of forecast tide events."""
        return {
            "forecast": [
                {
                    "datetime": p.timestamp.isoformat(),
                    "type": p.type,
                    "height_m": p.height_m,
                }
                for p in self.coordinator.forecast
            ]
        }
