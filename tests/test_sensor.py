from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.chstides.api import ObservedData, PredictionPoint, TidePhase
from custom_components.chstides.coordinator import (
    ObservedDataCoordinator,
    PredictionCoordinator,
)
from custom_components.chstides.sensor import (
    NextHighTideSensor,
    NextLowTideSensor,
    TideForecastSensor,
    TidePhaseSensor,
    WaterLevelSensor,
)


@pytest.fixture
def observed_coord(hass):
    coord = MagicMock(spec=ObservedDataCoordinator)
    coord.hass = hass
    coord.latest = ObservedData(
        station_id="s001",
        timestamp=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
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


@pytest.fixture
def prediction_coord(hass):
    future_high = datetime(2026, 4, 8, 14, 30, tzinfo=UTC)
    future_low = datetime(2026, 4, 8, 20, 0, tzinfo=UTC)
    coord = MagicMock(spec=PredictionCoordinator)
    coord.hass = hass
    coord.next_high = PredictionPoint(future_high, 3.1, "HIGH")
    coord.next_low = PredictionPoint(future_low, 0.4, "LOW")
    coord.forecast = [
        PredictionPoint(future_high, 3.1, "HIGH"),
        PredictionPoint(future_low, 0.4, "LOW"),
    ]
    return coord


def test_next_high_tide_sensor_state(prediction_coord):
    sensor = NextHighTideSensor(
        prediction_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert "14:30" in sensor.native_value


def test_next_high_tide_sensor_attributes(prediction_coord):
    sensor = NextHighTideSensor(
        prediction_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.extra_state_attributes["height_m"] == 3.1
    assert "datetime_iso" in sensor.extra_state_attributes


def test_next_low_tide_sensor_state(prediction_coord):
    sensor = NextLowTideSensor(
        prediction_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert "20:00" in sensor.native_value


def test_tide_forecast_sensor_state_is_count(prediction_coord):
    sensor = TideForecastSensor(
        prediction_coord, "Quebec City", "03580", "s001", "entry1"
    )
    assert sensor.native_value == 2


def test_tide_forecast_sensor_forecast_attribute(prediction_coord):
    sensor = TideForecastSensor(
        prediction_coord, "Quebec City", "03580", "s001", "entry1"
    )
    forecast = sensor.extra_state_attributes["forecast"]
    assert len(forecast) == 2
    assert forecast[0]["type"] == "HIGH"
    assert forecast[0]["height_m"] == 3.1
    assert "datetime" in forecast[0]


def test_next_high_tide_none_when_no_data(hass):
    coord = MagicMock(spec=PredictionCoordinator)
    coord.hass = hass
    coord.next_high = None
    sensor = NextHighTideSensor(coord, "Quebec City", "03580", "s001", "entry1")
    assert sensor.native_value is None
