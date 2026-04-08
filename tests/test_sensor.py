from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant

from custom_components.chstides.api import ObservedData, TidePhase
from custom_components.chstides.coordinator import ObservedDataCoordinator, PredictionCoordinator
from custom_components.chstides.sensor import WaterLevelSensor, TidePhaseSensor


@pytest.fixture
def observed_coord(hass):
    coord = MagicMock(spec=ObservedDataCoordinator)
    coord.hass = hass
    coord.latest = ObservedData(
        station_id="s001",
        timestamp=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        height_m=1.42,
        time_series_code="wlo",
    )
    coord.phase = TidePhase.RISING
    return coord


def test_water_level_sensor_state(observed_coord):
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value == 1.42
    assert sensor.native_unit_of_measurement == "m"


def test_water_level_sensor_attributes(observed_coord):
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    attrs = sensor.extra_state_attributes
    assert attrs["station_id"] == "s001"
    assert "timestamp" in attrs


def test_water_level_sensor_none_when_no_data(observed_coord):
    observed_coord.latest = None
    sensor = WaterLevelSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value is None


def test_tide_phase_sensor_state(observed_coord):
    sensor = TidePhaseSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value == TidePhase.RISING


def test_tide_phase_sensor_unique_id(observed_coord):
    sensor = TidePhaseSensor(observed_coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.unique_id == "entry1_tide_phase"
