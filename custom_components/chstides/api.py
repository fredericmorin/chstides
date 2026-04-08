"""CHS API client, data models, and tide math helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


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
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return min(stations, key=lambda s: haversine(lat, lon, s.latitude, s.longitude))
