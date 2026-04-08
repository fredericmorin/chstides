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


from custom_components.chstides.api import derive_tide_phase, find_highs_lows


def _obs(height: float) -> ObservedData:
    return ObservedData("s1", datetime.now(timezone.utc), height, "wlo")


def test_derive_tide_phase_rising():
    assert derive_tide_phase([_obs(1.0), _obs(1.5)]) == TidePhase.RISING


def test_derive_tide_phase_falling():
    assert derive_tide_phase([_obs(1.5), _obs(1.0)]) == TidePhase.FALLING


def test_derive_tide_phase_single_point_defaults_rising():
    assert derive_tide_phase([_obs(1.0)]) == TidePhase.RISING


def test_derive_tide_phase_empty_defaults_rising():
    assert derive_tide_phase([]) == TidePhase.RISING


def test_find_highs_lows_identifies_single_peak_and_valley():
    # heights: low -> peak -> low -> valley -> low
    heights = [0.5, 1.0, 2.0, 1.5, 0.8, 0.3, 0.6]
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in heights]
    result = find_highs_lows(points)
    highs = [p for p in result if p.type == "HIGH"]
    lows = [p for p in result if p.type == "LOW"]
    assert len(highs) == 1
    assert highs[0].height_m == 2.0
    assert len(lows) == 1
    assert lows[0].height_m == 0.3


def test_find_highs_lows_empty_for_short_series():
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in [1.0, 2.0]]
    assert find_highs_lows(points) == []


def test_find_highs_lows_flat_series_returns_empty():
    now = datetime.now(timezone.utc)
    points = [PredictionPoint(now, 1.0, "UNKNOWN") for _ in range(5)]
    assert find_highs_lows(points) == []
