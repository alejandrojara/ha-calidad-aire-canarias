"""Shared pytest fixtures for Calidad del Aire - Gobierno de Canarias tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

SAMPLE_TOKEN = "test-secret-token-12345"

SAMPLE_STATIONS: list[dict[str, Any]] = [
    {
        "id": 101,
        "name": "Santa Cruz - Tomé Cano",
        "tag": "SC_TC",
        "cnac": "38038001",
        "zoneId": 1,
        "active": True,
    },
    {
        "id": 102,
        "name": "Las Palmas - Parque San Telmo",
        "tag": "LP_ST",
        "cnac": "35016002",
        "zoneId": 2,
        "active": True,
    },
    {
        "id": 199,
        "name": "Estación Histórica Cerrada",
        "tag": "OLD",
        "cnac": "38000999",
        "zoneId": 1,
        "active": False,
    },
]

SAMPLE_STATION_DETAIL: dict[str, Any] = {
    "id": 101,
    "name": "Santa Cruz - Tomé Cano",
    "tag": "SC_TC",
    "cnac": "38038001",
    "zoneId": 1,
    "active": True,
    "coordinates": {
        "latitude": 28.4636,
        "longitude": -16.2518,
        "altitude": 42.0,
    },
    "parameters": [
        {
            "tag": "PM10",
            "description": "Partículas PM10",
            "parameter": {"id": 1, "name": "PM10", "description": "Partículas PM10"},
            "unit": {"symbol": "ug/m3", "name": "Microgramos por metro cúbico"},
        },
        {
            "tag": "PM2,5",
            "description": "Desconocida",
            "parameter": {"id": 2, "name": "PM2.5", "description": "Desconocida"},
            "unit": {"symbol": "µg/m³", "name": "Microgramos por metro cúbico"},
        },
        {
            "tag": "NO2",
            "description": "Dióxido de nitrógeno",
            "parameter": {"id": 3, "name": "NO2", "description": "Dióxido de nitrógeno"},
            "unit": {"symbol": "µg/m³", "name": "Microgramos por metro cúbico"},
        },
        {
            "tag": "CO",
            "description": "Monóxido de carbono",
            "parameter": {"id": 4, "name": "CO", "description": "Monóxido de carbono"},
            "unit": {"symbol": "mg/m³", "name": "Miligramos por metro cúbico"},
        },
        {
            "tag": "C7H8",
            "description": "Tolueno",
            "parameter": {"id": 5, "name": "C7H8", "description": "Tolueno"},
            "unit": {"symbol": "µg/m³", "name": "Microgramos por metro cúbico"},
        },
        {
            "tag": "HCNM",
            "description": "Hidrocarburos no metánicos",
            "parameter": {
                "id": 6,
                "name": "HCNM",
                "description": "Hidrocarburos no metánicos",
            },
            "unit": {"symbol": "µg/m³", "name": "Microgramos por metro cúbico"},
        },
        {
            "tag": "HR",
            "description": "Humedad relativa",
            "parameter": {"id": 7, "name": "HR", "description": "Humedad relativa"},
            "unit": {"symbol": "%", "name": "Porcentaje"},
        },
        {
            "tag": "DV",
            "description": "Dirección del viento",
            "parameter": {"id": 8, "name": "DV", "description": "Dirección del viento"},
            "unit": {"symbol": "º", "name": "Grados"},
        },
        {
            "tag": "CAL",
            "description": "Cobertura de datos",
            "parameter": {"id": 9, "name": "CAL", "description": "Cobertura de datos"},
            "unit": {"symbol": "%", "name": "Porcentaje"},
        },
        {
            "tag": "SOL",
            "description": "Elevación solar",
            "parameter": {"id": 10, "name": "SOL", "description": "Elevación solar"},
            "unit": {"symbol": "°", "name": "Grados"},
        },
        {
            "tag": "Desconocida",
            "description": "Desconocida",
            "parameter": {"id": 99, "name": "Desconocida", "description": "Desconocida"},
            "unit": {"symbol": "-", "name": "Desconocida"},
        },
    ],
}

SAMPLE_ICA_PAYLOAD: dict[str, Any] = {
    "stationId": 101,
    "parameters": [
        {
            "parameter": "PM10",
            "ica": "regular",
            "date": "2026-11-20",
            "period": 14,
            "measurementValue": 42.5,
        },
        {
            "parameter": "NO2",
            "ica": "Buena",
            "date": "2026-11-20",
            "period": 14,
            "measurementValue": 18.0,
        },
        {
            "parameter": "NO",
            "ica": "Buena",
            "date": "2026-11-20",
            "period": 14,
            "measurementValue": 5.0,
        },
        {
            "parameter": "PM2,5",
            "ica": "Razonablemente buena",
            "date": "2026-11-20",
            "period": 14,
            "measurementValue": 15.2,
        },
    ],
}

SAMPLE_REALTIME_RECORDS: list[dict[str, Any]] = [
    {
        "parameterId": 1,
        "temporalValue": 38.0,
        "date": "2026-11-20",
        "period": 13,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 1,
        "temporalValue": 42.5,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 3,
        "temporalValue": 18.0,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 4,
        "temporalValue": 0.4,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 5,
        "temporalValue": 2.1,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 6,
        "temporalValue": 11.3,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 7,
        "temporalValue": 64.0,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 8,
        "temporalValue": 210.0,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 9,
        "temporalValue": 98.0,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
    {
        "parameterId": 10,
        "temporalValue": 45.0,
        "date": "2026-11-20",
        "period": 14,
        "temporalFlag": {"value": "V"},
    },
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in Home Assistant for all tests."""
    return


@pytest.fixture
def mock_api_client() -> Generator[dict[str, AsyncMock]]:
    """Patch CalidadAireCanariasApiClient methods so tests never hit external networks."""
    active_only = [s for s in SAMPLE_STATIONS if s["active"]]
    with (
        patch(
            "custom_components.calidad_aire_canarias.api.CalidadAireCanariasApiClient.async_get_stations",
            AsyncMock(return_value=active_only),
        ) as mock_stations,
        patch(
            "custom_components.calidad_aire_canarias.api.CalidadAireCanariasApiClient.async_get_station_detail",
            AsyncMock(return_value=SAMPLE_STATION_DETAIL),
        ) as mock_detail,
        patch(
            "custom_components.calidad_aire_canarias.api.CalidadAireCanariasApiClient.async_get_station_ica",
            AsyncMock(return_value=SAMPLE_ICA_PAYLOAD),
        ) as mock_ica,
        patch(
            "custom_components.calidad_aire_canarias.api.CalidadAireCanariasApiClient.async_get_realtime_datasets",
            AsyncMock(return_value=SAMPLE_REALTIME_RECORDS),
        ) as mock_realtime,
    ):
        yield {
            "stations": mock_stations,
            "detail": mock_detail,
            "ica": mock_ica,
            "realtime": mock_realtime,
        }
