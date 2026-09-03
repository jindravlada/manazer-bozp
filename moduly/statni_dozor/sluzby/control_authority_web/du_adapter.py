"""Read-only adapter pracovišť Drážního úřadu."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import datetime

from moduly.statni_dozor.constants import (
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    DU_OFFICES_SOURCE_URL,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_TERRITORIAL,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY,
    WEB_ADAPTER_ERROR_INCOMPLETE,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
)
from moduly.statni_dozor.sluzby.control_authority_web.html_tree import (
    HtmlNode,
    iter_nodes,
    node_text,
    parse_html_tree,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpClient,
    ControlAuthorityHttpResponse,
    HttpGet,
    validate_official_https_url,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
    adapter_error,
)

logger = logging.getLogger(__name__)

DU_ALLOWED_HOSTS = frozenset({"du.gov.cz", "www.du.gov.cz"})

_CITY_KIND = {
    "praha": OFFICE_KIND_HEADQUARTERS,
    "plzen": OFFICE_KIND_TERRITORIAL,
    "olomouc": OFFICE_KIND_TERRITORIAL,
}
_CITY_DISPLAY = {
    "praha": "Pracoviště Praha",
    "plzen": "Pracoviště Plzeň",
    "olomouc": "Pracoviště Olomouc",
}
_CITY_KEY = {
    "praha": "du:praha",
    "plzen": "du:plzen",
    "olomouc": "du:olomouc",
}
_KNOWN_CITIES = ("praha", "plzen", "olomouc")


def _fold_ascii(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch.casefold() for ch in ascii_text if ch.isalnum())


def _normalize_space(value: str | None) -> str:
    if not value:
        return ""
    text = (
        str(value)
        .replace("\xa0", " ")
        .replace("\u202f", " ")
        .replace("\u2009", " ")
    )
    return " ".join(text.split())


def _city_from_label(label: str) -> str | None:
    folded = _fold_ascii(label)
    found = [city for city in _KNOWN_CITIES if city in folded]
    if len(found) == 1:
        return found[0]
    return None


def _optional_contact(value: str | None) -> str | None:
    text = _normalize_space(value)
    if not text:
        return None
    cleaned = text.replace("\u29c9", "").replace("⧉", "")
    return _normalize_space(cleaned) or None


def _looks_like_office_tab(label: str) -> bool:
    return "pracovist" in _fold_ascii(label)


def _table_pairs(table: HtmlNode) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for node in iter_nodes(table):
        if not isinstance(node, HtmlNode) or node.tag != "tr":
            continue
        cells = [child for child in node.children if isinstance(child, HtmlNode)]
        ths = [child for child in cells if child.tag == "th"]
        tds = [child for child in cells if child.tag == "td"]
        if not ths or not tds:
            continue
        key = _fold_ascii(node_text(ths[0]))
        value = _normalize_space(node_text(tds[0]))
        if key and key not in pairs:
            pairs[key] = value
    return pairs


def _find_contact_pairs(panel: HtmlNode) -> dict[str, str] | None:
    for node in iter_nodes(panel):
        if not isinstance(node, HtmlNode) or node.tag != "table":
            continue
        pairs = _table_pairs(node)
        if "adresa" in pairs:
            return pairs
    return None


def _decode_html(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def parse_du_offices_html(
    html: str,
    *,
    source_url: str = DU_OFFICES_SOURCE_URL,
) -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    """Čistě parsuje HTML Drážního úřadu. Nevolá síť ani čas."""
    tree = parse_html_tree(html or "")
    buttons = [
        node
        for node in iter_nodes(tree)
        if isinstance(node, HtmlNode)
        and node.tag == "button"
        and node.has_class("gov-tabs__link")
    ]
    if not buttons:
        logger.error("Stránka Drážního úřadu neobsahuje očekávané záložky pracovišť.")
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    by_id = {
        node.get("id"): node
        for node in iter_nodes(tree)
        if isinstance(node, HtmlNode) and node.get("id")
    }
    found: dict[str, ControlAuthorityOfficeWebRecord] = {}
    extra = False
    for button in buttons:
        label = _normalize_space(node_text(button))
        city = _city_from_label(label)
        if city is None:
            if _looks_like_office_tab(label):
                extra = True
            continue
        if city in found:
            logger.error("Duplicitní pracoviště Drážního úřadu: %s", city)
            raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
        panel_id = button.get("aria-controls")
        panel = by_id.get(panel_id) if panel_id else None
        if panel is None:
            logger.error("Záložka pracoviště %s nemá obsah.", city)
            raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
        pairs = _find_contact_pairs(panel)
        if pairs is None:
            logger.error("Pracoviště %s nemá tabulku s adresou.", city)
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        address = _normalize_space(pairs.get("adresa"))
        name = _CITY_DISPLAY[city]
        phone = _optional_contact(pairs.get("telefon"))
        email = _optional_contact(pairs.get("email"))
        if not name or not address:
            logger.error("Pracoviště %s nemá název nebo adresu.", city)
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        observed = {"name", "address", "office_kind", "source_url"}
        if "telefon" in pairs:
            observed.add("phone")
        if "email" in pairs:
            observed.add("email")
        found[city] = ControlAuthorityOfficeWebRecord(
            authority_code=DU_AUTHORITY_CODE,
            external_key=_CITY_KEY[city],
            name=name,
            address=address,
            phone=phone,
            email=email,
            website=None,
            territorial_scope=None,
            office_kind=_CITY_KIND[city],
            source_url=source_url,
            observed_fields=frozenset(observed),
        )

    if extra or len(found) != 3:
        logger.error(
            "Neúplný seznam pracovišť Drážního úřadu: %s",
            sorted(found),
        )
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)

    records = tuple(found[city] for city in _KNOWN_CITIES)
    keys = tuple(record.external_key for record in records)
    if keys != DU_OFFICE_EXTERNAL_KEYS:
        logger.error("Neočekávané klíče pracovišť Drážního úřadu: %s", keys)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    if len(set(keys)) != 3:
        raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
    return records


def fetch_du_offices(
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    source_url: str = DU_OFFICES_SOURCE_URL,
) -> ControlAuthorityWebFetchResult:
    """Stáhne oficiální stránku a vrátí kompletní seznam tří pracovišť."""
    validated = validate_official_https_url(
        source_url, allowed_hosts=DU_ALLOWED_HOSTS
    )

    def getter(url: str) -> ControlAuthorityHttpResponse:
        if isinstance(http_get, ControlAuthorityHttpClient):
            return http_get.get(url, allowed_hosts=DU_ALLOWED_HOSTS)
        if http_get is not None:
            return http_get(url)
        return ControlAuthorityHttpClient().get(url, allowed_hosts=DU_ALLOWED_HOSTS)

    response = getter(validated)
    html = _decode_html(response.body)
    records = parse_du_offices_html(html, source_url=validated)
    stamp = (clock or datetime.now)()
    return ControlAuthorityWebFetchResult(
        authority_code=DU_AUTHORITY_CODE,
        source_url=validated,
        fetched_at=stamp,
        records=records,
        warnings=(),
        is_complete=len(records) == 3,
    )
