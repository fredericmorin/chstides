import re
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.chstides.api import (
    CHSApiError,
    CHSApiClient,
    ObservedData,
    PredictionPoint,
    Station,
    TidePhase,
    _SessionCHSIWLS,
    derive_tide_phase,
    find_highs_lows,
    find_nearest_station,
)


def test_station_dataclass():
    s = Station(
        id="abc", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22
    )
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


def _obs(height: float) -> ObservedData:
    return ObservedData("s1", datetime.now(UTC), height, "wlo")


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
    now = datetime.now(UTC)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in heights]
    result = find_highs_lows(points)
    highs = [p for p in result if p.type == "HIGH"]
    lows = [p for p in result if p.type == "LOW"]
    assert len(highs) == 1
    assert highs[0].height_m == 2.0
    assert len(lows) == 1
    assert lows[0].height_m == 0.3


def test_find_highs_lows_empty_for_short_series():
    now = datetime.now(UTC)
    points = [PredictionPoint(now, h, "UNKNOWN") for h in [1.0, 2.0]]
    assert find_highs_lows(points) == []


def test_find_highs_lows_flat_series_returns_empty():
    now = datetime.now(UTC)
    points = [PredictionPoint(now, 1.0, "UNKNOWN") for _ in range(5)]
    assert find_highs_lows(points) == []


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


@pytest.mark.asyncio
async def test_session_chs_iwls_raises_on_http_error(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        client = _SessionCHSIWLS(session)
        with pytest.raises(CHSApiError) as exc_info:
            await client._async_get_data(
                "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations"
            )
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_session_chs_iwls_returns_json(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        payload=[{"id": "s001"}],
    )
    async with aiohttp.ClientSession() as session:
        client = _SessionCHSIWLS(session)
        data = await client._async_get_data(
            "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations"
        )
    assert data == [{"id": "s001"}]
