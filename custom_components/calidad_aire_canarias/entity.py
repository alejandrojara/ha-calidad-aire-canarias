"""Base entity for Calidad del Aire - Gobierno de Canarias."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, PORTAL_URL
from .coordinator import CalidadAireCanariasDataUpdateCoordinator


class CalidadAireCanariasEntity(CoordinatorEntity[CalidadAireCanariasDataUpdateCoordinator]):
    """Base entity class for a Canary Islands Air Quality monitoring station."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CalidadAireCanariasDataUpdateCoordinator,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        station_data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(station_data.station_id))},
            name=station_data.station_name or f"Estación {station_data.station_id}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=station_data.cnac or station_data.station_tag or None,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PORTAL_URL,
        )
