from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.chstides.api import ObservedData, PredictionPoint, TidePhase, CHSApiError
from custom_components.chstides.coordinator import ObservedDataCoordinator, PredictionCoordinator


@pytest.fixture
def hass(hass):
    return hass


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_observed_coordinator_stores_latest_and_phase(hass, mock_client, now):
    mock_client.get_observed_water_level.return_value = [
        ObservedData("s1", now, 1.0, "wlo"),
        ObservedData("s1", now, 1.5, "wlo"),
    ]
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    await coord.async_refresh()

    assert coord.latest.height_m == 1.5
    assert coord.phase == TidePhase.RISING


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_api_error(hass, mock_client):
    mock_client.get_observed_water_level.side_effect = CHSApiError("timeout", None)
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_observed_coordinator_raises_on_empty_data(hass, mock_client):
    mock_client.get_observed_water_level.return_value = []
    coord = ObservedDataCoordinator(hass, mock_client, "s1", 5)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_prediction_coordinator_sets_next_high_and_low(hass, mock_client, now):
    future_high = datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc)
    future_low = datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc)
    mock_client.get_predictions.return_value = [
        PredictionPoint(future_high, 3.1, "HIGH"),
        PredictionPoint(future_low, 0.4, "LOW"),
    ]
    coord = PredictionCoordinator(hass, mock_client, "s1", 7, 24)
    await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
    assert coord.next_low.height_m == 0.4
    assert len(coord.forecast) == 2


@pytest.mark.asyncio
async def test_prediction_coordinator_keeps_stale_on_error(hass, mock_client, now):
    future = datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc)
    mock_client.get_predictions.return_value = [PredictionPoint(future, 3.1, "HIGH")]
    coord = PredictionCoordinator(hass, mock_client, "s1", 7, 24)
    await coord.async_refresh()

    # Second call fails — stale data retained
    mock_client.get_predictions.side_effect = CHSApiError("timeout", None)
    await coord.async_refresh()

    assert coord.next_high.height_m == 3.1
