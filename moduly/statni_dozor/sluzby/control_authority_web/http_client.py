"""Bezpečný HTTPS GET pro oficiální stránky kontrolních orgánů."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests import Response
from requests.exceptions import SSLError, Timeout

from core.version import APP_EXE_NAME, APP_NAME, APP_VERSION
from moduly.statni_dozor.constants import (
    WEB_ADAPTER_ERROR_HTTP,
    WEB_ADAPTER_ERROR_INVALID_URL,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_ADAPTER_ERROR_TIMEOUT,
    WEB_ADAPTER_ERROR_TOO_LARGE,
    WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT,
    WEB_ADAPTER_HTTP_TIMEOUT_SECONDS,
    WEB_ADAPTER_MAX_RESPONSE_BYTES,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityWebAdapterError,
    adapter_error,
)

logger = logging.getLogger(__name__)

_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
    }
)
_MAX_REDIRECTS = 5
_CHUNK_SIZE = 8192


def default_user_agent() -> str:
    return f"{APP_EXE_NAME}/{APP_VERSION} ({APP_NAME})"


@dataclass(frozen=True)
class ControlAuthorityHttpResponse:
    status_code: int
    body: bytes
    content_type: str | None
    final_url: str


HttpGet = Callable[[str], ControlAuthorityHttpResponse]


def validate_official_https_url(url: str, *, allowed_hosts: frozenset[str]) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username
        or parsed.password
    ):
        raise adapter_error(WEB_ADAPTER_ERROR_INVALID_URL)
    if host not in {item.casefold() for item in allowed_hosts}:
        raise adapter_error(WEB_ADAPTER_ERROR_INVALID_URL)
    return text


def _content_type_of(headers: Mapping[str, Any]) -> str | None:
    raw = headers.get("Content-Type") or headers.get("content-type")
    if raw is None:
        return None
    return str(raw).split(";", 1)[0].strip().casefold() or None


def _require_html_content_type(content_type: str | None) -> None:
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise adapter_error(WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT)


def _read_limited_body(response: Response, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise adapter_error(WEB_ADAPTER_ERROR_TOO_LARGE)
        chunks.append(chunk)
    return b"".join(chunks)


class ControlAuthorityHttpClient:
    """HTTPS GET s TLS, timeoutem, limitem velikosti a bez cookies."""

    def __init__(
        self,
        *,
        timeout_seconds: float = WEB_ADAPTER_HTTP_TIMEOUT_SECONDS,
        max_bytes: int = WEB_ADAPTER_MAX_RESPONSE_BYTES,
        user_agent: str | None = None,
        request: Callable[..., Response] | None = None,
    ):
        self._timeout = float(timeout_seconds)
        self._max_bytes = int(max_bytes)
        self._user_agent = user_agent or default_user_agent()
        self._request = request or requests.request

    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
    ) -> ControlAuthorityHttpResponse:
        current = validate_official_https_url(url, allowed_hosts=allowed_hosts)
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                response = self._request(
                    "GET",
                    current,
                    timeout=self._timeout,
                    allow_redirects=False,
                    verify=True,
                    stream=True,
                    headers=headers,
                )
            except ControlAuthorityWebAdapterError:
                raise
            except Timeout:
                logger.exception("Timeout při načtení oficiální stránky %s", current)
                raise adapter_error(WEB_ADAPTER_ERROR_TIMEOUT) from None
            except SSLError:
                logger.exception("TLS chyba při načtení oficiální stránky %s", current)
                raise adapter_error(WEB_ADAPTER_ERROR_NETWORK) from None
            except requests.RequestException:
                logger.exception("Síťová chyba při načtení oficiální stránky %s", current)
                raise adapter_error(WEB_ADAPTER_ERROR_NETWORK) from None
            try:
                status = int(response.status_code)
                if status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location") or ""
                    nxt = urljoin(current, str(location).strip())
                    current = validate_official_https_url(
                        nxt, allowed_hosts=allowed_hosts
                    )
                    continue
                if status >= 400 or status < 200:
                    logger.error(
                        "HTTP %s při načtení oficiální stránky %s",
                        status,
                        current,
                    )
                    raise adapter_error(WEB_ADAPTER_ERROR_HTTP)
                content_type = _content_type_of(response.headers)
                _require_html_content_type(content_type)
                body = _read_limited_body(response, max_bytes=self._max_bytes)
            finally:
                response.close()
            return ControlAuthorityHttpResponse(
                status_code=status,
                body=body,
                content_type=content_type,
                final_url=current,
            )
        raise adapter_error(WEB_ADAPTER_ERROR_INVALID_URL)
