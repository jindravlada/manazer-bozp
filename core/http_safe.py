"""Bezpečný HTTPS GET s allowlistem hostů, ručními redirecty a limitem těla.

Používají ARES a e-Sbírka. Klient kontrolních orgánů se nemění.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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
SAFE_HTTPS_RETRYABLE_STATUSES = frozenset({429, 503})
SAFE_HTTPS_MAX_RETRY_AFTER_SECONDS = 30.0
SAFE_HTTPS_RETRY_BACKOFF_SECONDS = 0.5


class SafeHttpsError(Exception):
    """Uživatelsky bezpečná chyba HTTPS požadavku (bez tracebacku v textu)."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


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


def _header_value(headers: Mapping[str, Any], name: str) -> str:
    for key, value in headers.items():
        if str(key).casefold() == name.casefold():
            return str(value or "").strip()
    return ""


def parse_retry_after_seconds(
    headers: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    maximum: float = SAFE_HTTPS_MAX_RETRY_AFTER_SECONDS,
) -> float | None:
    if not headers:
        return None
    raw = _header_value(headers, "Retry-After")
    if not raw:
        return None
    cap = max(0.0, float(maximum))
    if raw.isdigit():
        return min(float(int(raw)), cap)
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    wait = (parsed - moment).total_seconds()
    return min(max(0.0, wait), cap)


def retry_backoff_seconds(attempt: int) -> float:
    exponent = max(0, int(attempt))
    return min(
        SAFE_HTTPS_RETRY_BACKOFF_SECONDS * (2**exponent),
        SAFE_HTTPS_MAX_RETRY_AFTER_SECONDS,
    )


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


def _sender(
    request: Callable[..., Response] | None,
    session: requests.Session | None,
) -> Callable[..., Response]:
    if request is not None:
        return request
    if session is not None:
        return session.request
    return requests.request


def safe_https_get(
    url: str,
    *,
    allowed_hosts: frozenset[str],
    timeout: float,
    max_bytes: int,
    request: Callable[..., Response] | None = None,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
    max_redirects: int = _MAX_REDIRECTS,
    max_retries: int = 0,
    sleep: Callable[[float], None] | None = None,
) -> SafeHttpsResponse:
    """GET přes HTTPS na povolený host, bez automatických redirectů, s limitem těla.

    Opakuje se jen při HTTP 429, HTTP 503 a timeoutu, nejvýše ``max_retries``-krát.
    Výchozí ``max_retries=0`` zachovává původní chování ARES a HTML e-Sbírky.
    """
    original = validate_https_url(url, allowed_hosts=allowed_hosts)
    send = _sender(request, session)
    wait = time.sleep if sleep is None else sleep
    request_headers = {
        "User-Agent": _user_agent(),
        **(headers or {}),
    }
    redirect_limit = max(0, int(max_redirects))
    attempts = max(0, int(max_retries)) + 1

    for attempt in range(attempts):
        current = original
        redirects_seen = 0
        retry_after: float | None = None
        try:
            while True:
                response = send(
                    "GET",
                    current,
                    timeout=float(timeout),
                    allow_redirects=False,
                    verify=True,
                    stream=True,
                    headers=request_headers,
                )
                try:
                    status = int(response.status_code)
                    if status in _REDIRECT_STATUSES:
                        if redirects_seen >= redirect_limit:
                            logger.warning(
                                "Překročen počet přesměrování HTTPS požadavku na %s",
                                current,
                            )
                            raise SafeHttpsError(
                                "Překročen počet přesměrování.", kind="invalid_url"
                            )
                        location = str(response.headers.get("Location") or "").strip()
                        if not location:
                            raise SafeHttpsError(
                                "Neplatná adresa služby.", kind="invalid_url"
                            )
                        current = validate_https_url(
                            urljoin(current, location),
                            allowed_hosts=allowed_hosts,
                        )
                        redirects_seen += 1
                        continue
                    if (
                        status in SAFE_HTTPS_RETRYABLE_STATUSES
                        and attempt < attempts - 1
                    ):
                        retry_after = parse_retry_after_seconds(response.headers)
                        break
                    body = _read_limited_body(response, max_bytes=int(max_bytes))
                finally:
                    response.close()
                return SafeHttpsResponse(
                    status_code=status,
                    body=body,
                    final_url=current,
                )
        except SafeHttpsError:
            raise
        except Timeout:
            if attempt >= attempts - 1:
                logger.exception("Timeout HTTPS požadavku na %s", original)
                raise SafeHttpsError(
                    "Vypršel časový limit spojení.", kind="timeout"
                ) from None
            logger.warning(
                "Timeout HTTPS požadavku na %s, pokus %s/%s",
                original,
                attempt + 1,
                attempts,
            )
            wait(retry_backoff_seconds(attempt))
            continue
        except SSLError:
            logger.exception("TLS chyba HTTPS požadavku na %s", original)
            raise SafeHttpsError("Služba není dostupná.", kind="network") from None
        except requests.RequestException:
            logger.exception("Síťová chyba HTTPS požadavku na %s", original)
            raise SafeHttpsError("Služba není dostupná.", kind="network") from None

        wait(
            retry_after
            if retry_after is not None
            else retry_backoff_seconds(attempt)
        )

    raise SafeHttpsError("Služba není dostupná.", kind="network")
