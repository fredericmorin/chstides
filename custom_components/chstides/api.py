"""CHS API client, data models, and tide math helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from pychs import CHS_IWLS
from pychs.const import ENDPOINT, ENDPOINT_STATIONS

from .const import (
    HTTP_ERROR_STATUS_MIN,
    TIME_SERIES_OBSERVED,
    TIME_SERIES_PREDICTED,
    TIME_SERIES_PREDICTED_CONTINUOUS,
)

if TYPE_CHECKING:
    import aiohttp

_MIN_PHASE_POINTS = 2


class TidePhase:
    """Tide phase constants."""

    RISING = "Rising"
    FALLING = "Falling"
    HIGH = "High"
    LOW = "Low"


class CHSApiError(Exception):
    """Raised when the CHS API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialise with a message and optional HTTP status code."""
        super().__init__(message)
        self.status_code = status_code

    @classmethod
    def from_status(cls, status: int) -> CHSApiError:
        """Create a CHSApiError from an HTTP status code."""
        msg = f"CHS API returned {status}"
        return cls(msg, status)


@dataclass
class Station:
    """A CHS tide station."""

    id: str
    code: str
    name: str
    latitude: float
    longitude: float


@dataclass
class ObservedData:
    """A single observed (or estimated) water level reading."""

    station_id: str
    timestamp: datetime
    height_m: float
    time_series_code: str
    source: Literal["measured", "estimated"] = "measured"


@dataclass
class PredictionPoint:
    """A single predicted tide event (HIGH or LOW)."""

    timestamp: datetime
    height_m: float
    type: Literal["HIGH", "LOW"]


class _SessionCHSIWLS(CHS_IWLS):
    """CHS_IWLS subclass that uses an injected aiohttp session."""

    def __init__(self, session: aiohttp.ClientSession, **kwargs: object) -> None:
        """Initialise with an externally managed aiohttp session."""
        super().__init__(**kwargs)
        self._ha_session = session

    async def _async_get_data(self, url: str) -> Any:
        """Fetch JSON from *url*, raising CHSApiError on HTTP errors."""
        async with self._ha_session.get(url) as resp:
            if resp.status >= HTTP_ERROR_STATUS_MIN:
                raise CHSApiError.from_status(resp.status)
            return await resp.json()

    async def _set_station_data(self, data: dict) -> None:
        """No-op: we create fresh instances per call."""

    async def stations(self, **kwargs: Any) -> list[Any]:
        """Guard against IndexError when a code filter returns no results."""
        params = ["code", "chs-region-code", "time-series-code"]
        if self._station_code and kwargs.get("code") is None:
            kwargs["code"] = self._station_code
        qparams = self._validate_query_parameters(params, **kwargs)
        url = ENDPOINT + ENDPOINT_STATIONS + self._construct_query_parameters(**qparams)
        data = await self._async_get_data(url)
        if not isinstance(data, list) or not data:
            return data if isinstance(data, list) else []
        if qparams.get("code") is not None:
            await self._set_station_data(data[0])
        return data


async def get_stations(
    session: aiohttp.ClientSession, code: str | None = None
) -> list[Station]:
    """Return all stations, or those matching station code."""
    chs = _SessionCHSIWLS(session, station_code=code)
    data = await chs.stations()
    if not isinstance(data, list):
        return []
    return [
        Station(
            id=s["id"],
            code=s["code"],
            name=s["officialName"],
            latitude=s["latitude"],
            longitude=s["longitude"],
        )
        for s in data
    ]


async def get_observed_water_level(
    session: aiohttp.ClientSession, station_id: str
) -> list[ObservedData]:
    """Return the last 30 minutes of observed water level readings."""
    now = datetime.now(UTC).replace(tzinfo=None)
    from_dt = now - timedelta(minutes=30)
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(
        **{
            "time-series-code": TIME_SERIES_OBSERVED,
            "from": from_dt,
            "to": now,
        }
    )
    return [
        ObservedData(
            station_id=station_id,
            timestamp=datetime.fromisoformat(d["eventDate"]),
            height_m=float(d["value"]),
            time_series_code=TIME_SERIES_OBSERVED,
        )
        for d in data
    ]


async def get_predicted_water_level(
    session: aiohttp.ClientSession, station_id: str
) -> list[ObservedData]:
    """
    Return last 30 min of wlp predictions up to now.

    Returns ObservedData with source='estimated'.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    from_dt = now - timedelta(minutes=30)
    to_dt = now
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(
        **{
            "time-series-code": TIME_SERIES_PREDICTED_CONTINUOUS,
            "from": from_dt,
            "to": to_dt,
        }
    )
    return [
        ObservedData(
            station_id=station_id,
            timestamp=datetime.fromisoformat(d["eventDate"]),
            height_m=float(d["value"]),
            time_series_code=TIME_SERIES_PREDICTED_CONTINUOUS,
            source="estimated",
        )
        for d in data
    ]


async def get_predictions(
    session: aiohttp.ClientSession, station_id: str, days: int
) -> list[PredictionPoint]:
    """Return HIGH/LOW tide events for the next N days using wlp-hilo."""
    # microsecond=1 ensures the library's isoformat()[:-7] strips correctly
    today = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=1, tzinfo=None
    )
    to_dt = today + timedelta(days=days, hours=23, minutes=59, seconds=59)
    chs = _SessionCHSIWLS(session, station_id=station_id)
    data = await chs.station_data(
        **{
            "time-series-code": TIME_SERIES_PREDICTED,
            "from": today,
            "to": to_dt,
        }
    )
    raw = [
        PredictionPoint(
            timestamp=datetime.fromisoformat(d["eventDate"]),
            height_m=float(d["value"]),
            type="HIGH",
        )
        for d in data
    ]
    return _classify_hilo(raw)


def _classify_hilo(points: list[PredictionPoint]) -> list[PredictionPoint]:
    """Label wlp-hilo events HIGH or LOW by comparing adjacent heights."""
    if not points:
        return []
    if len(points) == 1:
        return [PredictionPoint(points[0].timestamp, points[0].height_m, "HIGH")]
    result = []
    for i, p in enumerate(points):
        if i < len(points) - 1:
            tide_type: Literal["HIGH", "LOW"] = (
                "HIGH" if p.height_m > points[i + 1].height_m else "LOW"
            )
        else:
            tide_type = "HIGH" if p.height_m > points[i - 1].height_m else "LOW"
        result.append(PredictionPoint(p.timestamp, p.height_m, tide_type))
    return result


def derive_tide_phase(recent_points: list[ObservedData]) -> str:
    """Derive tide phase from the trend of recent observed water level points."""
    if len(recent_points) < _MIN_PHASE_POINTS:
        return TidePhase.RISING
    diff = recent_points[-1].height_m - recent_points[-2].height_m
    return TidePhase.RISING if diff >= 0 else TidePhase.FALLING


def find_nearest_station(stations: list[Station], lat: float, lon: float) -> Station:
    """Return the station closest to (lat, lon) using Haversine distance."""

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return min(stations, key=lambda s: haversine(lat, lon, s.latitude, s.longitude))
