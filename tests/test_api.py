"""Unit tests for the CalidadAireCanariasApiClient."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.calidad_aire_canarias.api import (
    CalidadAireCanariasApiClient,
    CalidadAireCanariasAuthError,
    CalidadAireCanariasConnectionError,
    CalidadAireCanariasError,
    CalidadAireCanariasNotFoundError,
    CalidadAireCanariasRateLimitError,
    normalize_bearer_token,
    parse_retry_after,
)
from custom_components.calidad_aire_canarias.const import USER_AGENT


class _FakeResponseContext:
    """Async context manager simulating aiohttp.ClientResponse and tracking exit."""

    def __init__(
        self,
        status: int = 200,
        body: str = "",
        headers: dict[str, str] | None = None,
        reason: str = "OK",
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}
        self.reason = reason
        self.entered = False
        self.exited = False

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> _FakeResponseContext:
        self.entered = True
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.exited = True


def _make_session(resp: _FakeResponseContext) -> MagicMock:
    session = MagicMock(spec=aiohttp.ClientSession)
    session.request = MagicMock(return_value=resp)
    return session


def test_normalize_bearer_token() -> None:
    """Strip whitespace and accidental 'Bearer ' prefix case-insensitively."""
    assert normalize_bearer_token("  abc123  ") == "abc123"
    assert normalize_bearer_token("Bearer abc123") == "abc123"
    assert normalize_bearer_token("  bearer   xyz.token  ") == "xyz.token"
    assert normalize_bearer_token("   ") == ""


def test_parse_retry_after() -> None:
    """Parse integer delta-seconds and RFC 7231 HTTP-date Retry-After headers."""
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after(" 120 ") == 120
    assert parse_retry_after("not-a-date") is None

    future = datetime.now(UTC) + timedelta(seconds=90)
    parsed = parse_retry_after(format_datetime(future, usegmt=True))
    assert parsed is not None
    assert 85 <= parsed <= 95


async def test_empty_token_rejected_before_network() -> None:
    """Empty token fails fast with AuthError without making an HTTP request."""
    session = MagicMock(spec=aiohttp.ClientSession)
    client = CalidadAireCanariasApiClient(session=session, token="   ")
    with pytest.raises(CalidadAireCanariasAuthError):
        await client.async_get_stations()
    session.request.assert_not_called()


async def test_get_stations_sends_headers_and_releases_response() -> None:
    """Verify Authorization, User-Agent headers, active filtering, and context manager cleanup."""
    payload = [
        {"id": 1, "name": "Activa", "active": True},
        {"id": 2, "name": "Inactiva", "active": False},
    ]
    resp = _FakeResponseContext(status=200, body=json.dumps(payload))
    session = _make_session(resp)
    client = CalidadAireCanariasApiClient(session=session, token="Bearer my-token")

    stations = await client.async_get_stations(only_active=True)

    assert len(stations) == 1
    assert stations[0]["id"] == 1
    assert resp.entered is True
    assert resp.exited is True

    _, kwargs = session.request.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer my-token"
    assert kwargs["headers"]["Accept"] == "application/json"
    assert kwargs["headers"]["User-Agent"] == USER_AGENT


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_error_releases_response(status: int) -> None:
    """HTTP 401/403 raises AuthError and still releases the response."""
    resp = _FakeResponseContext(status=status, reason="Unauthorized")
    client = CalidadAireCanariasApiClient(session=_make_session(resp), token="tok")

    with pytest.raises(CalidadAireCanariasAuthError):
        await client.async_get_stations()

    assert resp.exited is True


async def test_rate_limit_429_parses_retry_after_and_releases() -> None:
    """HTTP 429 raises RateLimitError with parsed Retry-After."""
    resp = _FakeResponseContext(status=429, headers={"Retry-After": "180"})
    client = CalidadAireCanariasApiClient(session=_make_session(resp), token="tok")

    with pytest.raises(CalidadAireCanariasRateLimitError) as err:
        await client.async_get_stations()

    assert err.value.retry_after == 180
    assert resp.exited is True


async def test_5xx_raises_connection_error() -> None:
    """HTTP 503 raises CalidadAireCanariasConnectionError with server detail."""
    resp = _FakeResponseContext(
        status=503,
        body=json.dumps({"message": "Servicio en mantenimiento"}),
        reason="Service Unavailable",
    )
    client = CalidadAireCanariasApiClient(session=_make_session(resp), token="tok")

    with pytest.raises(CalidadAireCanariasConnectionError, match="Servicio en mantenimiento"):
        await client.async_get_station_detail(101)

    assert resp.exited is True


async def test_404_raises_not_found_and_ica_returns_none() -> None:
    """HTTP 404 returns None for ICA endpoint while raising NotFoundError for station detail."""
    resp_ica = _FakeResponseContext(status=404, body=json.dumps({"message": "No ICA"}))
    client_ica = CalidadAireCanariasApiClient(session=_make_session(resp_ica), token="tok")
    assert await client_ica.async_get_station_ica(101) is None
    assert resp_ica.exited is True

    resp_detail = _FakeResponseContext(status=404, body=json.dumps({"message": "No station"}))
    client_detail = CalidadAireCanariasApiClient(session=_make_session(resp_detail), token="tok")
    with pytest.raises(CalidadAireCanariasNotFoundError):
        await client_detail.async_get_station_detail(999)


async def test_ica_propagates_500_connection_error() -> None:
    """HTTP 500 on ICA endpoint must not be silently swallowed."""
    resp = _FakeResponseContext(status=500, reason="Internal Server Error")
    client = CalidadAireCanariasApiClient(session=_make_session(resp), token="tok")

    with pytest.raises(CalidadAireCanariasConnectionError):
        await client.async_get_station_ica(101)


async def test_204_and_invalid_json() -> None:
    """HTTP 204 returns None and invalid JSON raises CalidadAireCanariasError."""
    resp_204 = _FakeResponseContext(status=204)
    client_204 = CalidadAireCanariasApiClient(session=_make_session(resp_204), token="tok")
    assert await client_204.async_get_stations() == []
    assert resp_204.exited is True

    resp_bad = _FakeResponseContext(status=200, body="<html>not json</html>")
    client_bad = CalidadAireCanariasApiClient(session=_make_session(resp_bad), token="tok")
    with pytest.raises(CalidadAireCanariasError, match="JSON inválida"):
        await client_bad.async_get_stations()
    assert resp_bad.exited is True


async def test_timeout_and_client_error() -> None:
    """Timeouts and aiohttp.ClientError wrap as CalidadAireCanariasConnectionError."""
    session_timeout = MagicMock(spec=aiohttp.ClientSession)
    session_timeout.request = MagicMock(side_effect=TimeoutError())
    client_timeout = CalidadAireCanariasApiClient(session=session_timeout, token="tok")
    with pytest.raises(CalidadAireCanariasConnectionError):
        await client_timeout.async_get_stations()

    session_err = MagicMock(spec=aiohttp.ClientSession)
    session_err.request = MagicMock(side_effect=aiohttp.ClientConnectionError("refused"))
    client_err = CalidadAireCanariasApiClient(session=session_err, token="tok")
    with pytest.raises(CalidadAireCanariasConnectionError):
        await client_err.async_get_stations()


async def test_realtime_datasets_aligns_start_date_to_utc_hour() -> None:
    """Verify start_date is aligned to exact UTC hour and parameters are repeated."""
    resp = _FakeResponseContext(status=200, body="[]")
    session = _make_session(resp)
    client = CalidadAireCanariasApiClient(session=session, token="tok")

    custom_start = datetime(2026, 11, 20, 14, 37, 45, tzinfo=UTC)
    result = await client.async_get_realtime_datasets(
        station_id=101,
        parameter_ids=[1, 3],
        start_date=custom_start,
    )

    assert result == []
    _, kwargs = session.request.call_args
    assert kwargs["params"] == [
        ("start_date", "2026-11-20T14:00:00Z"),
        ("stations", "101"),
        ("parameters", "1"),
        ("parameters", "3"),
    ]


async def test_realtime_datasets_empty_parameters_short_circuits() -> None:
    """Empty parameter_ids list skips HTTP call."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.request = AsyncMock()
    client = CalidadAireCanariasApiClient(session=session, token="tok")

    assert await client.async_get_realtime_datasets(101, []) == []
    session.request.assert_not_called()
