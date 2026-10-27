"""Sensor platform for Calidad del Aire - Gobierno de Canarias."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import (
    CalidadAireCanariasConfigEntry,
    CalidadAireCanariasDataUpdateCoordinator,
    ParameterMetadata,
    ParameterReading,
)

_LOGGER = logging.getLogger(__name__)

# Normalización de símbolos de unidades devueltos por la API a constantes de Home Assistant
UNIT_NORMALIZATION: dict[str, str] = {
    "ug/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ug/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "µg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "µg/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "μg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "μg/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "mg/m3": CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    "mg/m³": CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    "ppm": CONCENTRATION_PARTS_PER_MILLION,
    "ºc": UnitOfTemperature.CELSIUS,
    "°c": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "m/s": UnitOfSpeed.METERS_PER_SECOND,
    "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "hpa": UnitOfPressure.HPA,
    "mbar": UnitOfPressure.MBAR,
    "w/m2": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "w/m²": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "mm": UnitOfPrecipitationDepth.MILLIMETERS,
    "l/m2": UnitOfPrecipitationDepth.MILLIMETERS,
    "l/m²": UnitOfPrecipitationDepth.MILLIMETERS,
    "º": DEGREE,
    "°": DEGREE,
    "grados": DEGREE,
}


@dataclass(frozen=True)
class PollutantClassRule:
    """Mapping rule from parameter code/name to HA SensorDeviceClass and icon."""

    device_class: SensorDeviceClass | None
    required_unit: str | None
    icon: str


POLLUTANT_RULES: dict[str, PollutantClassRule] = {
    "PM10": PollutantClassRule(
        device_class=SensorDeviceClass.PM10,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur",
    ),
    "PM2.5": PollutantClassRule(
        device_class=SensorDeviceClass.PM25,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur-radial",
    ),
    "PM2,5": PollutantClassRule(
        device_class=SensorDeviceClass.PM25,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur-radial",
    ),
    "PM25": PollutantClassRule(
        device_class=SensorDeviceClass.PM25,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur-radial",
    ),
    "PM1": PollutantClassRule(
        device_class=SensorDeviceClass.PM1,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur-linear",
    ),
    "NO2": PollutantClassRule(
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:smog",
    ),
    "NO": PollutantClassRule(
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:smog",
    ),
    "NOX": PollutantClassRule(
        device_class=None,
        required_unit=None,
        icon="mdi:smog",
    ),
    "SO2": PollutantClassRule(
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:chemical-weapon",
    ),
    "O3": PollutantClassRule(
        device_class=SensorDeviceClass.OZONE,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:weather-sunny-alert",
    ),
    "CO": PollutantClassRule(
        device_class=SensorDeviceClass.CO,
        required_unit=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:molecule-co",
    ),
    "C6H6": PollutantClassRule(
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        required_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:hexagon-outline",
    ),
    "SH2": PollutantClassRule(
        device_class=None,
        required_unit=None,
        icon="mdi:scent",
    ),
    "H2S": PollutantClassRule(
        device_class=None,
        required_unit=None,
        icon="mdi:scent",
    ),
    "NH3": PollutantClassRule(
        device_class=None,
        required_unit=None,
        icon="mdi:chemical-weapon",
    ),
}


def _normalize_unit(raw_symbol: str | None) -> str | None:
    """Normalize unit symbols from the API to standard Home Assistant units."""
    if not raw_symbol:
        return None
    cleaned = raw_symbol.strip()
    return UNIT_NORMALIZATION.get(cleaned.lower(), cleaned)


def _resolve_sensor_classification(
    meta: ParameterMetadata, normalized_unit: str | None
) -> tuple[SensorDeviceClass | None, SensorStateClass, str]:
    """Determine the appropriate SensorDeviceClass, SensorStateClass, and icon."""
    candidates = [
        meta.name.strip().upper(),
        meta.station_param_tag.strip().upper(),
    ]
    for code in candidates:
        if code in POLLUTANT_RULES:
            rule = POLLUTANT_RULES[code]
            if (
                rule.device_class is not None
                and rule.required_unit is not None
                and normalized_unit == rule.required_unit
            ):
                return (
                    rule.device_class,
                    SensorStateClass.MEASUREMENT,
                    rule.icon,
                )
            return None, SensorStateClass.MEASUREMENT, rule.icon

    if normalized_unit == UnitOfTemperature.CELSIUS:
        return (
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            "mdi:thermometer",
        )
    if normalized_unit == PERCENTAGE:
        return (
            SensorDeviceClass.HUMIDITY,
            SensorStateClass.MEASUREMENT,
            "mdi:water-percent",
        )
    if normalized_unit in (
        UnitOfSpeed.METERS_PER_SECOND,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
    ):
        return (
            SensorDeviceClass.WIND_SPEED,
            SensorStateClass.MEASUREMENT,
            "mdi:weather-windy",
        )
    if normalized_unit in (UnitOfPressure.HPA, UnitOfPressure.MBAR):
        return (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            SensorStateClass.MEASUREMENT,
            "mdi:gauge",
        )
    if normalized_unit == UnitOfIrradiance.WATTS_PER_SQUARE_METER:
        return (
            SensorDeviceClass.IRRADIANCE,
            SensorStateClass.MEASUREMENT,
            "mdi:white-balance-sunny",
        )
    if normalized_unit == UnitOfPrecipitationDepth.MILLIMETERS:
        return (
            SensorDeviceClass.PRECIPITATION,
            SensorStateClass.MEASUREMENT,
            "mdi:weather-rainy",
        )
    if normalized_unit == DEGREE:
        return (
            SensorDeviceClass.WIND_DIRECTION,
            SensorStateClass.MEASUREMENT_ANGLE,
            "mdi:compass-outline",
        )

    return None, SensorStateClass.MEASUREMENT, "mdi:chemical-weapon"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalidadAireCanariasConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Calidad del Aire Canarias sensors based on a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    station_id = data.station_id

    # Limpiar entidades huérfanas o 'Desconocida' registradas previamente en el Entity Registry
    valid_unique_ids: set[str] = {f"{station_id}_ica"} | {
        f"{station_id}_param_{param_id}"
        for param_id in data.parameters_metadata
    }
    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        ent_reg, entry.entry_id
    ):
        if entity_entry.unique_id not in valid_unique_ids:
            _LOGGER.info(
                "Eliminando entidad obsoleta o sin identificar del registro: %s (%s)",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)

    entities: list[SensorEntity] = [
        CalidadAireCanariasIcaSensor(coordinator),
    ]

    for param_id, meta in data.parameters_metadata.items():
        entities.append(
            CalidadAireCanariasParameterSensor(
                coordinator=coordinator,
                parameter_id=param_id,
                metadata=meta,
            )
        )

    async_add_entities(entities)


class CalidadAireCanariasBaseSensor(
    CoordinatorEntity[CalidadAireCanariasDataUpdateCoordinator], SensorEntity
):
    """Base sensor class for Calidad del Aire - Gobierno de Canarias."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CalidadAireCanariasDataUpdateCoordinator,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        station_data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(station_data.station_id))},
            name=station_data.station_name
            or f"Estación {station_data.station_id}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=station_data.cnac or station_data.station_tag or None,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www3.gobiernodecanarias.org/calidadambiental/calidadaire/",
        )


