import math
import pytest
from datetime import datetime, timezone
from custom_components.chstides.api import (
    Station,
    ObservedData,
    PredictionPoint,
    TidePhase,
    CHSApiError,
    find_nearest_station,
)


def test_station_dataclass():
    s = Station(id="abc", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22)
    assert s.id == "abc"
    assert s.code == "03580"
    assert s.latitude == 46.81


def test_find_nearest_station_returns_closest():
    stations = [
        Station("1", "A", "Far", 60.0, -80.0),
        Station("2", "B", "Near", 45.5, -73.6),
        Station("3", "C", "Mid", 50.0, -75.0),
    ]
    result = find_nearest_station(stations, 45.4, -73.5)
    assert result.code == "B"


def test_find_nearest_station_single():
    stations = [Station("1", "A", "Only", 46.0, -72.0)]
    result = find_nearest_station(stations, 45.0, -71.0)
    assert result.code == "A"


def test_chs_api_error_stores_status():
    err = CHSApiError("not found", 404)
    assert err.status_code == 404
    assert "not found" in str(err)
