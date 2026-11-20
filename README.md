# Calidad del Aire - Gobierno de Canarias (`ha-calidad-aire-canarias`)

<p align="center">
  <img src="https://raw.githubusercontent.com/alejandrojara/ha-calidad-aire-canarias/main/custom_components/calidad_aire_canarias/brand/icon.png" alt="Calidad del Aire - Gobierno de Canarias" width="140" height="140" />
</p>

<p align="center">
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/ci.yml"><img src="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/hassfest.yml"><img src="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/hassfest.yml/badge.svg" alt="hassfest" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/hacs.yml"><img src="https://github.com/alejandrojara/ha-calidad-aire-canarias/actions/workflows/hacs.yml/badge.svg" alt="HACS" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/releases"><img src="https://img.shields.io/badge/version-20261120.1-blue.svg" alt="Version" /></a>
  <a href="https://github.com/alejandrojara/ha-calidad-aire-canarias/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
</p>

Integración personalizada **no oficial** para **Home Assistant** (compatible con el **Home Assistant Marketplace** y **HACS**) que consulta la **API pública de Calidad del Aire del Gobierno de Canarias (v1)** (`https://www3.gobiernodecanarias.org/calidadambiental/calidadaire/anemo`) para monitorizar el Índice de Calidad del Aire (ICA), los contaminantes y los parámetros meteorológicos de cada estación activa.

