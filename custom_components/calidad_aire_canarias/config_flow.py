"""Config flow for Calidad del Aire - Gobierno de Canarias integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
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
import voluptuous as vol

from .api import (
    CalidadAireCanariasApiClient,
    CalidadAireCanariasAuthError,
    CalidadAireCanariasConnectionError,
    CalidadAireCanariasError,
    CalidadAireCanariasRateLimitError,
    normalize_bearer_token,
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


def _flow_schema(schema: vol.Schema) -> Any:
    """Adapt voluptuous.Schema for HA 2026 probatio typing while staying HA 2025.8+ compatible."""
    return schema


def _token_schema() -> Any:
    """Return the Bearer token input schema."""
    return _flow_schema(
        vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
    )


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

    async def _async_validate_token(
        self, raw_token: str
    ) -> tuple[str | None, list[dict[str, Any]], dict[str, str]]:
        """Validate a Bearer token and fetch active stations."""
        errors: dict[str, str] = {}
        token = normalize_bearer_token(raw_token)
        if not token:
            return None, [], {"base": "invalid_auth"}

        session = async_get_clientsession(self.hass)
        client = CalidadAireCanariasApiClient(session=session, token=token)

        try:
            active_stations = await client.async_get_stations(only_active=True)
        except CalidadAireCanariasAuthError:
            errors["base"] = "invalid_auth"
        except CalidadAireCanariasRateLimitError:
            errors["base"] = "rate_limited"
        except (CalidadAireCanariasConnectionError, CalidadAireCanariasError):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Error inesperado al validar el token contra la API de Canarias")
            errors["base"] = "unknown"
        else:
            return token, active_stations, errors

        return None, [], errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: Authenticate with Bearer Token and fetch active stations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token, active_stations, errors = await self._async_validate_token(
                str(user_input[CONF_ACCESS_TOKEN])
            )
            if not errors and token is not None:
                stations_map = {
                    str(station["id"]): station
                    for station in sorted(
                        active_stations,
                        key=lambda s: str(s.get("name") or "").lower(),
                    )
                    if station.get("id") is not None
                }
                if not stations_map:
                    errors["base"] = "no_active_stations"
                else:
                    self._access_token = token
                    self._stations = stations_map
                    return await self.async_step_station()

        return self.async_show_form(
            step_id="user",
            data_schema=_token_schema(),
            errors=errors,
            last_step=False,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Select an active air quality monitoring station from the UI."""
        if not self._access_token or not self._stations:
            return await self.async_step_user()

        errors: dict[str, str] = {}

        if user_input is not None:
            station_id_str = str(user_input[CONF_STATION_ID])
            station = self._stations.get(station_id_str)
            if station is None:
                errors["base"] = "invalid_station"
            else:
                station_id = int(station["id"])
                station_name = str(station.get("name") or f"Estación {station_id}").strip()
                station_tag = str(station.get("tag") or "").strip()

                await self.async_set_unique_id(str(station_id))
                self._abort_if_unique_id_configured()

                title = f"{station_name} ({station_tag})" if station_tag else station_name

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

        data_schema = _flow_schema(
            vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            custom_value=False,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        )

        return self.async_show_form(
            step_id="station",
            data_schema=data_schema,
            errors=errors,
            last_step=True,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication when Bearer token becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauthentication is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            token, _stations, errors = await self._async_validate_token(
                str(user_input[CONF_ACCESS_TOKEN])
            )
            if not errors and token is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_token_schema(),
            description_placeholders={
                "station_name": reauth_entry.title,
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow updating the Bearer token directly from the integration menu."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            token, _stations, errors = await self._async_validate_token(
                str(user_input[CONF_ACCESS_TOKEN])
            )
            if not errors and token is not None:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_token_schema(),
            description_placeholders={
                "station_name": reconfigure_entry.title,
            },
            errors=errors,
        )


class CalidadAireCanariasOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for Calidad del Aire - Gobierno de Canarias."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            interval = min(
                max(int(user_input[CONF_SCAN_INTERVAL]), MIN_SCAN_INTERVAL_MINUTES),
                MAX_SCAN_INTERVAL_MINUTES,
            )
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: interval,
                },
            )

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_flow_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_SCAN_INTERVAL, default=current_interval): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL_MINUTES,
                                max=MAX_SCAN_INTERVAL_MINUTES,
                                step=5,
                                unit_of_measurement="min",
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                    }
                )
            ),
        )
