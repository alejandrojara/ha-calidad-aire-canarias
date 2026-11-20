"""Integration tests for sensor and button platforms."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ACCESS_TOKEN,
    DEGREE,
    PERCENTAGE,
    UnitOfDensity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calidad_aire_canarias.const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_TAG,
    DOMAIN,
    ICA_CATEGORIES,
)

from .conftest import SAMPLE_TOKEN


async def test_sensors_button_classification_and_stale_cleanup(
    hass: HomeAssistant, mock_api_client: dict[str, AsyncMock]
) -> None:
    """Verify full entry setup, sensor classifications, ENUM ICA, stale cleanup, and refresh button."""
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
    )
    entry.add_to_hass(hass)

    # Pre-register a stale sensor AND a valid button in the entity registry to verify cleanup
    ent_reg = er.async_get(hass)
    stale_sensor = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "101_param_999",
        config_entry=entry,
    )
    existing_button = ent_reg.async_get_or_create(
        "button",
        DOMAIN,
        "101_refresh",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Stale sensor must be removed, while existing button must be preserved!
    assert ent_reg.async_get(stale_sensor.entity_id) is None
    assert ent_reg.async_get(existing_button.entity_id) is not None

    # ICA sensor: ENUM device class, proper translation key, expected value and attributes
    ica_entry = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_ica")
    assert ica_entry is not None
    ica_state = hass.states.get(ica_entry)
    assert ica_state is not None
    assert ica_state.state == "Regular"
    assert ica_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert ica_state.attributes["options"] == ICA_CATEGORIES
    assert ica_state.attributes["dominant_parameter"] == "PM10"

    # CO in mg/m³ now gets SensorDeviceClass.CO!
    co_entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_4")
    assert co_entity_id is not None
    co_state = hass.states.get(co_entity_id)
    assert co_state is not None
    assert co_state.state == "0.4"
    assert co_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.CO
    assert co_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER

    # C7H8 (Toluene) gets VOLATILE_ORGANIC_COMPOUNDS
    toluene_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_5")
    assert toluene_id is not None
    toluene_state = hass.states.get(toluene_id)
    assert toluene_state is not None
    assert toluene_state.attributes[ATTR_DEVICE_CLASS] == (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    )
    assert (
        toluene_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
    )

    # HR (%) gets HUMIDITY, while non-humidity CAL (%) has no device_class
    hr_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_7")
    cal_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_9")
    assert hr_id is not None and cal_id is not None
    hr_state = hass.states.get(hr_id)
    cal_state = hass.states.get(cal_id)
    assert hr_state is not None and cal_state is not None
    assert hr_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.HUMIDITY
    assert ATTR_DEVICE_CLASS not in cal_state.attributes
    assert cal_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    # DV (°) gets WIND_DIRECTION + MEASUREMENT_ANGLE, while non-wind SOL (°) has no device_class
    dv_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_8")
    sol_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "101_param_10")
    assert dv_id is not None and sol_id is not None
    dv_state = hass.states.get(dv_id)
    sol_state = hass.states.get(sol_id)
    assert dv_state is not None and sol_state is not None
    assert dv_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WIND_DIRECTION
    assert dv_state.attributes["state_class"] == SensorStateClass.MEASUREMENT_ANGLE
    assert ATTR_DEVICE_CLASS not in sol_state.attributes
    assert sol_state.attributes["state_class"] == SensorStateClass.MEASUREMENT_ANGLE
    assert sol_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == DEGREE

    # Refresh button triggers refresh once and enforces cooldown on immediate second press
    initial_ica_calls = mock_api_client["ica"].await_count
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: existing_button.entity_id},
        blocking=True,
    )
    assert mock_api_client["ica"].await_count == initial_ica_calls + 1

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: existing_button.entity_id},
            blocking=True,
        )

    # Clean unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