class CalidadAireCanariasIcaSensor(CalidadAireCanariasBaseSensor):
    """Sensor representing the overall Air Quality Index (ICA) of the station."""

    _attr_translation_key = "station_ica"
    _attr_icon = "mdi:air-filter"

    def __init__(
        self,
        coordinator: CalidadAireCanariasDataUpdateCoordinator,
    ) -> None:
        """Initialize the station ICA sensor."""
        super().__init__(coordinator)
        station_id = coordinator.data.station_id
        self._attr_unique_id = f"{station_id}_ica"
        self.entity_description = SensorEntityDescription(
            key="ica",
            translation_key="station_ica",
            name="Índice de Calidad del Aire (ICA)",
            icon="mdi:air-filter",
        )

    @property
    def native_value(self) -> str | None:
        """Return the current textual ICA category of the station."""
        return self.coordinator.data.overall_ica

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for the station ICA."""
        data = self.coordinator.data
        return {
            "station_id": data.station_id,
            "station_tag": data.station_tag,
            "cnac": data.cnac,
            "zone_id": data.zone_id,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "altitude": data.altitude,
            "dominant_parameter": data.dominant_parameter,
            "date": data.ica_date,
            "period": data.ica_period,
            "parameters_ica": data.ica_by_parameter,
        }


class CalidadAireCanariasParameterSensor(CalidadAireCanariasBaseSensor):
    """Sensor for an individual pollutant or parameter measured at the station."""

    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: CalidadAireCanariasDataUpdateCoordinator,
        parameter_id: int,
        metadata: ParameterMetadata,
    ) -> None:
        """Initialize the pollutant/parameter sensor."""
        super().__init__(coordinator)
        self._parameter_id = parameter_id
        self._metadata = metadata

        station_id = coordinator.data.station_id
        self._attr_unique_id = f"{station_id}_param_{parameter_id}"

        normalized_unit = _normalize_unit(metadata.unit_symbol)
        device_class, state_class, icon = _resolve_sensor_classification(
            metadata, normalized_unit
        )

        # Construimos un nombre descriptivo combinando descripción y código si difieren
        display_name = metadata.description.strip()
        short_name = metadata.name.strip()
        if (
            short_name
            and short_name.upper() not in display_name.upper()
            and display_name.upper() != short_name.upper()
        ):
            sensor_name = f"{display_name} ({short_name})"
        else:
            sensor_name = display_name or short_name

        self._attr_name = sensor_name
        self._attr_native_unit_of_measurement = normalized_unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon

    @property
    def _reading(self) -> ParameterReading | None:
        """Return the latest reading for this parameter."""
        return self.coordinator.data.readings.get(self._parameter_id)

    @property
    def native_value(self) -> float | None:
        """Return the latest hourly value of the parameter."""
        reading = self._reading
        if reading is None:
            return None
        return reading.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed metadata and reading attributes."""
        reading = self._reading
        attrs: dict[str, Any] = {
            "parameter_id": self._parameter_id,
            "parameter_code": self._metadata.name,
            "parameter_description": self._metadata.description,
            "station_parameter_tag": self._metadata.station_param_tag,
            "unit_name": self._metadata.unit_name,
        }
        if reading is not None:
            attrs["date"] = reading.date
            attrs["period"] = reading.period
            attrs["temporal_flag"] = reading.flag
            if reading.ica_category is not None:
                attrs["ica_category"] = reading.ica_category
            if reading.ica_measurement_value is not None:
                attrs["ica_measurement_value"] = reading.ica_measurement_value
        return attrs
