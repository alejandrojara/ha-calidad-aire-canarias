"""DataUpdateCoordinator for Calidad del Aire - Gobierno de Canarias."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    CalidadAireCanariasApiClient,
    CalidadAireCanariasAuthError,
    CalidadAireCanariasConnectionError,
    CalidadAireCanariasError,
    CalidadAireCanariasRateLimitError,
)
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    ICA_DISPLAY_NAMES,
    ICA_SEVERITY_ORDER,
)

_LOGGER = logging.getLogger(__name__)

# Textos de marcador de posición devueltos por la API para canales no asignados o sin nombre
INVALID_PARAMETER_LABELS: set[str] = {
    "",
    "-",
    "desconocida",
    "desconocido",
    "unknown",
    "sin nombre",
    "sin descripción",
    "sin descripcion",
    "sin datos",
    "n/a",
    "na",
    "null",
    "none",
}

# Nombres descriptivos estándar por código de parámetro en caso de que la API devuelva "Desconocida" en description
KNOWN_PARAMETER_DESCRIPTIONS: dict[str, str] = {
    "SO2": "Dióxido de azufre",
    "NO2": "Dióxido de nitrógeno",
    "NO": "Monóxido de nitrógeno",
    "NOX": "Óxidos de nitrógeno",
    "PM10": "Partículas PM10",
    "PM2.5": "Partículas PM2.5",
    "PM2,5": "Partículas PM2.5",
    "PM25": "Partículas PM2.5",
    "PM1": "Partículas PM1",
    "O3": "Ozono",
    "CO": "Monóxido de carbono",
    "C6H6": "Benceno",
    "C7H8": "Tolueno",
    "C8H10": "Xileno",
    "SH2": "Ácido sulfhídrico",
    "H2S": "Ácido sulfhídrico",
    "NH3": "Amoníaco",
    "CH4": "Metano",
    "HCNM": "Hidrocarburos no metánicos",
    "HCT": "Hidrocarburos totales",
    "VV": "Velocidad del viento",
    "DV": "Dirección del viento",
    "TMP": "Temperatura",
    "TEMP": "Temperatura",
    "HR": "Humedad relativa",
    "PRB": "Presión barométrica",
    "PRES": "Presión atmosférica",
    "RS": "Radiación solar",
    "LL": "Precipitación",
    "PREC": "Precipitación",
}


def _clean_label(value: Any) -> str:
    """Return stripped label or empty string if it is a placeholder like 'Desconocida'."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in INVALID_PARAMETER_LABELS:
        return ""
    return text


@dataclass
class ParameterMetadata:
    """Metadata of a parameter measured by a station."""

    parameter_id: int
    name: str
    description: str
    station_param_tag: str
    station_param_description: str
    unit_symbol: str | None
    unit_name: str | None


@dataclass
class ParameterReading:
    """Latest hourly reading for a parameter."""

    parameter_id: int
    value: float | None
    date: str | None = None
    period: int | None = None
    flag: str | None = None
    ica_category: str | None = None
    ica_measurement_value: float | None = None


@dataclass
class StationAirQualityData:
    """Aggregated data returned by the coordinator."""

    station_id: int
    station_name: str
    station_tag: str
    cnac: str | None
    zone_id: int | None
    latitude: float | None
    longitude: float | None
    altitude: float | None
    active: bool
    parameters_metadata: dict[int, ParameterMetadata] = field(
        default_factory=dict
    )
    readings: dict[int, ParameterReading] = field(default_factory=dict)
    overall_ica: str | None = None
    dominant_parameter: str | None = None
    ica_date: str | None = None
    ica_period: int | None = None
    ica_by_parameter: dict[str, dict[str, Any]] = field(default_factory=dict)


type CalidadAireCanariasConfigEntry = ConfigEntry[
    CalidadAireCanariasDataUpdateCoordinator
]


