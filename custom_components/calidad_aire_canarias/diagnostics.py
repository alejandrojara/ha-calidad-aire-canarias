"""Diagnostics support for Calidad del Aire - Gobierno de Canarias."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import CalidadAireCanariasConfigEntry

TO_REDACT = {CONF_ACCESS_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: CalidadAireCanariasConfigEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics for a Calidad del Aire Canarias config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "pref_disable_polling": entry.pref_disable_polling,
        },
        "coordinator": coordinator.get_diagnostics(),
    }
