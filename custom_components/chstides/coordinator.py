"""DataUpdateCoordinators for observed water level and tide predictions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
    derive_tide_phase,
    get_observed_water_level,
    get_predictions,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ObservedDataCoordinator(DataUpdateCoordinator):
    """Polls observed water level (wlo) on a short interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        station_id: str,
        interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_observed_{station_id}",
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._session = session
        self._station_id = station_id
        self.latest: ObservedData | None = None
        self.phase: str = TidePhase.RISING

    async def _async_update_data(self) -> dict:
        try:
            points = await get_observed_water_level(self._session, self._station_id)
        except CHSApiError as err:
            if err.status_code == 404:
                _LOGGER.warning(
                    "Station %s has no observed water level data (wlo); "
                    "observed sensors will be unavailable.",
                    self._station_id,
                )
                return {"latest": None, "phase": self.phase}
            raise UpdateFailed(f"CHS API error: {err}") from err
        if not points:
            raise UpdateFailed("No observed data returned from CHS API")
        self.latest = points[-1]
        self.phase = derive_tide_phase(points)
        return {"latest": self.latest, "phase": self.phase}


class PredictionCoordinator(DataUpdateCoordinator):
    """Polls tide predictions (wlp) daily and caches stale data on failure."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        station_id: str,
        days: int,
        interval_hours: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_predictions_{station_id}",
            update_interval=timedelta(hours=interval_hours),
        )
        self._session = session
        self._station_id = station_id
        self._days = days
        self.forecast: list[PredictionPoint] = []
        self.next_high: PredictionPoint | None = None
        self.next_low: PredictionPoint | None = None

    async def _async_update_data(self) -> dict:
        try:
            points = await get_predictions(self._session, self._station_id, self._days)
        except CHSApiError as err:
            _LOGGER.warning("Failed to fetch predictions, keeping stale data: %s", err)
            return {
                "forecast": self.forecast,
                "next_high": self.next_high,
                "next_low": self.next_low,
            }

        now = datetime.now(UTC)
        self.forecast = points
        future = [p for p in points if p.timestamp > now]
        self.next_high = next((p for p in future if p.type == "HIGH"), None)
        self.next_low = next((p for p in future if p.type == "LOW"), None)
        return {
            "forecast": self.forecast,
            "next_high": self.next_high,
            "next_low": self.next_low,
        }
