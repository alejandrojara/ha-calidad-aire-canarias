"""Tests for config flow, reauth, reconfigure, and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calidad_aire_canarias.api import (
    CalidadAireCanariasAuthError,
    CalidadAireCanariasConnectionError,
    CalidadAireCanariasRateLimitError,
)
from custom_components.calidad_aire_canarias.const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_TAG,
    DOMAIN,
)

from .conftest import SAMPLE_TOKEN


async def test_user_flow_success_and_bearer_prefix_stripped(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Test two-step user config flow including Bearer prefix normalization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["last_step"] is False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_TOKEN: f"Bearer {SAMPLE_TOKEN}"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station"
    assert result["last_step"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "101"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Santa Cruz - Tomé Cano (SC_TC)"
    assert result["data"] == {
        CONF_ACCESS_TOKEN: SAMPLE_TOKEN,
        CONF_STATION_ID: 101,
        CONF_STATION_NAME: "Santa Cruz - Tomé Cano",
        CONF_STATION_TAG: "SC_TC",
    }


async def test_user_flow_errors(hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]) -> None:
    """Test invalid_auth, rate_limited, cannot_connect, and no_active_stations errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Whitespace-only token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "   "}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    # Auth error
    mock_api_client["stations"].side_effect = CalidadAireCanariasAuthError("401")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    # Rate limit error
    mock_api_client["stations"].side_effect = CalidadAireCanariasRateLimitError("429")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "tok"}
    )
    assert result["errors"] == {"base": "rate_limited"}

    # Connection error
    mock_api_client["stations"].side_effect = CalidadAireCanariasConnectionError("timeout")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "tok"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    # No active stations
    mock_api_client["stations"].side_effect = None
    mock_api_client["stations"].return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "tok"}
    )
    assert result["errors"] == {"base": "no_active_stations"}


async def test_user_flow_duplicate_station_aborts(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Adding an already configured station aborts with already_configured."""
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: SAMPLE_TOKEN}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "101"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_and_reconfigure_flows(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Test reauth and reconfigure flows update token and reload cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="101",
        title="Santa Cruz - Tomé Cano (SC_TC)",
        data={
            CONF_ACCESS_TOKEN: "old-token",
            CONF_STATION_ID: 101,
            CONF_STATION_NAME: "Santa Cruz - Tomé Cano",
            CONF_STATION_TAG: "SC_TC",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Reauth
    reauth = await entry.start_reauth_flow(hass)
    assert reauth["type"] is FlowResultType.FORM
    assert reauth["step_id"] == "reauth_confirm"

    reauth_res = await hass.config_entries.flow.async_configure(
        reauth["flow_id"],
        {CONF_ACCESS_TOKEN: "Bearer new-reauth-token"},
    )
    assert reauth_res["type"] is FlowResultType.ABORT
    assert reauth_res["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-reauth-token"

    # Reconfigure
    reconf = await entry.start_reconfigure_flow(hass)
    assert reconf["type"] is FlowResultType.FORM
    assert reconf["step_id"] == "reconfigure"

    reconf_res = await hass.config_entries.flow.async_configure(
        reconf["flow_id"],
        {CONF_ACCESS_TOKEN: "new-reconfigure-token"},
    )
    assert reconf_res["type"] is FlowResultType.ABORT
    assert reconf_res["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-reconfigure-token"


async def test_options_flow_with_reload(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Test OptionsFlowWithReload updates scan_interval and reloads entry cleanly."""
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

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 30},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.runtime_data.update_interval.total_seconds() == 1800
