"""Button platform for Calidad del Aire - Gobierno de Canarias."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    CalidadAireCanariasConfigEntry,
    CalidadAireCanariasDataUpdateCoordinator,
)
from .entity import CalidadAireCanariasEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalidadAireCanariasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up manual refresh button for a configured monitoring station."""
    coordinator = entry.runtime_data
    async_add_entities([CalidadAireCanariasRefreshButton(coordinator)])


class CalidadAireCanariasRefreshButton(CalidadAireCanariasEntity, ButtonEntity):
    """Button triggering a cooldown-protected on-demand station refresh."""

    _attr_icon = "mdi:refresh"
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: CalidadAireCanariasDataUpdateCoordinator,
    ) -> None:
        """Initialize the refresh button."""
        super().__init__(coordinator)
        station_id = coordinator.data.station_id
        self._attr_unique_id = f"{station_id}_refresh"

    async def async_press(self) -> None:
        """Handle manual refresh button press."""
        await self.coordinator.async_manual_refresh()
