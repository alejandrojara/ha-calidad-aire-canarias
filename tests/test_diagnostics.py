"""Tests for Calidad del Aire - Gobierno de Canarias diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calidad_aire_canarias.const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_TAG,
    DOMAIN,
)
from custom_components.calidad_aire_canarias.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import SAMPLE_TOKEN


async def test_diagnostics_redacts_access_token(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Ensure Bearer token is strictly redacted in diagnostics output."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="101",
        title="Santa Cruz - Tomé Cano (SC_TC)",
        data={
            CONF_ACCESS_TOKEN: SAMPLE_TOKEN,
            CONF_STATION_ID: 101,
            CONF_STATION_NAME: "Santa Cruz - Tomé Cano",
            CONF_STATION_TAG: "SC_TC",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"]["data"][CONF_ACCESS_TOKEN] == REDACTED
    assert SAMPLE_TOKEN not in str(diag)
    assert diag["coordinator"]["station_id"] == 101
    assert diag["coordinator"]["rate_limit_active"] is False
    assert diag["coordinator"]["station"]["overall_ica"] == "Regular"
    assert diag["coordinator"]["station"]["dominant_parameter"] == "PM10"
