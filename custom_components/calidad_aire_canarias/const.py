"""Constants for the Calidad del Aire - Gobierno de Canarias integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "calidad_aire_canarias"
MANUFACTURER: Final = "Gobierno de Canarias"
MODEL: Final = "Red de Control y Vigilancia de la Calidad del Aire"

BASE_URL: Final = (
    "https://www3.gobiernodecanarias.org/calidadambiental/calidadaire/anemo"
)

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_STATION_TAG: Final = "station_tag"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES: Final = 60
MIN_SCAN_INTERVAL_MINUTES: Final = 15
MAX_SCAN_INTERVAL_MINUTES: Final = 240
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

# Ventana en horas (alineada a hora UTC en punto) para consultar /api/v1/datasets/realtime.
# Usar 12 horas garantiza estar siempre dentro del límite de 24h y reduce el coste de consulta.
DEFAULT_REALTIME_LOOKBACK_HOURS: Final = 12

DEFAULT_TIMEOUT: Final = 30

# Categorías estándar del Índice de Calidad del Aire (ICA) nacional/europeo
ICA_CATEGORIES: Final[list[str]] = [
    "Buena",
    "Razonablemente buena",
    "Regular",
    "Desfavorable",
    "Muy desfavorable",
    "Extremadamente desfavorable",
    "Sin datos",
]

# Mapa de normalización de nombres de categoría ICA
ICA_DISPLAY_NAMES: Final[dict[str, str]] = {
    "buena": "Buena",
    "razonablemente buena": "Razonablemente buena",
    "regular": "Regular",
    "desfavorable": "Desfavorable",
    "muy desfavorable": "Muy desfavorable",
    "extremadamente desfavorable": "Extremadamente desfavorable",
    "sin datos": "Sin datos",
}

# Orden de severidad (de mejor a peor calidad) para calcular el ICA global de la estación
ICA_SEVERITY_ORDER: Final[dict[str, int]] = {
    "sin datos": 0,
    "buena": 1,
    "razonablemente buena": 2,
    "regular": 3,
    "desfavorable": 4,
    "muy desfavorable": 5,
    "extremadamente desfavorable": 6,
}
