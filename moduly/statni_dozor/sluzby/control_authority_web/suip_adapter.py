"""Read-only adapter oblastních inspektorátů práce SÚIP."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urljoin, urlparse

from moduly.statni_dozor.constants import (
    OFFICE_KIND_REGIONAL,
    SUIP_AUTHORITY_CODE,
    SUIP_HUB_SOURCE_URL,
    SUIP_MAX_HTTP_REQUESTS,
    SUIP_OFFICE_EXTERNAL_KEYS,
    SUIP_OIP_CODES,
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

SUIP_ALLOWED_HOSTS = frozenset({"suip.gov.cz", "www.suip.gov.cz"})
SUIP_OIP_CODE_SET = frozenset(SUIP_OIP_CODES)
_OIP_TO_KEY = dict(zip(SUIP_OIP_CODES, SUIP_OFFICE_EXTERNAL_KEYS, strict=True))


def suip_office_detail_url(oip_code: str) -> str:
    return f"https://suip.gov.cz/web/{oip_code}/povinne-zverejnovane-informace"


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


def _element_siblings_after(node: HtmlNode) -> list[HtmlNode]:
    if node.parent is None:
        return []
    elements = [child for child in node.parent.children if isinstance(child, HtmlNode)]
    try:
        index = elements.index(node)
    except ValueError:
        return []
    return elements[index + 1 :]


def _next_paragraph(heading: HtmlNode) -> HtmlNode | None:
    for sibling in _element_siblings_after(heading):
        if sibling.tag in {"h3", "h4"}:
            return None
        if sibling.tag == "p":
            return sibling
    return None


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


def _is_regional_line(text: str) -> bool:
    folded = _fold_ascii(text)
    return "regionalnikancelar" in folded or "detasovanepracoviste" in folded


def _oip_code_from_href(href: str | None) -> str | None:
    if not href:
        return None
    path = urlparse(urljoin("https://suip.gov.cz/", href.strip())).path.casefold()
    for part in path.split("/"):
        if len(part) >= 5 and part.startswith("oip") and part[3:].isdigit():
            return part
    return None


def _heading_fold(node: HtmlNode) -> str:
    return _fold_ascii(node_text(node))


def _is_postal_heading(folded: str) -> bool:
    return folded.startswith("41") and "postovniadresa" in folded and not folded.startswith("410")


def _is_phone_heading(folded: str) -> bool:
    return folded.startswith("44") and "telefon" in folded


def _is_website_heading(folded: str) -> bool:
    return folded.startswith("45") and "internet" in folded


def _main_office_lines(lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        if _is_regional_line(line):
            break
        kept.append(line)
    return kept


def _phone_from_line(line: str) -> str | None:
    text = _normalize_space(line)
    lower = text.casefold()
    fax_at = lower.find("fax")
    if fax_at == 0:
        return None
    if fax_at > 0:
        text = text[:fax_at]
    if not _fold_ascii(text).startswith("tel"):
        return None
    started = False
    chars: list[str] = []
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


def _pick_office_email(tree: HtmlNode) -> str | None:
    found: list[str] = []
    seen: set[str] = set()
    for node in iter_nodes(tree):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = (node.get("href") or "").strip()
        if not href.casefold().startswith("mailto:"):
            continue
        address = href.split(":", 1)[1].split("?", 1)[0].strip().casefold()
        if not address.endswith("@suip.gov.cz"):
            continue
        if address in seen:
            continue
        seen.add(address)
        found.append(address)
    preferred = [
        item
        for item in found
        if not item.startswith("epodatelna.") and item != "epodatelna@suip.gov.cz"
    ]
    if len(preferred) == 1:
        return preferred[0]
    office_boxes = [
        item
        for item in found
        if item.startswith("epodatelna.") and item != "epodatelna@suip.gov.cz"
    ]
    if not preferred and len(office_boxes) == 1:
        return office_boxes[0]
    return None


def _website_from_paragraph(paragraph: HtmlNode, oip_code: str) -> str | None:
    for node in iter_nodes(paragraph):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = node.get("href") or ""
        code = _oip_code_from_href(href)
        if code == oip_code:
            return f"https://suip.gov.cz/web/{oip_code}"
        text_code = _oip_code_from_href(node_text(node))
        if text_code == oip_code:
            return f"https://suip.gov.cz/web/{oip_code}"
    return None


def parse_suip_hub_html(html: str) -> tuple[str, ...]:
    """Najde kódy oip03–oip10 v rozcestníku. Nevolá síť."""
    tree = parse_html_tree(html or "")
    seen: set[str] = set()
    extra = False
    found_link = False
    for node in iter_nodes(tree):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        code = _oip_code_from_href(node.get("href"))
        if code is None:
            continue
        found_link = True
        if code not in SUIP_OIP_CODE_SET:
            extra = True
            continue
        seen.add(code)
    if not found_link:
        logger.error("Rozcestník SÚIP neobsahuje odkazy na oblastní inspektoráty.")
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    if extra or seen != SUIP_OIP_CODE_SET:
        logger.error("Rozcestník SÚIP nemá přesně osm OIP: %s extra=%s", sorted(seen), extra)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    return SUIP_OIP_CODES


def parse_suip_office_html(
    html: str,
    *,
    oip_code: str,
    source_url: str,
) -> ControlAuthorityOfficeWebRecord:
    """Čistě parsuje detailní stránku jednoho OIP. Identita je oip_code, ne pořadí HTML."""
    code = str(oip_code or "").strip().casefold()
    if code not in SUIP_OIP_CODE_SET:
        logger.error("Neočekávaný kód OIP %s", oip_code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    tree = parse_html_tree(html or "")
    headings = [
        node
        for node in iter_nodes(tree)
        if isinstance(node, HtmlNode) and node.tag in {"h3", "h4"}
    ]
    postal = None
    phone_heading = None
    website_heading = None
    for heading in headings:
        folded = _heading_fold(heading)
        if postal is None and _is_postal_heading(folded):
            postal = heading
        elif phone_heading is None and _is_phone_heading(folded):
            phone_heading = heading
        elif website_heading is None and _is_website_heading(folded):
            website_heading = heading
    if postal is None:
        logger.error("Stránka %s nemá kontaktní poštovní adresu.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    paragraph = _next_paragraph(postal)
    if paragraph is None:
        logger.error("Stránka %s nemá odstavec s adresou.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    lines = _main_office_lines(_block_lines(paragraph))
    if not lines or "oblastniinspektoratprace" not in _fold_ascii(lines[0]):
        logger.error("Stránka %s nemá název oblastního inspektorátu.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    name = lines[0]
    address_parts = lines[1:]
    address = ", ".join(address_parts)
    if not address or not any(char.isdigit() for char in address):
        logger.error("Stránka %s nemá úplnou adresu OIP.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)

    observed = {"name", "address", "office_kind", "source_url"}
    phone = None
    if phone_heading is not None:
        phone_p = _next_paragraph(phone_heading)
        if phone_p is not None:
            for line in _block_lines(phone_p):
                phone = _phone_from_line(line)
                if phone:
                    observed.add("phone")
                    break
    email = _pick_office_email(tree)
    if email:
        observed.add("email")
    website = None
    if website_heading is not None:
        web_p = _next_paragraph(website_heading)
        if web_p is not None:
            website = _website_from_paragraph(web_p, code)
            if website:
                observed.add("website")
    return ControlAuthorityOfficeWebRecord(
        authority_code=SUIP_AUTHORITY_CODE,
        external_key=_OIP_TO_KEY[code],
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


def _complete_suip_records(
    records: list[ControlAuthorityOfficeWebRecord],
) -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    keys = [record.external_key for record in records]
    if len(keys) != len(set(keys)):
        logger.error("Duplicitní klíč OIP v výsledku SÚIP: %s", keys)
        raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
    by_key = {record.external_key: record for record in records}
    if set(by_key) != set(SUIP_OFFICE_EXTERNAL_KEYS):
        logger.error("Neúplný seznam OIP: %s", sorted(by_key))
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    ordered = tuple(by_key[key] for key in SUIP_OFFICE_EXTERNAL_KEYS)
    for record in ordered:
        if not record.name or not record.address:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if record.authority_code != SUIP_AUTHORITY_CODE:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    return ordered


def fetch_suip_offices(
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    source_url: str = SUIP_HUB_SOURCE_URL,
) -> ControlAuthorityWebFetchResult:
    """Stáhne rozcestník a osm detailních stránek OIP. Nejvýše 9 požadavků."""
    hub_url = validate_official_https_url(
        source_url, allowed_hosts=SUIP_ALLOWED_HOSTS
    )
    requests_used = 0

    def getter(url: str) -> ControlAuthorityHttpResponse:
        nonlocal requests_used
        requests_used += 1
        if requests_used > SUIP_MAX_HTTP_REQUESTS:
            logger.error("Překročen limit požadavků adapteru SÚIP.")
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if isinstance(http_get, ControlAuthorityHttpClient):
            return http_get.get(url, allowed_hosts=SUIP_ALLOWED_HOSTS)
        if http_get is not None:
            return http_get(url)
        return ControlAuthorityHttpClient().get(url, allowed_hosts=SUIP_ALLOWED_HOSTS)

    hub = getter(hub_url)
    parse_suip_hub_html(_decode_html(hub.body))
    records: list[ControlAuthorityOfficeWebRecord] = []
    for code in SUIP_OIP_CODES:
        detail_url = validate_official_https_url(
            suip_office_detail_url(code), allowed_hosts=SUIP_ALLOWED_HOSTS
        )
        response = getter(detail_url)
        records.append(
            parse_suip_office_html(
                _decode_html(response.body),
                oip_code=code,
                source_url=detail_url,
            )
        )
    complete = _complete_suip_records(records)
    stamp = (clock or datetime.now)()
    return ControlAuthorityWebFetchResult(
        authority_code=SUIP_AUTHORITY_CODE,
        source_url=hub_url,
        fetched_at=stamp,
        records=complete,
        warnings=(),
        is_complete=len(complete) == 8,
    )
