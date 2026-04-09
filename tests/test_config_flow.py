from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.chstides.api import Station
from custom_components.chstides.const import DOMAIN

MOCK_STATION = Station(
    id="s001", code="03580", name="Quebec City", latitude=46.81, longitude=-71.22
)


@pytest.fixture(autouse=True)
def mock_client_setup() -> Generator[AsyncMock]:
    with patch(
        "custom_components.chstides.config_flow.get_stations",
        new_callable=AsyncMock,
    ) as mock_get_stations:
        mock_get_stations.return_value = [MOCK_STATION]
        yield mock_get_stations


@pytest.mark.asyncio
async def test_step_station_shows_form(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"


@pytest.mark.asyncio
async def test_step_station_with_valid_code_proceeds(
    hass: HomeAssistant, mock_client_setup: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "03580", "auto_detect": False},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "options"


@pytest.mark.asyncio
async def test_step_station_with_invalid_code_shows_error(
    hass: HomeAssistant, mock_client_setup: AsyncMock
) -> None:
    mock_client_setup.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "INVALID", "auto_detect": False},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"station_code": "station_not_found"}


@pytest.mark.asyncio
async def test_step_station_auto_detect_prefills_nearest(
    hass: HomeAssistant, mock_client_setup: AsyncMock
) -> None:
    hass.config.latitude = 46.8
    hass.config.longitude = -71.2
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"station_code": "", "auto_detect": True},
    )
    # Re-shows the form with station_code pre-filled
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station"
    assert (
        result["description_placeholders"]["nearest_station"] == "Quebec City (03580)"
    )
