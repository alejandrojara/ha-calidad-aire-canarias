# Calidad del Aire - Gobierno de Canarias (Home Assistant)

<p align="center">
  <img src="https://raw.githubusercontent.com/alejandrojara/ha-calidad-aire-canarias/main/custom_components/calidad_aire_canarias/brand/icon.png" alt="Calidad del Aire - Gobierno de Canarias" width="140" height="140" />
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/releases"><img src="https://img.shields.io/badge/version-20261027.1-blue.svg" alt="Version" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias"><img src="https://img.shields.io/badge/maintainer-%40alejandrojara-blue.svg" alt="Maintainer" /></a>
</p>

Integración personalizada (`custom_component`) para **Home Assistant** compatible con **HACS**, que consulta la **API pública de calidad del aire del Gobierno de Canarias (v1)** (`https://www3.gobiernodecanarias.org/calidadambiental/calidadaire/anemo`).

## Características

- **Autenticación mediante Bearer Token** (`HTTP Bearer`).
- **Configuración 100% desde la interfaz de usuario (Config Flow)** en dos pasos:
  1. Validación del token Bearer y descarga del catálogo de estaciones públicas.
  2. Selector desplegable con todas las estaciones activas (`active: true`) ordenadas alfabéticamente.
- **Flujo de Opciones (`OptionsFlow`)**: Permite ajustar el intervalo de sondeo (por defecto **60 minutos**, configurable entre 15 y 240 minutos) desde el botón *Configurar* de la integración.
- **Flujo de reautenticación (`reauth`)** integrado si el token caduca o es revocado.
- **Basada en `DataUpdateCoordinator`** con ventana horaria alineada a hora UTC en punto (`YYYY-MM-DDTHH:00:00Z`) y gestión automática de cabeceras `Retry-After` ante respuestas `HTTP 429`.
- **Creación dinámica y limpieza automática de sensores por estación**:
  - **Sensor de Índice de Calidad del Aire (ICA)** (`/api/v1/ica/stations/{id}`), calculando la categoría vigente de la estación, el contaminante dominante y el desglose horario por parámetro en sus atributos.
  - **Sensores para todos los contaminantes y parámetros meteorológicos disponibles** en la estación (`/api/v1/stations/{id}` + `/api/v1/datasets/realtime`), filtrando automáticamente canales no asignados (`Desconocida`) y asignando `SensorDeviceClass`, `SensorStateClass` (`MEASUREMENT` o `MEASUREMENT_ANGLE` para dirección de viento) y unidades nativas de Home Assistant (`µg/m³`, `mg/m³`, `ppm`, `°C`, `%`, `m/s`, `hPa`, `W/m²`, `mm`, `°`).
- **Iconos nativos locales en `brand/`** (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`, más variantes `dark_*`) compatibles de forma nativa con Home Assistant 2026.3+.

## Estructura del proyecto

```text
├── hacs.json
├── README.md
└── custom_components/
    └── calidad_aire_canarias/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
        ├── brand/
        │   ├── dark_icon.png
        │   ├── dark_icon@2x.png
        │   ├── dark_logo.png
        │   ├── dark_logo@2x.png
        │   ├── icon.png
        │   ├── icon@2x.png
        │   ├── logo.png
        │   └── logo@2x.png
        └── translations/
            ├── en.json
            └── es.json
```

## Instalación mediante HACS

1. Abre **HACS** en tu instancia de Home Assistant.
2. Haz clic en el menú de tres puntos (arriba a la derecha) y selecciona **Repositorios personalizados** (*Custom repositories*).
3. Añade la URL `https://github.com/alejandrojara/ha-calidad-aire-canarias` con la categoría **Integración** (*Integration*).
4. Busca **Calidad del Aire - Gobierno de Canarias** e instálala.
5. Reinicia Home Assistant.

## Configuración

1. Ve a **Ajustes** → **Dispositivos y servicios** → **Añadir integración**.
2. Busca **Calidad del Aire - Gobierno de Canarias**.
3. Introduce tu **Bearer Token** de la API del Gobierno de Canarias.
4. Selecciona la **estación activa** que deseas monitorizar. Puedes añadir tantas estaciones como desees repitiendo el asistente.
