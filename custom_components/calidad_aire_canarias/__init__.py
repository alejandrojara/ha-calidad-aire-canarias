"""The Calidad del Aire - Gobierno de Canarias integration."""

from __future__ import annotations

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CalidadAireCanariasApiClient
from .const import CONF_STATION_ID
from .coordinator import (
    CalidadAireCanariasConfigEntry,
    CalidadAireCanariasDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: CalidadAireCanariasConfigEntry
) -> bool:
    """Set up Calidad del Aire - Gobierno de Canarias from a config entry."""
    session = async_get_clientsession(hass)
    client = CalidadAireCanariasApiClient(
        session=session,
        token=entry.data[CONF_ACCESS_TOKEN],
    )
    station_id = int(entry.data[CONF_STATION_ID])

    coordinator = CalidadAireCanariasDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        station_id=station_id,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CalidadAireCanariasConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: CalidadAireCanariasConfigEntry
) -> None:
    """Reload config entry when options or credentials are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
