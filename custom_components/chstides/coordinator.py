"""DataUpdateCoordinators for observed water level and tide predictions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
    derive_tide_phase,
    get_observed_water_level,
    get_predicted_water_level,
    get_predictions,
)
from .const import DOMAIN, HTTP_STATUS_NOT_FOUND

if TYPE_CHECKING:
    import aiohttp
    from homeassistant.core import HomeAssistant

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
        """Initialise the coordinator with station and update interval."""
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
        """Fetch the latest observed water level, falling back to wlp on 404."""
        try:
            points = await get_observed_water_level(self._session, self._station_id)
        except CHSApiError as err:
            if err.status_code == HTTP_STATUS_NOT_FOUND:
                _LOGGER.warning(
                    "Station %s has no observed water level data (wlo); "
                    "falling back to predicted water level (wlp).",
                    self._station_id,
                )
                return await self._fetch_predicted_fallback()
            msg = f"CHS API error: {err}"
            raise UpdateFailed(msg) from err
        if not points:
            msg = "No observed data returned from CHS API"
            raise UpdateFailed(msg)
        self.latest = points[-1]
        self.phase = derive_tide_phase(points)
        return {"latest": self.latest, "phase": self.phase}

    async def _fetch_predicted_fallback(self) -> dict:
        """Fetch wlp predictions as a fallback when wlo returns 404."""
        try:
            points = await get_predicted_water_level(self._session, self._station_id)
        except CHSApiError as err:
            _LOGGER.warning(
                "Failed to fetch predicted fallback for station %s: %s",
                self._station_id,
                err,
            )
            self.latest = None
            return {"latest": None, "phase": self.phase}
        if not points:
            self.latest = None
            return {"latest": None, "phase": self.phase}
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
        """Initialise with station, forecast window, and update interval."""
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
        self._unsub_event_timer: callable | None = None

    @property
    def next_high(self) -> PredictionPoint | None:
        """Return the next future high tide, evaluated at read time."""
        now = datetime.now(UTC)
        return next(
            (p for p in self.forecast if p.type == "HIGH" and p.timestamp > now), None
        )

    @property
    def next_low(self) -> PredictionPoint | None:
        """Return the next future low tide, evaluated at read time."""
        now = datetime.now(UTC)
        return next(
            (p for p in self.forecast if p.type == "LOW" and p.timestamp > now), None
        )

    async def _async_update_data(self) -> dict:
        """Fetch tide predictions, keeping stale data on failure."""
        try:
            points = await get_predictions(self._session, self._station_id, self._days)
        except CHSApiError as err:
            _LOGGER.warning("Failed to fetch predictions, keeping stale data: %s", err)
            return {"forecast": self.forecast}

        self.forecast = points
        self._schedule_next_event_refresh()
        return {"forecast": self.forecast}

    def _schedule_next_event_refresh(self) -> None:
        """Schedule a listener notification just after the next tide event passes."""
        if self._unsub_event_timer is not None:
            self._unsub_event_timer()
            self._unsub_event_timer = None

        now = datetime.now(UTC)
        next_event = next((p for p in self.forecast if p.timestamp > now), None)
        if next_event is None:
            return

        fire_at = next_event.timestamp + timedelta(minutes=1)

        @callback
        def _on_event_passed(_now: datetime) -> None:
            self._unsub_event_timer = None
            self.async_update_listeners()
            self._schedule_next_event_refresh()

        self._unsub_event_timer = async_track_point_in_utc_time(
            self.hass, _on_event_passed, fire_at
        )