def _normalize_pollutant_token(value: str) -> str:
    """Normalize pollutant code/name for comparison (e.g. 'PM2,5' -> 'PM2.5')."""
    cleaned = value.strip().upper().replace(",", ".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned == "PM25":
        return "PM2.5"
    return cleaned


def _normalize_ica_category(raw_ica: str | None) -> str | None:
    """Normalize ICA textual category to clean display casing."""
    if not raw_ica:
        return None
    cleaned = raw_ica.strip()
    if not cleaned:
        return None
    return ICA_DISPLAY_NAMES.get(cleaned.lower(), cleaned)


class CalidadAireCanariasDataUpdateCoordinator(
    DataUpdateCoordinator[StationAirQualityData]
):
    """Coordinator to manage fetching air quality data from Gobierno de Canarias API."""

    config_entry: CalidadAireCanariasConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CalidadAireCanariasConfigEntry,
        client: CalidadAireCanariasApiClient,
        station_id: int,
    ) -> None:
        """Initialize the coordinator."""
        scan_minutes = int(
            entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
            )
        )
        self._default_interval = timedelta(minutes=scan_minutes)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{station_id}",
            update_interval=self._default_interval,
        )
        self.client = client
        self.station_id = station_id
        self._station_detail: dict[str, Any] | None = None

    async def _async_update_data(self) -> StationAirQualityData:
        """Fetch station detail (if needed), current ICA, and realtime measurements."""
        try:
            if self._station_detail is None:
                self._station_detail = (
                    await self.client.async_get_station_detail(self.station_id)
                )

            parameters_meta = self._parse_parameters_metadata(
                self._station_detail
            )
            parameter_ids = list(parameters_meta.keys())

            # 1. Consultamos el ICA actual de la estación
            ica_payload = await self.client.async_get_station_ica(
                self.station_id
            )

            # 2. Consultamos los datos temporales horarios de las últimas horas (alineadas a UTC)
            realtime_records: list[dict[str, Any]] = []
            if parameter_ids:
                try:
                    realtime_records = (
                        await self.client.async_get_realtime_datasets(
                            station_id=self.station_id,
                            parameter_ids=parameter_ids,
                        )
                    )
                except (
                    CalidadAireCanariasAuthError,
                    CalidadAireCanariasRateLimitError,
                    CalidadAireCanariasConnectionError,
                ):
                    raise
                except CalidadAireCanariasError as err:
                    _LOGGER.warning(
                        "No se pudieron obtener los datasets en tiempo real para la estación %s (%s). "
                        "Se utilizarán los datos disponibles de ICA.",
                        self.station_id,
                        err,
                    )

            # Si el intervalo había sido incrementado por un HTTP 429 previo, lo restauramos
            if self.update_interval != self._default_interval:
                self.update_interval = self._default_interval

        except CalidadAireCanariasAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Error de autenticación Bearer con la API de Calidad del Aire: {err}"
            ) from err
        except CalidadAireCanariasRateLimitError as err:
            if err.retry_after:
                self.update_interval = timedelta(
                    seconds=max(err.retry_after, 60)
                )
            raise UpdateFailed(
                f"Límite de tasa superado (HTTP 429). Reintentar tras {err.retry_after or 3600}s: {err}"
            ) from err
        except CalidadAireCanariasError as err:
            raise UpdateFailed(
                f"Error comunicando con la API de Calidad del Aire de Canarias: {err}"
            ) from err

        return self._build_station_data(
            self._station_detail,
            parameters_meta,
            ica_payload,
            realtime_records,
        )

    @staticmethod
    def _parse_parameters_metadata(
        station_detail: dict[str, Any],
    ) -> dict[int, ParameterMetadata]:
        """Extract parameter definitions from StationDetailV1Response, skipping invalid/unknown placeholders."""
        metadata: dict[int, ParameterMetadata] = {}
        raw_params = station_detail.get("parameters") or []
        for item in raw_params:
            if not isinstance(item, dict):
                continue
            param_obj = item.get("parameter") or {}
            unit_obj = item.get("unit") or {}
            param_id = param_obj.get("id")
            if param_id is None:
                continue
            param_id_int = int(param_id)

            raw_name = _clean_label(param_obj.get("name"))
            raw_desc = _clean_label(param_obj.get("description"))
            item_tag = _clean_label(item.get("tag"))
            item_desc = _clean_label(item.get("description"))

            # Determinamos el código/nombre corto del parámetro
            param_name = raw_name or item_tag or item_desc
            if not param_name:
                _LOGGER.debug(
                    "Omitiendo parámetro sin nombre válido o marcado como 'Desconocida' (id=%s)",
                    param_id_int,
                )
                continue

            # Determinamos la descripción legible, usando el catálogo estándar si la API devolvió 'Desconocida'
            known_desc = KNOWN_PARAMETER_DESCRIPTIONS.get(
                param_name.upper()
            ) or KNOWN_PARAMETER_DESCRIPTIONS.get(item_tag.upper())
            param_desc = raw_desc or known_desc or item_desc or param_name

            metadata[param_id_int] = ParameterMetadata(
                parameter_id=param_id_int,
                name=param_name,
                description=param_desc,
                station_param_tag=item_tag or param_name,
                station_param_description=item_desc or param_desc,
                unit_symbol=_clean_label(unit_obj.get("symbol")) or None,
                unit_name=_clean_label(unit_obj.get("name")) or None,
            )
        return metadata

    @classmethod
    def _build_station_data(
        cls,
        station_detail: dict[str, Any],
        parameters_meta: dict[int, ParameterMetadata],
        ica_payload: dict[str, Any] | None,
        realtime_records: list[dict[str, Any]],
    ) -> StationAirQualityData:
        """Combine station metadata, ICA response, and latest realtime readings."""
        coords = station_detail.get("coordinates") or {}

        # Procesar el ICA por parámetro y determinar el ICA global de la estación
        ica_by_parameter: dict[str, dict[str, Any]] = {}
        overall_ica: str | None = None
        dominant_parameter: str | None = None
        ica_date: str | None = None
        ica_period: int | None = None
        max_severity = -1

        if isinstance(ica_payload, dict):
            for ica_item in ica_payload.get("parameters") or []:
                if not isinstance(ica_item, dict):
                    continue
                param_key = str(ica_item.get("parameter") or "").strip()
                raw_ica_cat = str(ica_item.get("ica") or "").strip()
                ica_cat = _normalize_ica_category(raw_ica_cat)
                item_date = ica_item.get("date")
                item_period = ica_item.get("period")
                measurement_val = ica_item.get("measurementValue")

                if not param_key:
                    continue

                ica_by_parameter[param_key] = {
                    "parameter": param_key,
                    "ica": ica_cat,
                    "date": item_date,
                    "period": item_period,
                    "measurement_value": measurement_val,
                }

                if ica_cat:
                    severity = ICA_SEVERITY_ORDER.get(ica_cat.lower(), 0)
                    if severity > max_severity:
                        max_severity = severity
                        overall_ica = ica_cat
                        dominant_parameter = (
                            param_key if severity > 0 else None
                        )
                        ica_date = item_date
                        ica_period = item_period

        # Agrupar las lecturas horarias en tiempo real por parameterId y elegir la más reciente
        latest_realtime: dict[int, dict[str, Any]] = {}
        for record in realtime_records:
            if not isinstance(record, dict):
                continue
            param_id = record.get("parameterId")
            temp_val = record.get("temporalValue")
            if param_id is None or temp_val is None:
                continue
            param_id_int = int(param_id)
            rec_key = (
                str(record.get("date") or ""),
                int(record.get("period") or 0),
            )
            current = latest_realtime.get(param_id_int)
            if current is None:
                latest_realtime[param_id_int] = record
            else:
                curr_key = (
                    str(current.get("date") or ""),
                    int(current.get("period") or 0),
                )
                if rec_key >= curr_key:
                    latest_realtime[param_id_int] = record

        # Construir lecturas consolidadas para cada parámetro de la estación
        readings: dict[int, ParameterReading] = {}
        for param_id, meta in parameters_meta.items():
            rt_record = latest_realtime.get(param_id)
            matched_ica = cls._match_ica_for_parameter(meta, ica_by_parameter)

            value: float | None = None
            date_str: str | None = None
            period_int: int | None = None
            flag_str: str | None = None

            if rt_record is not None:
                raw_val = rt_record.get("temporalValue")
                value = float(raw_val) if raw_val is not None else None
                date_str = rt_record.get("date")
                period_int = rt_record.get("period")
                flag_obj = rt_record.get("temporalFlag") or {}
                flag_str = (
                    flag_obj.get("value")
                    if isinstance(flag_obj, dict)
                    else None
                )
            elif (
                matched_ica is not None
                and matched_ica.get("measurement_value") is not None
            ):
                # Fallback al valor medido reportado en el endpoint ICA si no hay registro en realtime
                value = float(matched_ica["measurement_value"])
                date_str = matched_ica.get("date")
                period_int = matched_ica.get("period")

            readings[param_id] = ParameterReading(
                parameter_id=param_id,
                value=value,
                date=date_str,
                period=period_int,
                flag=flag_str,
                ica_category=matched_ica.get("ica") if matched_ica else None,
                ica_measurement_value=(
                    float(matched_ica["measurement_value"])
                    if matched_ica
                    and matched_ica.get("measurement_value") is not None
                    else None
                ),
            )

        return StationAirQualityData(
            station_id=int(station_detail.get("id", 0)),
            station_name=str(station_detail.get("name") or ""),
            station_tag=str(station_detail.get("tag") or ""),
            cnac=station_detail.get("cnac"),
            zone_id=station_detail.get("zoneId"),
            latitude=coords.get("latitude"),
            longitude=coords.get("longitude"),
            altitude=coords.get("altitude"),
            active=bool(station_detail.get("active", True)),
            parameters_metadata=parameters_meta,
            readings=readings,
            overall_ica=overall_ica,
            dominant_parameter=dominant_parameter,
            ica_date=ica_date,
            ica_period=ica_period,
            ica_by_parameter=ica_by_parameter,
        )

    @staticmethod
    def _match_ica_for_parameter(
        meta: ParameterMetadata,
        ica_by_parameter: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Match a station parameter metadata with an ICA parameter entry if applicable."""
        candidates = {
            _normalize_pollutant_token(meta.name),
            _normalize_pollutant_token(meta.station_param_tag),
            _normalize_pollutant_token(meta.description),
        }
        for key, ica_info in ica_by_parameter.items():
            norm_key = _normalize_pollutant_token(key)
            if norm_key in candidates:
                return ica_info
            pattern = rf"(?<![A-Z0-9]){re.escape(norm_key)}(?![A-Z0-9])"
            if any(re.search(pattern, cand) for cand in candidates if cand):
                return ica_info
        return None
