"""Tests for CalidadAireCanariasDataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calidad_aire_canarias.api import (
    CalidadAireCanariasApiClient,
    CalidadAireCanariasAuthError,
    CalidadAireCanariasConnectionError,
    CalidadAireCanariasError,
    CalidadAireCanariasRateLimitError,
)
from custom_components.calidad_aire_canarias.const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_TAG,
    DOMAIN,
)
from custom_components.calidad_aire_canarias.coordinator import (
    CalidadAireCanariasDataUpdateCoordinator,
)

from .conftest import (
    SAMPLE_ICA_PAYLOAD,
    SAMPLE_REALTIME_RECORDS,
    SAMPLE_STATION_DETAIL,
    SAMPLE_TOKEN,
)


def _create_entry(hass: HomeAssistant, scan_interval: int = 60) -> MockConfigEntry:
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
        options={CONF_SCAN_INTERVAL: scan_interval},
    )
    entry.add_to_hass(hass)
    return entry


def _mock_client() -> AsyncMock:
    client = AsyncMock(spec=CalidadAireCanariasApiClient)
    client.async_get_station_detail = AsyncMock(return_value=SAMPLE_STATION_DETAIL)
    client.async_get_station_ica = AsyncMock(return_value=SAMPLE_ICA_PAYLOAD)
    client.async_get_realtime_datasets = AsyncMock(return_value=SAMPLE_REALTIME_RECORDS)
    return client


async def test_coordinator_parses_ica_realtime_fallback_and_avoids_no_false_match(
    hass: HomeAssistant,
) -> None:
    """Verify full station data building, PM2.5 ICA fallback, and HCNM non-matching with NO."""
    entry = _create_entry(hass)
    client = _mock_client()
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    data = await coordinator._async_update_data()

    assert data.station_id == 101
    assert data.overall_ica == "Regular"
    assert data.dominant_parameter == "PM10"
    assert data.ica_date == "2026-11-20"
    assert data.ica_period == 14

    # Parameter 99 ('Desconocida') must be filtered out
    assert 99 not in data.parameters_metadata

    # PM10 picks latest period (14 -> 42.5, not period 13 -> 38.0)
    assert data.readings[1].value == 42.5
    assert data.readings[1].period == 14
    assert data.readings[1].ica_category == "Regular"

    # PM2.5 has no realtime record, so it falls back to ICA measurementValue (15.2)
    assert data.parameters_metadata[2].description == "Partículas PM2.5"
    assert data.readings[2].value == 15.2
    assert data.readings[2].ica_category == "Razonablemente buena"

    # HCNM ("Hidrocarburos no metánicos") must NOT falsely match ICA parameter "NO"
    assert data.readings[6].value == 11.3
    assert data.readings[6].ica_category is None

    # Second update reuses cached station_detail
    await coordinator._async_update_data()
    assert client.async_get_station_detail.await_count == 1


async def test_coordinator_ignores_nan_and_malformed_values(hass: HomeAssistant) -> None:
    """Non-finite or invalid numbers must not crash the coordinator update."""
    entry = _create_entry(hass)
    client = _mock_client()
    client.async_get_realtime_datasets = AsyncMock(
        return_value=[
            {"parameterId": 1, "temporalValue": float("nan"), "date": "2026-11-20", "period": 15},
            {"parameterId": 1, "temporalValue": "not-a-number", "date": "2026-11-20", "period": 15},
            {"parameterId": 1, "temporalValue": 25.0, "date": "2026-11-20", "period": 14},
            {"parameterId": "bad", "temporalValue": 10.0, "date": "2026-11-20", "period": 14},
        ]
    )
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    data = await coordinator._async_update_data()
    assert data.readings[1].value == 25.0


async def test_coordinator_raises_update_failed_when_both_endpoints_fail(
    hass: HomeAssistant,
) -> None:
    """When both ICA and realtime fail with API errors, raise UpdateFailed instead of empty data."""
    entry = _create_entry(hass)
    client = _mock_client()
    client.async_get_station_ica = AsyncMock(side_effect=CalidadAireCanariasError("ICA 400"))
    client.async_get_realtime_datasets = AsyncMock(
        side_effect=CalidadAireCanariasError("Realtime 400")
    )
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_update_failed_when_realtime_fails_and_no_ica(
    hass: HomeAssistant,
) -> None:
    """When ICA returns None (404) and realtime fails, raise UpdateFailed."""
    entry = _create_entry(hass)
    client = _mock_client()
    client.async_get_station_ica = AsyncMock(return_value=None)
    client.async_get_realtime_datasets = AsyncMock(
        side_effect=CalidadAireCanariasError("Realtime 400")
    )
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_auth_and_connection_errors(hass: HomeAssistant) -> None:
    """AuthError raises ConfigEntryAuthFailed; ConnectionError raises UpdateFailed."""
    entry = _create_entry(hass)
    client = _mock_client()
    client.async_get_station_ica = AsyncMock(side_effect=CalidadAireCanariasAuthError("401"))
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    client.async_get_station_ica = AsyncMock(
        side_effect=CalidadAireCanariasConnectionError("timeout")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_rate_limit_backoff_and_recovery(hass: HomeAssistant) -> None:
    """Verify 429 backoff (with and without Retry-After) and interval restoration on recovery."""
    entry = _create_entry(hass, scan_interval=60)
    client = _mock_client()
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    # 1. With Retry-After header
    client.async_get_station_ica = AsyncMock(
        side_effect=CalidadAireCanariasRateLimitError("429", retry_after=900)
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=900)
    assert coordinator.get_diagnostics()["rate_limit_active"] is True

    # 2. Without Retry-After header -> doubles current interval (900 -> 1800)
    client.async_get_station_ica = AsyncMock(
        side_effect=CalidadAireCanariasRateLimitError("429", retry_after=None)
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=1800)

    # 3. Recovery restores default interval (60 min = 3600 s)
    client.async_get_station_ica = AsyncMock(return_value=SAMPLE_ICA_PAYLOAD)
    await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(minutes=60)
    assert coordinator.get_diagnostics()["rate_limit_active"] is False


async def test_coordinator_manual_refresh_cooldown(hass: HomeAssistant) -> None:
    """Verify manual refresh enforces cooldown and raises translated HomeAssistantError."""
    entry = _create_entry(hass)
    client = _mock_client()
    coordinator = CalidadAireCanariasDataUpdateCoordinator(hass, entry, client, 101)

    await coordinator.async_manual_refresh()
    assert client.async_get_station_ica.await_count == 1

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_manual_refresh()
    assert err.value.translation_key == "refresh_cooldown"