> [!IMPORTANT]
> **Componente no oficial:** Este proyecto es una integración comunitaria independiente desarrollada por terceros. **No está afiliado, patrocinado, avalado ni soportado oficialmente por el Gobierno de Canarias ni por la Consejería de Transición Ecológica y Energía.** Para soporte o incidencias técnicas de esta integración utiliza únicamente el [issue tracker de este repositorio](https://github.com/alejandrojara/ha-calidad-aire-canarias/issues) y nunca los canales de atención del Gobierno de Canarias.

---

## Características principales

* **Configuración 100 % visual (sin YAML):** asistente guiado en dos pasos:
  1. Validación del **Bearer Token** (limpia automáticamente espacios o un prefijo `Bearer ` pegado por error) y descarga del catálogo de estaciones públicas activas.
  2. Selector desplegable con todas las estaciones activas (`active: true`) ordenadas alfabéticamente con etiqueta y código CNAC. Puedes añadir tantas estaciones como necesites.
* **Flujos completos de mantenimiento:**
  * **Opciones (`OptionsFlowWithReload`):** ajusta el intervalo de sondeo (por defecto **60 minutos**, entre 15 y 240 minutos) con recarga automática sin `update_listener` obsoletos.
  * **Reconfiguración (`Reconfigure`):** actualiza o rota el Bearer Token en cualquier momento desde el menú de la estación sin borrar entidades ni historial.
  * **Reautenticación (`Reauth`):** flujo integrado automático si el token caduca o devuelve `HTTP 401/403`.
* **Sondeo responsable con `DataUpdateCoordinator`:**
  * Ventana horaria alineada a hora UTC en punto (`YYYY-MM-DDTHH:00:00Z`) conforme a la API v1.
  * `always_update=False` para evitar escrituras innecesarias en la base de datos cuando los datos horarios no cambian.
  * Gestión de `HTTP 429` respetando `Retry-After` (segundos o fecha HTTP RFC 7231) y *backoff* automático de seguridad.
* **Entidades nativas y limpieza automática:**
  * **Sensor de Índice de Calidad del Aire (ICA)** (`SensorDeviceClass.ENUM`, traducible a español e inglés) con la categoría global de la estación, contaminante dominante y desglose por contaminante en atributos.
  * **Sensores dinámicos de contaminantes y meteorología** (`/api/v1/stations/{id}` + `/api/v1/datasets/realtime`), filtrando canales sin asignar (`Desconocida`) y asignando `SensorDeviceClass`, `SensorStateClass` (`MEASUREMENT` o `MEASUREMENT_ANGLE`) y unidades nativas (`µg/m³`, `mg/m³`, `ppm`, `ppb`, `°C`, `%`, `m/s`, `km/h`, `hPa`, `mbar`, `W/m²`, `mm`, `mm/h`, `°`).
  * **Botón de actualización manual** (`button.<estacion>_actualizar`) con *cooldown* de 60 s para consultas puntuales sin saturar la API.
* **Diagnósticos integrados:** descarga información de depuración desde la tarjeta de la integración con **redacción automática del Bearer Token** (`**REDACTED**`).
* **Preparada para el Home Assistant Marketplace (2026.11+):** incluye categoría oficial (`weather_alerts.air_quality_pollen`), iconos locales optimizados en `brand/` (`icon.png` y `icon@2x.png`) y validación continua con `hassfest`, `HACS Action` y `pytest`.

---

## Requisitos previos

* **Home Assistant 2025.8.0** o superior.
* Un **Bearer Token** válido de la API pública de Calidad del Aire del Gobierno de Canarias. Puedes consultar la documentación oficial y el procedimiento de solicitud de acceso en el [portal de la API Pública (v1) del Gobierno de Canarias](https://www3.gobiernodecanarias.org/calidadambiental/calidadaire/api-publica).

> **Nota sobre la frecuencia de actualización:** Los datos de medición se publican con resolución horaria. Realizar peticiones cada pocos minutos no generará lecturas nuevas y puede activar límites de uso (`HTTP 429`).

---

## Instalación

### Mediante Home Assistant Marketplace (Home Assistant 2026.11 o superior — recomendado)

[![Abrir repositorio en Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=alejandrojara&repository=ha-calidad-aire-canarias&category=integration)

1. Pulsa el botón superior, o ve a **Ajustes → Marketplace** → menú superior derecho (`⋮`) → **Repositorios personalizados** y añade `https://github.com/alejandrojara/ha-calidad-aire-canarias` con la categoría **Integración**.
2. Instala **Calidad del Aire - Gobierno de Canarias**. En instalaciones nuevas con flujo de configuración, el Marketplace carga la integración automáticamente (si actualizas una versión anterior, reinicia Home Assistant cuando se indique).
3. Añade tu estación desde **Ajustes → Dispositivos y servicios → Añadir integración**, o con este botón:

[![Añadir integración Calidad del Aire - Gobierno de Canarias](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=calidad_aire_canarias)

### Mediante HACS (Home Assistant 2025.8 – 2026.10)

[![Añadir repositorio a HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alejandrojara&repository=ha-calidad-aire-canarias&category=integration)

1. Pulsa el botón superior (o abre **HACS** → `⋮` → **Repositorios personalizados** y añade `https://github.com/alejandrojara/ha-calidad-aire-canarias` con la categoría **Integración**).
2. Busca **Calidad del Aire - Gobierno de Canarias** e instálala.
3. Reinicia Home Assistant y añade la integración desde **Ajustes → Dispositivos y servicios → Añadir integración**.

### Instalación manual

Copia la carpeta `custom_components/calidad_aire_canarias` dentro de `<config>/custom_components/calidad_aire_canarias` en tu servidor de Home Assistant y reinicia.

---

## Configuración

1. Ve a **Ajustes → Dispositivos y servicios → Añadir integración** y busca **Calidad del Aire - Gobierno de Canarias**.
2. Introduce tu **Bearer Token** y pulsa **Siguiente**.
3. Selecciona la **estación activa** que deseas monitorizar y pulsa **Enviar**.
4. *(Opcional)* Pulsa **Configurar** en la tarjeta de la estación para ajustar el intervalo de sondeo, o **Reconfigurar** desde el menú (`⋮`) si necesitas renovar el token.

---

## Entidades creadas por estación

Cada estación configurada crea su propio **Dispositivo** (servicio) en Home Assistant:

| Entidad | Tipo | Descripción |
| :--- | :--- | :--- |
| `sensor.<estacion>_indice_de_calidad_del_aire_ica` | `sensor` (`enum`) | Categoría global ICA vigente (`Buena`, `Razonablemente buena`, `Regular`, `Desfavorable`, `Muy desfavorable`, `Extremadamente desfavorable`, `Sin datos`). Expone `dominant_parameter`, `date`, `period`, coordenadas y `parameters_ica`. |
| `sensor.<estacion>_<parametro>` | `sensor` (numérico) | Un sensor por cada contaminante o variable meteorológica medida en la estación (`PM10`, `PM2.5`, `NO2`, `O3`, `SO2`, `CO`, `C6H6`, temperatura, humedad, viento, presión, radiación solar, precipitación, etc.). |
| `button.<estacion>_actualizar` | `button` | Fuerza una actualización puntual bajo demanda (con *cooldown* de 60 s). |

> Los `entity_id` se generan en el idioma configurado en Home Assistant (en inglés `_air_quality_index_ica` y `_refresh`; en español `_indice_de_calidad_del_aire_ica` y `_actualizar`).

---

## Ejemplos de tarjetas nativas de Home Assistant

### 1. Tarjeta Markdown con resumen ICA y refresco al pulsar

```yaml
type: markdown
title: 🌬️ Calidad del Aire
content: |
  {%- set ica_entity = 'sensor.mi_estacion_indice_de_calidad_del_aire_ica' -%}
  {%- set ica = states(ica_entity) -%}
  {%- set dominant = state_attr(ica_entity, 'dominant_parameter') -%}
  {%- set params = state_attr(ica_entity, 'parameters_ica') or {} -%}
  **ICA actual:** {{ ica }}{% if dominant %} *(dominante: {{ dominant }})*{% endif %}

  {% if params | length > 0 -%}
  | Contaminante | Categoría ICA | Medición |
  | :--- | :--- | ---: |
  {%- for name, info in params.items() %}
  | **{{ name }}** | {{ info.ica or 'Sin datos' }} | {{ info.measurement_value if info.measurement_value is not none else '—' }} |
  {%- endfor %}
  {%- else -%}
  Sin desglose ICA disponible en este momento.
  {%- endif %}
tap_action:
  action: perform-action
  perform_action: button.press
  target:
    entity_id: button.mi_estacion_actualizar
```

### 2. Tarjetas Tile nativas para ICA y contaminantes principales

```yaml
type: grid
columns: 2
square: false
cards:
  - type: tile
    entity: sensor.mi_estacion_indice_de_calidad_del_aire_ica
    name: ICA
  - type: tile
    entity: sensor.mi_estacion_particulas_pm10
    name: PM10
  - type: tile
    entity: sensor.mi_estacion_particulas_pm2_5
    name: PM2.5
  - type: tile
    entity: button.mi_estacion_actualizar
    name: Actualizar
    tap_action:
      action: perform-action
      perform_action: button.press
      target:
        entity_id: button.mi_estacion_actualizar
```

---

## Estructura del proyecto

```text
├── .github/workflows/
│   ├── ci.yml
│   ├── hacs.yml
│   └── hassfest.yml
├── hacs.json
├── LICENSE
├── pyproject.toml
├── README.md
├── custom_components/
│   └── calidad_aire_canarias/
│       ├── __init__.py
│       ├── api.py
│       ├── button.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── diagnostics.py
│       ├── entity.py
│       ├── manifest.json
│       ├── sensor.py
│       ├── brand/
│       │   ├── icon.png
│       │   └── icon@2x.png
│       └── translations/
│           ├── en.json
│           └── es.json
└── tests/
```

---

## Aviso legal, atribución de datos y uso responsable

* **Componente no oficial y ausencia de afiliación:** `ha-calidad-aire-canarias` es software libre independiente de la comunidad, **no oficial y sin respaldo, patrocinio ni vinculación con el Gobierno de Canarias ni con la Consejería de Transición Ecológica y Energía**.
* **Exclusión de garantías:** Esta integración se proporciona *«tal cual»* (*as is*), sin garantía de disponibilidad continua ni exactitud de las mediciones, y puede verse afectada por cambios no anunciados en la API pública externa.
* **Fuente de datos:** Red de Control y Vigilancia de la Calidad del Aire del **Gobierno de Canarias** (API Pública v1, datos temporales en tiempo real no validados y cálculo horario del ICA).
* **Seguridad y uso responsable:** Nunca compartas tu Bearer Token en repositorios públicos ni capturas de pantalla. La integración redacta automáticamente el token en Diagnósticos y limita el sondeo por defecto a 60 minutos (con *cooldown* manual de 60 s y gestión de `Retry-After`) para respetar los límites del servicio público.

---

## Licencia

Distribuido bajo licencia [MIT](LICENSE).
