"""Bezpečný HTTPS GET s allowlistem hostů, ručními redirecty a limitem těla.

Používají ARES a e-Sbírka. Klient kontrolních orgánů se nemění.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests import Response
from requests.exceptions import SSLError, Timeout

from core.version import APP_EXE_NAME, APP_VERSION

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5
_CHUNK_SIZE = 8192
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class SafeHttpsError(Exception):
    """Uživatelsky bezpečná chyba HTTPS požadavku (bez tracebacku v textu)."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class SafeHttpsResponse:
    status_code: int
    body: bytes
    final_url: str


def _user_agent() -> str:
    return f"{APP_EXE_NAME}/{APP_VERSION}"


def _is_ip_hostname(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def validate_https_url(url: str, *, allowed_hosts: frozenset[str]) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold()
    allowed = {item.casefold() for item in allowed_hosts}
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username
        or parsed.password
        or _is_ip_hostname(host)
        or host in {"localhost", "localhost.localdomain"}
        or host not in allowed
    ):
        raise SafeHttpsError("Neplatná adresa služby.", kind="invalid_url")
    return text


def _content_length(headers: Mapping[str, Any]) -> int | None:
    raw = headers.get("Content-Length") or headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _read_limited_body(response: Response, *, max_bytes: int) -> bytes:
    declared = _content_length(response.headers)
    if declared is not None and declared > max_bytes:
        logger.warning(
            "Content-Length %s překračuje limit %s bajtů",
            declared,
            max_bytes,
        )
        raise SafeHttpsError("Odpověď je příliš velká.", kind="too_large")

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            logger.warning(
                "Načtená odpověď překročila limit %s bajtů",
                max_bytes,
            )
            raise SafeHttpsError("Odpověď je příliš velká.", kind="too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def safe_https_get(
    url: str,
    *,
    allowed_hosts: frozenset[str],
    timeout: float,
    max_bytes: int,
    request: Callable[..., Response] | None = None,
    headers: dict[str, str] | None = None,
    max_redirects: int = _MAX_REDIRECTS,
) -> SafeHttpsResponse:
    """GET přes HTTPS na povolený host, bez automatických redirectů, s limitem těla."""
    current = validate_https_url(url, allowed_hosts=allowed_hosts)
    send = request or requests.request
    request_headers = {
        "User-Agent": _user_agent(),
        **(headers or {}),
    }
    limit = max(0, int(max_redirects))
    redirects_seen = 0
    while True:
        try:
            response = send(
                "GET",
                current,
                timeout=float(timeout),
                allow_redirects=False,
                verify=True,
                stream=True,
                headers=request_headers,
            )
        except SafeHttpsError:
            raise
        except Timeout:
            logger.exception("Timeout HTTPS požadavku na %s", current)
            raise SafeHttpsError(
                "Vypršel časový limit spojení.", kind="timeout"
            ) from None
        except SSLError:
            logger.exception("TLS chyba HTTPS požadavku na %s", current)
            raise SafeHttpsError("Služba není dostupná.", kind="network") from None
        except requests.RequestException:
            logger.exception("Síťová chyba HTTPS požadavku na %s", current)
            raise SafeHttpsError("Služba není dostupná.", kind="network") from None
        try:
            status = int(response.status_code)
            if status in _REDIRECT_STATUSES:
                if redirects_seen >= limit:
                    logger.warning(
                        "Překročen počet přesměrování HTTPS požadavku na %s",
                        current,
                    )
                    raise SafeHttpsError(
                        "Překročen počet přesměrování.", kind="invalid_url"
                    )
                location = str(response.headers.get("Location") or "").strip()
                if not location:
                    raise SafeHttpsError("Neplatná adresa služby.", kind="invalid_url")
                current = validate_https_url(
                    urljoin(current, location),
                    allowed_hosts=allowed_hosts,
                )
                redirects_seen += 1
                continue
            body = _read_limited_body(response, max_bytes=int(max_bytes))
        finally:
            response.close()
        return SafeHttpsResponse(
            status_code=status,
            body=body,
            final_url=current,
        )
