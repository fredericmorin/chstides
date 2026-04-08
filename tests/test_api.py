import re
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    Station,
    TidePhase,
    _SessionCHSIWLS,
    derive_tide_phase,
    find_nearest_station,
    get_observed_water_level,
    get_predicted_water_level,
    get_predictions,
    get_stations,
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


@pytest.mark.asyncio
async def test_get_stations_returns_all_stations(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        payload=[
            {
                "id": "s001",
                "code": "03580",
                "officialName": "Quebec City",
                "latitude": 46.81,
                "longitude": -71.22,
            }
        ],
    )
    async with aiohttp.ClientSession() as session:
        stations = await get_stations(session)
    assert len(stations) == 1
    assert stations[0].code == "03580"
    assert stations[0].name == "Quebec City"


@pytest.mark.asyncio
async def test_get_stations_with_code_filter(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations\?code=03580"),
        payload=[
            {
                "id": "s001",
                "code": "03580",
                "officialName": "Quebec City",
                "latitude": 46.81,
                "longitude": -71.22,
            }
        ],
    )
    async with aiohttp.ClientSession() as session:
        stations = await get_stations(session, code="03580")
    assert stations[0].code == "03580"


@pytest.mark.asyncio
async def test_get_stations_empty_returns_empty_list(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations\?code=NOPE"),
        payload=[],
    )
    async with aiohttp.ClientSession() as session:
        stations = await get_stations(session, code="NOPE")
    assert stations == []


@pytest.mark.asyncio
async def test_get_stations_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        "https://api-iwls.dfo-mpo.gc.ca/api/v1/stations",
        status=500,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError) as exc_info:
            await get_stations(session)
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_observed_water_level_returns_observed_data(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlo"
        ),
        payload=[
            {"eventDate": "2026-04-07T12:00:00Z", "value": 1.42, "qcFlagCode": "1"},
            {"eventDate": "2026-04-07T12:05:00Z", "value": 1.50, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_observed_water_level(session, "s001")
    assert len(points) == 2
    assert points[0].height_m == 1.42
    assert points[1].height_m == 1.50
    assert points[0].station_id == "s001"
    assert points[0].time_series_code == "wlo"
    assert points[0].source == "measured"
    assert points[1].source == "measured"


@pytest.mark.asyncio
async def test_get_observed_water_level_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_observed_water_level(session, "s001")


@pytest.mark.asyncio
async def test_get_predictions_classifies_high_low(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlp-hilo"
        ),
        payload=[
            {"eventDate": "2026-04-08T06:00:00Z", "value": 3.1, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T12:00:00Z", "value": 0.4, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T18:00:00Z", "value": 2.9, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert len(points) == 3
    assert points[0].type == "HIGH"
    assert points[0].height_m == 3.1
    assert points[1].type == "LOW"
    assert points[1].height_m == 0.4
    assert points[2].type == "HIGH"
    assert points[2].height_m == 2.9


@pytest.mark.asyncio
async def test_get_predictions_single_event_defaults_high(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        payload=[
            {"eventDate": "2026-04-08T06:00:00Z", "value": 3.1, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert len(points) == 1
    assert points[0].type == "HIGH"


@pytest.mark.asyncio
async def test_get_predictions_empty_returns_empty(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        payload=[],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predictions(session, "s001", days=1)
    assert points == []


@pytest.mark.asyncio
async def test_get_predictions_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=500,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_predictions(session, "s001", days=1)


@pytest.mark.asyncio
async def test_get_predicted_water_level_returns_estimated_data(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(
            r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data.*time-series-code=wlp"
        ),
        payload=[
            {"eventDate": "2026-04-08T12:00:00Z", "value": 1.80, "qcFlagCode": "1"},
            {"eventDate": "2026-04-08T12:15:00Z", "value": 1.85, "qcFlagCode": "1"},
        ],
    )
    async with aiohttp.ClientSession() as session:
        points = await get_predicted_water_level(session, "s001")
    assert len(points) == 2
    assert points[0].height_m == 1.80
    assert points[1].height_m == 1.85
    assert points[0].source == "estimated"
    assert points[1].source == "estimated"
    assert points[0].time_series_code == "wlp"
    assert points[0].station_id == "s001"


@pytest.mark.asyncio
async def test_get_predicted_water_level_raises_on_error(mock_aiohttp):
    mock_aiohttp.get(
        re.compile(r"https://api-iwls\.dfo-mpo\.gc\.ca/api/v1/stations/s001/data"),
        status=503,
    )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CHSApiError):
            await get_predicted_water_level(session, "s001")
