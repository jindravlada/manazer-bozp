"""Read-only adapter krajských ředitelství HZS ČR z centrálního přehledu."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urljoin, urlparse

from moduly.statni_dozor.constants import (
    HZS_AUTHORITY_CODE,
    HZS_MAX_HTTP_REQUESTS,
    HZS_OFFICE_EXTERNAL_KEYS,
    HZS_OFFICES_SOURCE_URL,
    HZS_REGION_SLUGS,
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

HZS_ALLOWED_HOSTS = frozenset({"hzscr.gov.cz", "www.hzscr.gov.cz"})
HZS_REGION_SLUG_SET = frozenset(HZS_REGION_SLUGS)
_SLUG_TO_KEY = dict(zip(HZS_REGION_SLUGS, HZS_OFFICE_EXTERNAL_KEYS, strict=True))

# Přesné oficiální popisky karet na hzscr.gov.cz, bez fuzzy párování.
_NAME_TO_KEY = {
    "hlavnimestopraha": "hzs:praha",
    "hzshlmprahy": "hzs:praha",
    "stredoceskykraj": "hzs:stredocesky-kraj",
    "hzsstredoceskehokraje": "hzs:stredocesky-kraj",
    "jihoceskykraj": "hzs:jihocesky-kraj",
    "hzsjihoceskehokraje": "hzs:jihocesky-kraj",
    "plzenskykraj": "hzs:plzensky-kraj",
    "hzsplzenskehokraje": "hzs:plzensky-kraj",
    "karlovarskykraj": "hzs:karlovarsky-kraj",
    "hzskarlovarskehokraje": "hzs:karlovarsky-kraj",
    "usteckykraj": "hzs:ustecky-kraj",
    "hzsusteckehokraje": "hzs:ustecky-kraj",
    "libereckykraj": "hzs:liberecky-kraj",
    "hzslibereckehokraje": "hzs:liberecky-kraj",
    "kralovehradeckykraj": "hzs:kralovehradecky-kraj",
    "hzskralovehradeckehokraje": "hzs:kralovehradecky-kraj",
    "pardubickykraj": "hzs:pardubicky-kraj",
    "hzspardubickehokraje": "hzs:pardubicky-kraj",
    "krajvysocina": "hzs:kraj-vysocina",
    "hzskrajevysocina": "hzs:kraj-vysocina",
    "jihomoravskykraj": "hzs:jihomoravsky-kraj",
    "hzsjihomoravskehokraje": "hzs:jihomoravsky-kraj",
    "olomouckykraj": "hzs:olomoucky-kraj",
    "hzsolomouckehokraje": "hzs:olomoucky-kraj",
    "moravskoslezskykraj": "hzs:moravskoslezsky-kraj",
    "hzsmoravskoslezskehokraje": "hzs:moravskoslezsky-kraj",
    "zlinskykraj": "hzs:zlinsky-kraj",
    "hzszlinskehokraje": "hzs:zlinsky-kraj",
}

_IGNORED_NAME_FOLDS = frozenset(
    {
        "generalnireditelstvi",
        "generalnireditelstvihzscr",
        "ministerstvovnitra",
        "ministerstvovnitrageneralnireditelstvihzscr",
        "zachrannyutvarhzscr",
        "institutochranyobyvatelstva",
        "technickyustavpozarniochrany",
        "servisniaopravarenskezarizenihzscr",
        "sospovospo",
        "hasicskyutvarochranyprazskehohradu",
        "uzemniodbor",
        "hasicskastanice",
        "tiskovymluvci",
        "reditelhzs",
    }
)


def hzs_office_website(slug: str) -> str:
    return f"https://hzscr.gov.cz/{slug}"


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


def _is_ignored_name(folded: str) -> bool:
    if folded in _IGNORED_NAME_FOLDS:
        return True
    return any(folded.startswith(prefix) for prefix in _IGNORED_NAME_FOLDS)


def _looks_like_unexpected_region(folded_name: str, slug: str | None) -> bool:
    if slug and slug not in HZS_REGION_SLUG_SET:
        if slug == "hlavni-mesto-praha" or slug.endswith("-kraj"):
            return True
    if folded_name.startswith("hzs") and "kraj" in folded_name:
        return True
    if folded_name.endswith("kraj") and folded_name not in _NAME_TO_KEY:
        return True
    return False


def _region_slug(href: str, *, source_url: str) -> str | None:
    href = str(href or "").strip()
    if not href or href.startswith("#") or href.casefold().startswith("mailto:"):
        return None
    parsed = urlparse(urljoin(source_url, href))
    host = (parsed.hostname or "").casefold()
    if host and host not in {item.casefold() for item in HZS_ALLOWED_HOSTS}:
        return None
    parts = [part for part in (parsed.path or "").split("/") if part]
    if len(parts) != 1:
        return None
    return parts[0].casefold()


def _anchor_title(anchor: HtmlNode) -> str:
    for node in iter_nodes(anchor):
        if isinstance(node, HtmlNode) and node.has_class("text-headline-s"):
            title = _normalize_space(node_text(node))
            if title:
                return title
    return _normalize_space(node_text(anchor))


def parse_hzs_offices_html(
    html: str,
    *,
    source_url: str = HZS_OFFICES_SOURCE_URL,
) -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    """Čistě parsuje centrální přehled HZS krajů. Nevolá síť."""
    tree = parse_html_tree(html or "")
    found: dict[str, ControlAuthorityOfficeWebRecord] = {}
    extra = False
    saw_card = False
    for node in iter_nodes(tree):
        if not isinstance(node, HtmlNode) or node.tag != "a":
            continue
        href = (node.get("href") or "").strip()
        if not href:
            continue
        title = _anchor_title(node)
        if not title:
            continue
        saw_card = True
        folded = _fold_ascii(title)
        slug = _region_slug(href, source_url=source_url)
        slug_key = _SLUG_TO_KEY.get(slug or "")
        name_key = _NAME_TO_KEY.get(folded)
        if slug_key and name_key and slug_key != name_key:
            logger.error(
                "Konflikt identity HZS: název %s neodpovídá odkazu %s",
                title,
                href,
            )
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        key = slug_key or name_key
        if key is None:
            if _is_ignored_name(folded):
                continue
            if _looks_like_unexpected_region(folded, slug):
                extra = True
            continue
        if key in found:
            logger.error("Duplicitní krajské HZS v přehledu: %s", key)
            raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
        website = hzs_office_website(slug) if slug in HZS_REGION_SLUG_SET else None
        if website is None:
            extra = True
            continue
        observed = {"name", "website", "office_kind", "source_url"}
        found[key] = ControlAuthorityOfficeWebRecord(
            authority_code=HZS_AUTHORITY_CODE,
            external_key=key,
            name=title,
            address=None,
            phone=None,
            email=None,
            website=website,
            territorial_scope=None,
            office_kind=OFFICE_KIND_REGIONAL,
            source_url=source_url,
            observed_fields=frozenset(observed),
        )

    if not saw_card and not found:
        logger.error("Přehled HZS krajů nemá očekávané karty ředitelství.")
        raise adapter_error(WEB_ADAPTER_ERROR_UNREADABLE_HTML)
    if extra or set(found) != set(HZS_OFFICE_EXTERNAL_KEYS):
        logger.error(
            "Neúplný nebo neočekávaný seznam krajských HZS: %s extra=%s",
            sorted(found),
            extra,
        )
        raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    ordered = tuple(found[key] for key in HZS_OFFICE_EXTERNAL_KEYS)
    keys = tuple(item.external_key for item in ordered)
    if len(set(keys)) != 14:
        raise adapter_error(WEB_ADAPTER_ERROR_DUPLICATE_KEY)
    for record in ordered:
        if not record.name or not record.website:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if record.authority_code != HZS_AUTHORITY_CODE:
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
    return ordered


def fetch_hzs_offices(
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    source_url: str = HZS_OFFICES_SOURCE_URL,
) -> ControlAuthorityWebFetchResult:
    """Stáhne jednu stránku HZS krajů. Krajské weby ani detaily nestahuje."""
    validated = validate_official_https_url(
        source_url, allowed_hosts=HZS_ALLOWED_HOSTS
    )
    requests_used = 0

    def getter(url: str) -> ControlAuthorityHttpResponse:
        nonlocal requests_used
        requests_used += 1
        if requests_used > HZS_MAX_HTTP_REQUESTS:
            logger.error("Překročen limit požadavků adapteru HZS.")
            raise adapter_error(WEB_ADAPTER_ERROR_INCOMPLETE)
        if isinstance(http_get, ControlAuthorityHttpClient):
            return http_get.get(url, allowed_hosts=HZS_ALLOWED_HOSTS)
        if http_get is not None:
            return http_get(url)
        return ControlAuthorityHttpClient().get(url, allowed_hosts=HZS_ALLOWED_HOSTS)

    response = getter(validated)
    records = parse_hzs_offices_html(
        _decode_html(response.body),
        source_url=validated,
    )
    stamp = (clock or datetime.now)()
    return ControlAuthorityWebFetchResult(
        authority_code=HZS_AUTHORITY_CODE,
        source_url=validated,
        fetched_at=stamp,
        records=records,
        warnings=(),
        is_complete=len(records) == 14,
    )
