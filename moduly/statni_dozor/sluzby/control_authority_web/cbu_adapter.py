"""Read-only adapter obvodních báňských úřadů ČBÚ."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import datetime

from moduly.statni_dozor.constants import (
    CBU_AUTHORITY_CODE,
    CBU_MAX_HTTP_REQUESTS,
    CBU_OFFICE_EXTERNAL_KEYS,
    CBU_OFFICES_SOURCE_URL,
    CBU_OBU_CODES,
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

CBU_ALLOWED_HOSTS = frozenset({"cbu.gov.cz", "www.cbu.gov.cz"})
CBU_OBU_CODE_SET = frozenset(CBU_OBU_CODES)
_OBU_TO_KEY = dict(zip(CBU_OBU_CODES, CBU_OFFICE_EXTERNAL_KEYS, strict=True))


def cbu_office_detail_url(office_code: str) -> str:
    return f"https://cbu.gov.cz/obu/{office_code}"


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
        if sibling.tag in {"h2", "h3"}:
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


def _heading_fold(node: HtmlNode) -> str:
    return _fold_ascii(node_text(node))


def _kontakt_root(tree: HtmlNode) -> HtmlNode | None:
    for node in iter_nodes(tree):
        if not isinstance(node, HtmlNode):
            continue
        labelled = (node.get("aria-labelledby") or "").casefold()
        if node.tag == "section" and labelled == "kontakt":
            return node
        node_id = (node.get("id") or "").casefold()
        if node.tag in {"h2", "h3"} and (
            node_id == "kontakt" or "kontaktniudaje" in _heading_fold(node)
        ):
            return node.parent or node
    return None


def _is_skip_address_line(text: str) -> bool:
    folded = _fold_ascii(text)
    if folded.startswith("ico") or folded.startswith("icoo"):
        return True
    if "pobox" in folded or "poboxu" in folded:
        return True
    if folded.startswith("datovaschr") or "datovaschr" in folded:
        return True
    return False


def _is_office_name(text: str) -> bool:
    folded = _fold_ascii(text)
    return folded.startswith("obvodnibanskyurad") and "prouzemi" in folded


def _phone_from_line(line: str) -> str | None:
    text = _normalize_space(line)
    lower = text.casefold()
    folded = _fold_ascii(text)
    if folded.startswith("fax") or "inspekcni" in folded:
        return None
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


def _office_email(paragraph: HtmlNode) -> str | None:
    found: list[str] = []
    seen: set[str] = set()
    for node in iter_nodes(paragraph):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = (node.get("href") or "").strip()
        if not href.casefold().startswith("mailto:"):
            continue
        address = href.split(":", 1)[1].split("?", 1)[0].strip().casefold()
        if not address.endswith("@cbu.gov.cz"):
            continue
        local = address.split("@", 1)[0]
        if local == "podatelna":
            continue
        if not local.startswith("podatelna."):
            continue
        if address in seen:
            continue
        seen.add(address)
        found.append(address)
    if len(found) == 1:
        return found[0]
    return None


def parse_cbu_office_html(
    html: str,
    *,
    office_code: str,
    source_url: str,
) -> ControlAuthorityOfficeWebRecord:
    """Čistě parsuje detailní stránku jednoho OBÚ. Identita je office_code."""
    code = str(office_code or "").strip().casefold()
    if code not in CBU_OBU_CODE_SET:
        logger.error("Neočekávaný kód OBÚ %s", office_code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    tree = parse_html_tree(html or "")
    root = _kontakt_root(tree)
    if root is None:
        logger.error("Stránka %s nemá sekci kontaktních údajů.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    address_heading = None
    phone_heading = None
    for node in iter_nodes(root):
        if not isinstance(node, HtmlNode) or node.tag not in {"h3", "h4"}:
            continue
        folded = _heading_fold(node)
        if address_heading is None and folded == "adresa":
            address_heading = node
        elif phone_heading is None and folded.startswith("telefon"):
            phone_heading = node
    if address_heading is None:
        logger.error("Stránka %s nemá nadpis adresy.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    paragraph = _next_paragraph(address_heading)
    if paragraph is None:
        logger.error("Stránka %s nemá odstavec s adresou.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    name = None
    address_parts: list[str] = []
    for line in _block_lines(paragraph):
        if _is_skip_address_line(line):
            continue
        if name is None and _is_office_name(line):
            name = line
            continue
        if name is None:
            continue
        address_parts.append(line)
    address = ", ".join(address_parts)
    if not name:
        logger.error("Stránka %s nemá oficiální název OBÚ.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    if not address or not any(char.isdigit() for char in address):
        logger.error("Stránka %s nemá úplnou adresu sídla OBÚ.", code)
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)

    observed = {"name", "address", "office_kind", "source_url", "website"}
    phone = None
    email = None
    if phone_heading is not None:
        phone_p = _next_paragraph(phone_heading)
        if phone_p is not None:
            for line in _block_lines(phone_p):
                phone = _phone_from_line(line)
                if phone:
                    observed.add("phone")
                    break
            email = _office_email(phone_p)
            if email:
                observed.add("email")
    website = cbu_office_detail_url(code)
    return ControlAuthorityOfficeWebRecord(
        authority_code=CBU_AUTHORITY_CODE,
        external_key=_OBU_TO_KEY[code],
        name=name,
        address=address,
        phone=phone,
        email=email,
        website=website,
        territorial_scope=None,
        office_kind=OFFICE_KIND_TERRITORIAL,
        source_url=source_url,
        observed_fields=frozenset(observed),
    )


def _complete_cbu_records(
    records: list[ControlAuthorityOfficeWebRecord],
) -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    keys = [record.external_key for record in records]
    if len(keys) != len(set(keys)):
        logger.error("Duplicitní klíč OBÚ v výsledku ČBÚ: %s", keys)
        raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
    by_key = {record.external_key: record for record in records}
    if set(by_key) != set(CBU_OFFICE_EXTERNAL_KEYS):
        logger.error("Neúplný seznam OBÚ: %s", sorted(by_key))
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    ordered = tuple(by_key[key] for key in CBU_OFFICE_EXTERNAL_KEYS)
    for record in ordered:
        if not record.name or not record.address:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if record.authority_code != CBU_AUTHORITY_CODE:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    return ordered


def fetch_cbu_offices(
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ControlAuthorityWebFetchResult:
    """Stáhne sedm detailních stránek OBÚ. Nejvýše 7 požadavků, bez rozcestníku."""
    requests_used = 0

    def getter(url: str) -> ControlAuthorityHttpResponse:
        nonlocal requests_used
        requests_used += 1
        if requests_used > CBU_MAX_HTTP_REQUESTS:
            logger.error("Překročen limit požadavků adapteru ČBÚ.")
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if isinstance(http_get, ControlAuthorityHttpClient):
            return http_get.get(url, allowed_hosts=CBU_ALLOWED_HOSTS)
        if http_get is not None:
            return http_get(url)
        return ControlAuthorityHttpClient().get(url, allowed_hosts=CBU_ALLOWED_HOSTS)

    records: list[ControlAuthorityOfficeWebRecord] = []
    for code in CBU_OBU_CODES:
        detail_url = validate_official_https_url(
            cbu_office_detail_url(code), allowed_hosts=CBU_ALLOWED_HOSTS
        )
        response = getter(detail_url)
        records.append(
            parse_cbu_office_html(
                _decode_html(response.body),
                office_code=code,
                source_url=detail_url,
            )
        )
    complete = _complete_cbu_records(records)
    stamp = (clock or datetime.now)()
    return ControlAuthorityWebFetchResult(
        authority_code=CBU_AUTHORITY_CODE,
        source_url=CBU_OFFICES_SOURCE_URL,
        fetched_at=stamp,
        records=complete,
        warnings=(),
        is_complete=len(complete) == 7,
    )
