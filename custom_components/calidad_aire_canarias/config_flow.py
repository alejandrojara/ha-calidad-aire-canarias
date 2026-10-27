"""Config flow for Calidad del Aire - Gobierno de Canarias integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
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
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_TAG,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class CalidadAireCanariasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Calidad del Aire - Gobierno de Canarias."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._access_token: str | None = None
        self._stations: dict[str, dict[str, Any]] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CalidadAireCanariasOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CalidadAireCanariasOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Authenticate with Bearer Token and fetch active stations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN].strip()
            session = async_get_clientsession(self.hass)
            client = CalidadAireCanariasApiClient(session=session, token=token)

            try:
                active_stations = await client.async_get_stations(
                    only_active=True
                )
            except CalidadAireCanariasAuthError:
                errors["base"] = "invalid_auth"
            except CalidadAireCanariasRateLimitError:
                errors["base"] = "rate_limited"
            except (
                CalidadAireCanariasConnectionError,
                CalidadAireCanariasError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Error inesperado al validar el token contra la API de Canarias"
                )
                errors["base"] = "unknown"
            else:
                if not active_stations:
                    errors["base"] = "no_active_stations"
                else:
                    self._access_token = token
                    self._stations = {
                        str(station["id"]): station
                        for station in sorted(
                            active_stations,
                            key=lambda s: str(s.get("name") or "").lower(),
                        )
                        if "id" in station
                    }
                    return await self.async_step_station()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Select an active air quality monitoring station from the UI."""
        if not self._access_token or not self._stations:
            return await self.async_step_user()

        if user_input is not None:
            station_id_str = str(user_input[CONF_STATION_ID])
            station = self._stations[station_id_str]
            station_id = int(station["id"])
            station_name = str(
                station.get("name") or f"Estación {station_id}"
            ).strip()
            station_tag = str(station.get("tag") or "").strip()

            await self.async_set_unique_id(str(station_id))
            self._abort_if_unique_id_configured()

            title = (
                f"{station_name} ({station_tag})"
                if station_tag
                else station_name
            )

            return self.async_create_entry(
                title=title,
                data={
                    CONF_ACCESS_TOKEN: self._access_token,
                    CONF_STATION_ID: station_id,
                    CONF_STATION_NAME: station_name,
                    CONF_STATION_TAG: station_tag,
                },
            )

        options: list[SelectOptionDict] = []
        for station_id_str, station in self._stations.items():
            name = str(station.get("name") or f"Estación {station_id_str}")
            tag = str(station.get("tag") or "").strip()
            cnac = str(station.get("cnac") or "").strip()
            label_parts = [name]
            if tag:
                label_parts.append(f"[{tag}]")
            if cnac:
                label_parts.append(f"({cnac})")
            options.append(
                SelectOptionDict(
                    value=station_id_str,
                    label=" ".join(label_parts),
                )
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="station",
            data_schema=data_schema,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when Bearer token becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauthentication is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN].strip()
            session = async_get_clientsession(self.hass)
            client = CalidadAireCanariasApiClient(session=session, token=token)

            try:
                await client.async_get_stations(only_active=True)
            except CalidadAireCanariasAuthError:
                errors["base"] = "invalid_auth"
            except CalidadAireCanariasRateLimitError:
                errors["base"] = "rate_limited"
            except (
                CalidadAireCanariasConnectionError,
                CalidadAireCanariasError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Error inesperado al reautenticar el token contra la API de Canarias"
                )
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={
                "station_name": reauth_entry.title,
            },
            errors=errors,
        )


class CalidadAireCanariasOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Calidad del Aire - Gobierno de Canarias."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_MINUTES,
                            max=MAX_SCAN_INTERVAL_MINUTES,
                            step=5,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
