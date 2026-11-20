"""API Client for the API pública de calidad del aire de Canarias (v1)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
import json
import logging
import math
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    DEFAULT_REALTIME_LOOKBACK_HOURS,
    DEFAULT_TIMEOUT,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class CalidadAireCanariasError(Exception):
    """Base exception for Calidad del Aire Canarias API errors."""


class CalidadAireCanariasAuthError(CalidadAireCanariasError):
    """Exception raised for authentication/authorization failures (401/403)."""


class CalidadAireCanariasNotFoundError(CalidadAireCanariasError):
    """Exception raised when a requested API resource does not exist (404)."""


class CalidadAireCanariasRateLimitError(CalidadAireCanariasError):
    """Exception raised when API rate limit or query cost is exceeded (429)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Initialize rate limit error with optional Retry-After seconds."""
        super().__init__(message)
        self.retry_after = retry_after


class CalidadAireCanariasConnectionError(CalidadAireCanariasError):
    """Exception raised for network, timeout, or transient server (5xx) errors."""


def normalize_bearer_token(raw_token: str) -> str:
    """Normalize a Bearer token by stripping whitespace and an optional 'Bearer ' prefix."""
    token = raw_token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def parse_retry_after(header_value: str | None) -> int | None:
    """Parse an HTTP Retry-After header (delta-seconds or RFC 7231 HTTP-date)."""
    if not header_value:
        return None
    cleaned = header_value.strip()
    if not cleaned:
        return None
    if cleaned.isdigit():
        return int(cleaned)
    try:
        retry_dt = parsedate_to_datetime(cleaned)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_dt.tzinfo is None:
        retry_dt = retry_dt.replace(tzinfo=UTC)
    delta_seconds = (retry_dt - datetime.now(UTC)).total_seconds()
    return max(math.ceil(delta_seconds), 0)


class CalidadAireCanariasApiClient:
    """Async client for the Canary Islands Government Air Quality OpenAPI v1."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = USER_AGENT,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._token = normalize_bearer_token(token)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._user_agent = user_agent

    @property
    def _headers(self) -> dict[str, str]:
        """Build HTTP headers including Bearer token authentication."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

    async def _async_request(
        self,
        method: str,
        path: str,
        params: list[tuple[str, str]] | dict[str, Any] | None = None,
    ) -> Any:
        """Perform an authenticated HTTP request against the API."""
        if not self._token:
            raise CalidadAireCanariasAuthError("Credencial Bearer vacía o ausente")

        url = f"{self._base_url}{path}"
        try:
            async with (
                asyncio.timeout(self._timeout),
                self._session.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                ) as response,
            ):
                if response.status in (401, 403):
                    raise CalidadAireCanariasAuthError(
                        "Credencial Bearer ausente, no válida o sin permisos (HTTP "
                        f"{response.status})"
                    )

                if response.status == 429:
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    raise CalidadAireCanariasRateLimitError(
                        "Límite de uso o coste de consulta superado (HTTP 429)",
                        retry_after=retry_after,
                    )

                if response.status == 204:
                    return None

                if response.status == 404:
                    error_detail = await self._extract_error_message(response)
                    raise CalidadAireCanariasNotFoundError(
                        f"Recurso no encontrado en {path}: {error_detail}"
                    )

                if response.status >= 500:
                    error_detail = await self._extract_error_message(response)
                    raise CalidadAireCanariasConnectionError(
                        f"Error temporal del servidor (HTTP {response.status}) en {path}: {error_detail}"
                    )

                if response.status >= 400:
                    error_detail = await self._extract_error_message(response)
                    raise CalidadAireCanariasError(
                        f"Error HTTP {response.status} en {path}: {error_detail}"
                    )

                text = await response.text()
                if not text or not text.strip():
                    return None
                try:
                    return json.loads(text)
                except ValueError as err:
                    raise CalidadAireCanariasError(f"Respuesta JSON inválida desde {path}") from err
        except TimeoutError as err:
            raise CalidadAireCanariasConnectionError(
                f"Tiempo de espera agotado al conectar con {url}"
            ) from err
        except aiohttp.ClientError as err:
            raise CalidadAireCanariasConnectionError(
                f"Error de conexión al consultar {url}: {err}"
            ) from err

    @staticmethod
    async def _extract_error_message(response: aiohttp.ClientResponse) -> str:
        """Extract message and details from ErrorResponse schema if present."""
        try:
            raw_text = await response.text()
            if raw_text and raw_text.strip():
                payload = json.loads(raw_text)
                if isinstance(payload, dict):
                    message = payload.get("message") or payload.get("status") or ""
                    details = payload.get("details")
                    if details and isinstance(details, list):
                        return f"{message} ({', '.join(str(d) for d in details)})"
                    if message:
                        return str(message)
        except (ValueError, aiohttp.ClientError):
            _LOGGER.debug("No se pudo decodificar el cuerpo de error HTTP %s", response.status)
        return response.reason or f"HTTP {response.status}"

    async def async_get_stations(self, only_active: bool = True) -> list[dict[str, Any]]:
        """List available public stations (/api/v1/stations)."""
        data = await self._async_request("GET", "/api/v1/stations")
        if not isinstance(data, list):
            return []
        if only_active:
            return [
                station
                for station in data
                if isinstance(station, dict) and station.get("active", False)
            ]
        return [station for station in data if isinstance(station, dict)]

    async def async_get_station_detail(self, station_id: int) -> dict[str, Any]:
        """Get full details and available parameters of a station (/api/v1/stations/{id})."""
        data = await self._async_request("GET", f"/api/v1/stations/{station_id}")
        if not isinstance(data, dict):
            raise CalidadAireCanariasError(
                f"Respuesta inválida al consultar el detalle de la estación {station_id}"
            )
        return data

    async def async_get_station_ica(self, station_id: int) -> dict[str, Any] | None:
        """Get current ICA for a public station (/api/v1/ica/stations/{id})."""
        try:
            data = await self._async_request("GET", f"/api/v1/ica/stations/{station_id}")
            return data if isinstance(data, dict) else None
        except CalidadAireCanariasNotFoundError as err:
            _LOGGER.debug(
                "No hay datos ICA disponibles para la estación %s: %s",
                station_id,
                err,
            )
            return None

    async def async_get_realtime_datasets(
        self,
        station_id: int,
        parameter_ids: list[int],
        start_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Query the last hours of temporal data (/api/v1/datasets/realtime).

        Note: The API requires `start_date` to be aligned to an exact UTC hour
        (minute=0, second=0, microsecond=0) and within the last 24 hours.
        """
        if not parameter_ids:
            return []

        if start_date is None:
            now_utc_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            aligned_start = now_utc_hour - timedelta(hours=DEFAULT_REALTIME_LOOKBACK_HOURS)
        else:
            aligned_start = start_date.astimezone(UTC).replace(minute=0, second=0, microsecond=0)

        iso_start = aligned_start.strftime("%Y-%m-%dT%H:00:00Z")

        params: list[tuple[str, str]] = [
            ("start_date", iso_start),
            ("stations", str(station_id)),
        ]
        for param_id in parameter_ids:
            params.append(("parameters", str(param_id)))

        data = await self._async_request("GET", "/api/v1/datasets/realtime", params=params)
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
