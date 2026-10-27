"""API Client for the API pública de calidad del aire de Canarias (v1)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    DEFAULT_REALTIME_LOOKBACK_HOURS,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class CalidadAireCanariasError(Exception):
    """Base exception for Calidad del Aire Canarias API errors."""


class CalidadAireCanariasAuthError(CalidadAireCanariasError):
    """Exception raised for authentication/authorization failures (401/403)."""


class CalidadAireCanariasRateLimitError(CalidadAireCanariasError):
    """Exception raised when API rate limit or query cost is exceeded (429)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Initialize rate limit error with optional Retry-After seconds."""
        super().__init__(message)
        self.retry_after = retry_after


class CalidadAireCanariasConnectionError(CalidadAireCanariasError):
    """Exception raised for network or server availability errors."""


class CalidadAireCanariasApiClient:
    """Async client for the Canary Islands Government Air Quality OpenAPI v1."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        base_url: str = BASE_URL,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._token = token.strip()
        self._base_url = base_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        """Build HTTP headers including Bearer token authentication."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    async def _async_request(
        self,
        method: str,
        path: str,
        params: list[tuple[str, str]] | dict[str, Any] | None = None,
    ) -> Any:
        """Perform an authenticated HTTP request against the API."""
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                )
        except TimeoutError as err:
            raise CalidadAireCanariasConnectionError(
                f"Tiempo de espera agotado al conectar con {url}"
            ) from err
        except aiohttp.ClientError as err:
            raise CalidadAireCanariasConnectionError(
                f"Error de conexión al consultar {url}: {err}"
            ) from err

        if response.status in (401, 403):
            raise CalidadAireCanariasAuthError(
                "Credencial Bearer ausente, no válida o sin permisos (HTTP "
                f"{response.status})"
            )

        if response.status == 429:
            retry_header = response.headers.get("Retry-After")
            retry_after = (
                int(retry_header)
                if retry_header and retry_header.isdigit()
                else None
            )
            raise CalidadAireCanariasRateLimitError(
                "Límite de uso o coste de consulta superado (HTTP 429)",
                retry_after=retry_after,
            )

        if response.status == 204:
            return None

        if response.status == 404:
            error_detail = await self._extract_error_message(response)
            raise CalidadAireCanariasError(
                f"Recurso no encontrado en {path}: {error_detail}"
            )

        if response.status >= 400:
            error_detail = await self._extract_error_message(response)
            raise CalidadAireCanariasError(
                f"Error HTTP {response.status} en {path}: {error_detail}"
            )

        try:
            text = await response.text()
            if not text or not text.strip():
                return None
            return await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise CalidadAireCanariasError(
                f"Respuesta JSON inválida desde {path}"
            ) from err

    @staticmethod
    async def _extract_error_message(response: aiohttp.ClientResponse) -> str:
        """Extract message and details from ErrorResponse schema if present."""
        try:
            payload = await response.json(content_type=None)
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("status") or ""
                details = payload.get("details")
                if details and isinstance(details, list):
                    return f"{message} ({', '.join(str(d) for d in details)})"
                if message:
                    return str(message)
        except Exception:  # noqa: BLE001
            pass
        return response.reason or f"HTTP {response.status}"

    async def async_get_stations(
        self, only_active: bool = True
    ) -> list[dict[str, Any]]:
        """List available public stations (/api/v1/stations)."""
        data = await self._async_request("GET", "/api/v1/stations")
        if not isinstance(data, list):
            return []
        if only_active:
            return [station for station in data if station.get("active", False)]
        return data

    async def async_get_station_detail(self, station_id: int) -> dict[str, Any]:
        """Get full details and available parameters of a station (/api/v1/stations/{id})."""
        data = await self._async_request("GET", f"/api/v1/stations/{station_id}")
        if not isinstance(data, dict):
            raise CalidadAireCanariasError(
                f"Respuesta inválida al consultar el detalle de la estación {station_id}"
            )
        return data

    async def async_get_station_ica(
        self, station_id: int
    ) -> dict[str, Any] | None:
        """Get current ICA for a public station (/api/v1/ica/stations/{id})."""
        try:
            data = await self._async_request(
                "GET", f"/api/v1/ica/stations/{station_id}"
            )
            return data if isinstance(data, dict) else None
        except (CalidadAireCanariasAuthError, CalidadAireCanariasRateLimitError):
            raise
        except CalidadAireCanariasError as err:
            _LOGGER.debug(
                "No se pudo obtener el ICA para la estación %s: %s",
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
            now_utc_hour = datetime.now(UTC).replace(
                minute=0, second=0, microsecond=0
            )
            aligned_start = now_utc_hour - timedelta(
                hours=DEFAULT_REALTIME_LOOKBACK_HOURS
            )
        else:
            aligned_start = start_date.astimezone(UTC).replace(
                minute=0, second=0, microsecond=0
            )

        iso_start = aligned_start.strftime("%Y-%m-%dT%H:00:00Z")

        params: list[tuple[str, str]] = [
            ("start_date", iso_start),
            ("stations", str(station_id)),
        ]
        for param_id in parameter_ids:
            params.append(("parameters", str(param_id)))

        data = await self._async_request(
            "GET", "/api/v1/datasets/realtime", params=params
        )
        return data if isinstance(data, list) else []
