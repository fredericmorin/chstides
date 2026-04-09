from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.chstides.api import (
    CHSApiError,
    ObservedData,
    PredictionPoint,
    TidePhase,
)
from custom_components.chstides.coordinator import (
    ObservedDataCoordinator,
    PredictionCoordinator,
)


@pytest.fixture
def hass(hass: HomeAssistant) -> HomeAssistant:
    return hass


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=aiohttp.ClientSession)


@pytest.fixture
def now() -> datetime:
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_observed_coordinator_stores_latest_and_phase(
    hass: HomeAssistant, mock_session: AsyncMock, now: datetime
) -> None:
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(
            return_value=[
                ObservedData("s1", now, 1.0, "wlo"),
                ObservedData("s1", now, 1.5, "wlo"),
            ]
        ),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        await coord.async_refresh()

    assert coord.latest.height_m == 1.5
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_api_error(
    hass: HomeAssistant, mock_session: AsyncMock
) -> None:
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(side_effect=CHSApiError("timeout", None)),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_empty_data(
    hass: HomeAssistant, mock_session: AsyncMock
) -> None:
    with patch(
        "custom_components.chstides.coordinator.get_observed_water_level",
        new=AsyncMock(return_value=[]),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_prediction_coordinator_sets_next_high_and_low(
    hass: HomeAssistant, mock_session: AsyncMock, now: datetime
) -> None:
    future_high = now + timedelta(hours=2)
    future_low = now + timedelta(hours=6)
    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=AsyncMock(
            return_value=[
                PredictionPoint(future_high, 3.1, "HIGH"),
                PredictionPoint(future_low, 0.4, "LOW"),
            ]
        ),
    ):
        coord = PredictionCoordinator(hass, mock_session, "s1", 7, 24)
        await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
    assert coord.next_low.height_m == 0.4
    assert len(coord.forecast) == 2


@pytest.mark.asyncio
async def test_prediction_coordinator_keeps_stale_on_error(
    hass: HomeAssistant, mock_session: AsyncMock, now: datetime
) -> None:
    future = now + timedelta(hours=2)
    first_call = AsyncMock(return_value=[PredictionPoint(future, 3.1, "HIGH")])
    second_call = AsyncMock(side_effect=CHSApiError("timeout", None))

    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=first_call,
    ):
        coord = PredictionCoordinator(hass, mock_session, "s1", 7, 24)
        await coord.async_refresh()

    with patch(
        "custom_components.chstides.coordinator.get_predictions",
        new=second_call,
    ):
        await coord.async_refresh()

    assert coord.next_high.height_m == 3.1


@pytest.mark.asyncio
async def test_observed_coordinator_falls_back_to_wlp_on_404(
    hass: HomeAssistant, mock_session: AsyncMock, now: datetime
) -> None:
    predicted_points = [
        ObservedData("s1", now, 1.8, "wlp", source="estimated"),
        ObservedData("s1", now, 1.85, "wlp", source="estimated"),
    ]
    with (
        patch(
            "custom_components.chstides.coordinator.get_observed_water_level",
            new=AsyncMock(side_effect=CHSApiError("not found", 404)),
        ),
        patch(
            "custom_components.chstides.coordinator.get_predicted_water_level",
            new=AsyncMock(return_value=predicted_points),
        ),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        await coord.async_refresh()

    assert coord.latest.height_m == 1.85
    assert coord.latest.source == "estimated"
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_returns_none_when_wlp_also_fails(
    hass: HomeAssistant, mock_session: AsyncMock
) -> None:
    with (
        patch(
            "custom_components.chstides.coordinator.get_observed_water_level",
            new=AsyncMock(side_effect=CHSApiError("not found", 404)),
        ),
        patch(
            "custom_components.chstides.coordinator.get_predicted_water_level",
            new=AsyncMock(side_effect=CHSApiError("wlp error", 500)),
        ),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        result = await coord._async_update_data()

    assert result["latest"] is None


@pytest.mark.asyncio
async def test_observed_coordinator_returns_none_when_wlp_empty(
    hass: HomeAssistant, mock_session: AsyncMock
) -> None:
    with (
        patch(
            "custom_components.chstides.coordinator.get_observed_water_level",
            new=AsyncMock(side_effect=CHSApiError("not found", 404)),
        ),
        patch(
            "custom_components.chstides.coordinator.get_predicted_water_level",
            new=AsyncMock(return_value=[]),
        ),
    ):
        coord = ObservedDataCoordinator(hass, mock_session, "s1", 5)
        result = await coord._async_update_data()

    assert result["latest"] is None
