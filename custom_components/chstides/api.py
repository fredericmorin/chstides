"""CHS API client, data models, and tide math helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import aiohttp
from pychs import CHS_IWLS


class _SessionCHSIWLS(CHS_IWLS):
    """CHS_IWLS subclass that uses an injected aiohttp session."""

    def __init__(self, session: aiohttp.ClientSession, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._ha_session = session

    async def _async_get_data(self, url: str) -> Any:
        async with self._ha_session.get(url) as resp:
            if resp.status >= 400:
                raise CHSApiError(f"CHS API returned {resp.status}", resp.status)
            return await resp.json()

    async def _set_station_data(self, data: dict) -> None:
        pass  # We create fresh instances per call; discard library-managed state.

    async def stations(self, **kwargs: object) -> list[Any]:
        """Override to guard against IndexError when a code filter returns no results."""
        from pychs.const import ENDPOINT, ENDPOINT_STATIONS

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


class TidePhase:
    RISING = "Rising"
    FALLING = "Falling"
    HIGH = "High"
    LOW = "Low"


class CHSApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Station:
    id: str
    code: str
    name: str
    latitude: float
    longitude: float


@dataclass
class ObservedData:
    station_id: str
    timestamp: datetime
    height_m: float
    time_series_code: str


@dataclass
class PredictionPoint:
    timestamp: datetime
    height_m: float
    type: Literal["HIGH", "LOW", "UNKNOWN"]


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


class CHSApiClient:
    """HTTP client for the CHS Integrated Water Level System API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        from .const import CHS_API_BASE

        url = f"{CHS_API_BASE}{path}"
        async with self._session.get(url, params=params) as resp:
            if resp.status >= 400:
                raise CHSApiError(f"CHS API returned {resp.status}", resp.status)
            return await resp.json()

    async def get_stations(self, code: str | None = None) -> list[Station]:
        params: dict[str, str] = {}
        if code:
            params["code"] = code
        data = await self._get("/api/v1/stations", params or None)
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

    async def get_station(self, station_id: str) -> Station:
        data = await self._get(f"/api/v1/stations/{station_id}")
        return Station(
            id=data["id"],
            code=data["code"],
            name=data["officialName"],
            latitude=data["latitude"],
            longitude=data["longitude"],
        )

    async def get_observed_water_level(self, station_id: str) -> list[ObservedData]:
        from .const import TIME_SERIES_OBSERVED

        now = datetime.now(UTC)
        from_dt = now - timedelta(minutes=30)
        params = {
            "time-series-code": TIME_SERIES_OBSERVED,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data = await self._get(f"/api/v1/stations/{station_id}/data", params)
        return [
            ObservedData(
                station_id=station_id,
                timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
                height_m=float(d["value"]),
                time_series_code=TIME_SERIES_OBSERVED,
            )
            for d in data
        ]

    async def get_predictions(
        self, station_id: str, days: int
    ) -> list[PredictionPoint]:
        from .const import TIME_SERIES_PREDICTED

        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = today + timedelta(days=days, hours=23, minutes=59, seconds=59)
        params = {
            "time-series-code": TIME_SERIES_PREDICTED,
            "from": today.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data = await self._get(f"/api/v1/stations/{station_id}/data", params)
        raw = [
            PredictionPoint(
                timestamp=datetime.fromisoformat(d["eventDate"].replace("Z", "+00:00")),
                height_m=float(d["value"]),
                type="UNKNOWN",
            )
            for d in data
        ]
        return find_highs_lows(raw)


def derive_tide_phase(recent_points: list[ObservedData]) -> str:
    """Derive tide phase from the trend of recent observed water level points."""
    if len(recent_points) < 2:
        return TidePhase.RISING
    diff = recent_points[-1].height_m - recent_points[-2].height_m
    return TidePhase.RISING if diff >= 0 else TidePhase.FALLING


def find_highs_lows(points: list[PredictionPoint]) -> list[PredictionPoint]:
    """Identify local maxima (HIGH) and minima (LOW) in a prediction time series."""
    if len(points) < 3:
        return []
    result = []
    for i in range(1, len(points) - 1):
        prev_h = points[i - 1].height_m
        curr_h = points[i].height_m
        next_h = points[i + 1].height_m
        if curr_h > prev_h and curr_h > next_h:
            result.append(PredictionPoint(points[i].timestamp, curr_h, "HIGH"))
        elif curr_h < prev_h and curr_h < next_h:
            result.append(PredictionPoint(points[i].timestamp, curr_h, "LOW"))
    return result
