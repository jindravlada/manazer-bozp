"""Read-only adapter krajských hygienických stanic z přehledu MZD."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse

from moduly.statni_dozor.constants import (
    KHS_AUTHORITY_CODE,
    KHS_MAX_HTTP_REQUESTS,
    KHS_OFFICE_EXTERNAL_KEYS,
    KHS_OFFICES_SOURCE_URL,
    OFFICE_KIND_REGIONAL,
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

KHS_ALLOWED_HOSTS = frozenset({"mzd.gov.cz", "www.mzd.gov.cz"})

# Přesné složené varianty prvního sloupce tabulky MZD, bez fuzzy párování.
_NAME_TO_KEY = {
    "hshlmprahy": "khs:praha",
    "stredoceskehokraje": "khs:stredocesky-kraj",
    "jihoceskehokraje": "khs:jihocesky-kraj",
    "plzenskehokraje": "khs:plzensky-kraj",
    "karlovarskehokraje": "khs:karlovarsky-kraj",
    "usteckehokraje": "khs:ustecky-kraj",
    "libereckehokraje": "khs:liberecky-kraj",
    "kralovehradeckehokraje": "khs:kralovehradecky-kraj",
    "pardubickehokraje": "khs:pardubicky-kraj",
    "krajevysocina": "khs:kraj-vysocina",
    "jihomoravskehokraje": "khs:jihomoravsky-kraj",
    "olomouckehokraje": "khs:olomoucky-kraj",
    "moravskoslezskehokraje": "khs:moravskoslezsky-kraj",
    "zlinskehokraje": "khs:zlinsky-kraj",
}


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


def _decode_html(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _block_lines(node: HtmlNode) -> list[str]:
    lines: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = _normalize_space("".join(buf))
        buf.clear()
        if text:
            lines.append(text)

    def walk(item: HtmlNode | str) -> None:
        if isinstance(item, str):
            buf.append(item)
            return
        if item.tag == "br":
            flush()
            return
        for child in item.children:
            walk(child)

    walk(node)
    flush()
    return lines


def _direct_rows(table: HtmlNode) -> list[HtmlNode]:
    rows: list[HtmlNode] = []
    for child in table.children:
        if not isinstance(child, HtmlNode):
            continue
        if child.tag in {"thead", "tbody", "tfoot"}:
            for inner in child.children:
                if isinstance(inner, HtmlNode) and inner.tag == "tr":
                    rows.append(inner)
        elif child.tag == "tr":
            rows.append(child)
    return rows


def _row_cells(row: HtmlNode, tag: str) -> list[HtmlNode]:
    return [child for child in row.children if isinstance(child, HtmlNode) and child.tag == tag]


def _is_url_line(text: str) -> bool:
    folded = text.casefold()
    return folded.startswith("www.") or folded.startswith("http://") or folded.startswith("https://")


def _station_name(cell: HtmlNode) -> str | None:
    for line in _block_lines(cell):
        if _is_url_line(line):
            continue
        return line
    return None


def _website_from_cell(cell: HtmlNode) -> str | None:
    for node in iter_nodes(cell):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = (node.get("href") or "").strip()
        if not href:
            continue
        if href.casefold().startswith("mailto:"):
            continue
        parsed = urlparse(href)
        if parsed.scheme.casefold() not in {"http", "https"}:
            continue
        if parsed.hostname and parsed.hostname.casefold() in KHS_ALLOWED_HOSTS:
            continue
        return href
    return None


def _email_from_cell(cell: HtmlNode) -> str | None:
    for node in iter_nodes(cell):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = (node.get("href") or "").strip()
        if not href.casefold().startswith("mailto:"):
            continue
        address = href.split(":", 1)[1].split("?", 1)[0].strip()
        if "@" in address:
            return address
    text = _normalize_space(node_text(cell))
    if "@" in text and " " not in text:
        return text
    for part in text.split():
        if "@" in part:
            return part.strip(".,;")
    return None


def _phone_from_cell(cell: HtmlNode) -> str | None:
    text = _normalize_space(node_text(cell))
    if not text:
        return None
    chars: list[str] = []
    started = False
    for char in text:
        if not started and (char == "+" or char.isdigit()):
            started = True
        if started:
            if char.isdigit() or char in {"+", " "}:
                chars.append(char)
            else:
                break
    phone = _normalize_space("".join(chars))
    return phone or None


def _find_khs_table(tree: HtmlNode) -> HtmlNode | None:
    for node in iter_nodes(tree):
        if not isinstance(node, HtmlNode) or node.tag != "table":
            continue
        rows = _direct_rows(node)
        if not rows:
            continue
        header_cells = _row_cells(rows[0], "th") or _row_cells(rows[0], "td")
        folds = [_fold_ascii(node_text(cell)) for cell in header_cells]
        if any(item == "khs" or item.startswith("khs") for item in folds) and any(
            "adresa" in item for item in folds
        ):
            return node
    return None


def _header_index(headers: list[str], *needles: str) -> int | None:
    for index, header in enumerate(headers):
        if any(needle in header for needle in needles):
            return index
    return None


def parse_khs_offices_html(
    html: str,
    *,
    source_url: str = KHS_OFFICES_SOURCE_URL,
) -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    """Čistě parsuje centrální přehled KHS na MZD. Nevolá síť."""
    tree = parse_html_tree(html or "")
    table = _find_khs_table(tree)
    if table is None:
        logger.error("Přehled KHS na MZD neobsahuje očekávanou tabulku.")
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    rows = _direct_rows(table)
    header = rows[0]
    header_cells = _row_cells(header, "th") or _row_cells(header, "td")
    headers = [_fold_ascii(node_text(cell)) for cell in header_cells]
    name_i = _header_index(headers, "khs")
    address_i = _header_index(headers, "adresa")
    phone_i = _header_index(headers, "telefon")
    email_i = _header_index(headers, "email")
    if name_i is None or address_i is None:
        logger.error("Tabulka KHS nemá sloupce názvu a adresy.")
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    found: dict[str, ControlAuthorityOfficeWebRecord] = {}
    extra = False
    for row in rows[1:]:
        cells = _row_cells(row, "td")
        if not cells:
            continue
        if name_i >= len(cells) or address_i >= len(cells):
            continue
        name = _station_name(cells[name_i])
        if not name:
            continue
        key = _NAME_TO_KEY.get(_fold_ascii(name))
        if key is None:
            extra = True
            continue
        if key in found:
            logger.error("Duplicitní KHS v přehledu MZD: %s", key)
            raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
        address_parts = [
            line
            for line in _block_lines(cells[address_i])
            if line and not _is_url_line(line)
        ]
        address = ", ".join(address_parts)
        if not address or not any(char.isdigit() for char in address):
            logger.error("KHS %s nemá úplnou adresu v přehledu MZD.", key)
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        observed = {"name", "address", "office_kind", "source_url"}
        website = _website_from_cell(cells[name_i])
        if website:
            observed.add("website")
        phone = None
        if phone_i is not None and phone_i < len(cells):
            phone = _phone_from_cell(cells[phone_i])
            if phone:
                observed.add("phone")
        email = None
        if email_i is not None and email_i < len(cells):
            email = _email_from_cell(cells[email_i])
            if email:
                observed.add("email")
        found[key] = ControlAuthorityOfficeWebRecord(
            authority_code=KHS_AUTHORITY_CODE,
            external_key=key,
            name=name,
            address=address,
            phone=phone,
            email=email,
            website=website,
            territorial_scope=None,
            office_kind=OFFICE_KIND_REGIONAL,
            source_url=source_url,
            observed_fields=frozenset(observed),
        )

    if extra or set(found) != set(KHS_OFFICE_EXTERNAL_KEYS):
        logger.error(
            "Neúplný nebo neočekávaný seznam KHS: %s extra=%s",
            sorted(found),
            extra,
        )
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    ordered = tuple(found[key] for key in KHS_OFFICE_EXTERNAL_KEYS)
    keys = tuple(item.external_key for item in ordered)
    if len(set(keys)) != 14:
        raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
    return ordered


def fetch_khs_offices(
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    source_url: str = KHS_OFFICES_SOURCE_URL,
) -> ControlAuthorityWebFetchResult:
    """Stáhne jednu stránku MZD a vrátí 14 KHS. Jednotlivé weby KHS nestahuje."""
    validated = validate_official_https_url(
        source_url, allowed_hosts=KHS_ALLOWED_HOSTS
    )
    requests_used = 0

    def getter(url: str) -> ControlAuthorityHttpResponse:
        nonlocal requests_used
        requests_used += 1
        if requests_used > KHS_MAX_HTTP_REQUESTS:
            logger.error("Překročen limit požadavků adapteru KHS.")
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if isinstance(http_get, ControlAuthorityHttpClient):
            return http_get.get(url, allowed_hosts=KHS_ALLOWED_HOSTS)
        if http_get is not None:
            return http_get(url)
        return ControlAuthorityHttpClient().get(url, allowed_hosts=KHS_ALLOWED_HOSTS)

    response = getter(validated)
    records = parse_khs_offices_html(
        _decode_html(response.body),
        source_url=validated,
    )
    stamp = (clock or datetime.now)()
    return ControlAuthorityWebFetchResult(
        authority_code=KHS_AUTHORITY_CODE,
        source_url=validated,
        fetched_at=stamp,
        records=records,
        warnings=(),
        is_complete=len(records) == 14,
    )
