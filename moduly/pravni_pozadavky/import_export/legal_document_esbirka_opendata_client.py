from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence
from urllib.parse import urlencode, urlparse

from core.http_safe import SafeHttpsError, safe_https_get
from moduly.pravni_pozadavky.import_export.legal_document_number import (
    normalize_legal_act_number_and_year,
)

logger = logging.getLogger(__name__)

ESBIRKA_OPENDATA_HOST = "opendata.eselpoint.gov.cz"
ESBIRKA_OPENDATA_ALLOWED_HOSTS = frozenset({ESBIRKA_OPENDATA_HOST})
ESBIRKA_OPENDATA_BASE_URL = f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/eli/cz/sb"
ESBIRKA_ELI_CHECKSUM_PREFIX = "esbirka-eli:"
ESBIRKA_LEGACY_CHECKSUM_PREFIX = "esbirka:"
# Metadata aktu mají jednotky kB; rezerva na větší JSON-LD kontext.
ESBIRKA_OPENDATA_MAX_RESPONSE_BYTES = 262_144
# Zákoník práce 262/2006 má ~272 KiB metadata znění (~3000 IRI fragmentů).
ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES = 1_048_576
# SPARQL vrátí texty všech fragmentů znění v jedné odpovědi (~2 MiB u 262/2006).
ESBIRKA_OPENDATA_SPARQL_URL = f"https://{ESBIRKA_OPENDATA_HOST}/sparql"
ESBIRKA_OPENDATA_SPARQL_MAX_RESPONSE_BYTES = 8_388_608
_SPARQL_TIMEOUT = 60
_REQUEST_TIMEOUT = 30
_PRED_HAS_FRAGMENT = (
    "https://slovník.gov.cz/datový/sbírka/pojem/má-fragment-znění"
)
_PRED_CONTAINS_FRAGMENT = (
    "https://slovník.gov.cz/datový/sbírka/pojem/obsahuje-fragment"
)
_PRED_FRAGMENT_TEXT = (
    "https://slovník.gov.cz/datový/sbírka/pojem/text-fragmentu"
)
_PRED_FRAGMENT_TYPE = (
    "https://slovník.gov.cz/datový/sbírka/pojem/má-typ-fragmentu"
)
_LAST_WORDING_LOCAL_NAME = "má-poslední-znění"
_WORDINGS_LOCAL_NAME = "má-znění"
_FRAGMENTS_LOCAL_NAME = "má-fragment-znění"
_EFFECTIVE_FROM_LOCAL_NAME = "účinnost-znění-od"
_EFFECTIVE_TO_LOCAL_NAME = "účinnost-znění-do"
_WORDING_TYPE_LOCAL_NAME = "má-typ-znění-právního-aktu"
_ELI_IN_VALUE_RE = re.compile(r"(eli/cz/sb/\d{4}/\d+/\d{4}-\d{2}-\d{2})")
_FRAGMENT_ELI_RE = re.compile(
    r"(eli/cz/sb/\d{4}/\d+/\d{4}-\d{2}-\d{2}(?:/dokument(?:/[A-Za-z0-9_.:-]+)*)?)"
)
_WORDING_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")
_ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
_PATH_SEGMENT_RE = re.compile(r"^([A-Za-z]+)(?:_([A-Za-z0-9.:-]+))?$")


@dataclass(frozen=True)
class ESbirkaOpenDataWording:
    last_wording_eli: str
    source_url: str
    effective_from: date | None
    version_label: str


@dataclass(frozen=True)
class ESbirkaOpenDataTemporalWording:
    source_eli: str
    source_url: str
    effective_from: date | None
    version_label: str


@dataclass(frozen=True)
class ESbirkaOpenDataFragmentRef:
    fragment_eli: str
    source_url: str
    list_index: int
    document_part: str
    path_segments: tuple[str, ...]
    section_kind: str
    section_number: str
    parent_path: str


@dataclass(frozen=True)
class ESbirkaOpenDataWordingDocument:
    source_eli: str
    source_url: str
    effective_from: date | None
    effective_to: date | None
    wording_type: str
    fragments: tuple[ESbirkaOpenDataFragmentRef, ...]


@dataclass(frozen=True)
class ESbirkaOpenDataFragmentContent:
    fragment_eli: str
    fragment_type: str
    html: str
    text: str


class LegalDocumentESbirkaOpenDataClient:
    def build_url(self, *, year: int | str, number: str) -> str:
        normalized_number, normalized_year = normalize_legal_act_number_and_year(
            number,
            year,
        )
        return f"{ESBIRKA_OPENDATA_BASE_URL}/{normalized_year}/{normalized_number}"

    def fetch_latest_wording(
        self,
        *,
        year: int | str,
        number: str,
    ) -> ESbirkaOpenDataWording:
        payload, url = self._fetch_act_payload(year=year, number=number)
        return self.extract_latest_wording(payload, source_url=url)

    def fetch_temporal_wordings(
        self,
        *,
        year: int | str,
        number: str,
    ) -> tuple[ESbirkaOpenDataTemporalWording, ...]:
        payload, url = self._fetch_act_payload(year=year, number=number)
        return self.extract_temporal_wordings(payload, source_url=url)

    def build_wording_url(self, source_eli: str) -> str:
        normalized = self.normalize_source_eli(source_eli)
        if not normalized:
            raise ValueError("Neočekávaný formát odpovědi.")
        return f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{normalized}"

    def fetch_wording_fragments(self, source_eli: str) -> ESbirkaOpenDataWordingDocument:
        normalized = self.normalize_source_eli(source_eli)
        if not normalized:
            raise ValueError("Neočekávaný formát odpovědi.")
        url = self.build_wording_url(normalized)
        payload, final_url = self._fetch_jsonld(
            url,
            max_bytes=ESBIRKA_OPENDATA_WORDING_MAX_RESPONSE_BYTES,
        )
        return self.extract_wording_fragments(
            payload,
            source_eli=normalized,
            source_url=final_url,
        )

    def fetch_in_force_wording_fragments(
        self,
        *,
        year: int | str,
        number: str,
        on_date: date,
    ) -> ESbirkaOpenDataWordingDocument:
        wordings = self.fetch_temporal_wordings(year=year, number=number)
        in_force = self.select_in_force_wording(wordings, on_date)
        if in_force is None:
            raise ValueError("Předpis nenalezen.")
        return self.fetch_wording_fragments(in_force.source_eli)

    def fetch_wording_fragment_contents(
        self,
        source_eli: str,
    ) -> tuple[ESbirkaOpenDataFragmentContent, ...]:
        normalized = self.normalize_source_eli(source_eli)
        if not normalized:
            raise ValueError("Neočekávaný formát odpovědi.")
        wording_iri = self.build_wording_url(normalized)
        query = (
            "SELECT ?frag ?text ?typ WHERE { "
            f"<{wording_iri}> <{_PRED_HAS_FRAGMENT}> ?frag . "
            f"?frag <{_PRED_CONTAINS_FRAGMENT}> ?c . "
            f"?c <{_PRED_FRAGMENT_TEXT}> ?text . "
            f"?c <{_PRED_FRAGMENT_TYPE}> ?typ . "
            "}"
        )
        payload = self._fetch_sparql(query)
        rows = self._sparql_bindings(payload)
        if not rows:
            raise ValueError("Neočekávaný formát odpovědi.")
        items: list[ESbirkaOpenDataFragmentContent] = []
        seen: set[str] = set()
        for row in rows:
            fragment_eli = self.normalize_fragment_eli(
                self._sparql_binding_value(row, "frag"),
                wording_eli=normalized,
            )
            html = self._sparql_binding_value(row, "text")
            fragment_type = self._fragment_type_code(
                self._sparql_binding_value(row, "typ"),
            )
            if not fragment_eli or fragment_eli in seen or not html.strip():
                continue
            seen.add(fragment_eli)
            items.append(
                ESbirkaOpenDataFragmentContent(
                    fragment_eli=fragment_eli,
                    fragment_type=fragment_type,
                    html=html,
                    text=html,
                )
            )
        if not items:
            raise ValueError("Neočekávaný formát odpovědi.")
        return tuple(items)

    def extract_latest_wording(
        self,
        payload: Any,
        *,
        source_url: str,
    ) -> ESbirkaOpenDataWording:
        record = self._select_act_record(payload)
        raw_value = self._find_last_wording_value(record)
        last_wording_eli = self.normalize_wording_eli(raw_value)
        if not last_wording_eli:
            raise ValueError("Neočekávaný formát odpovědi.")
        effective_from = self._parse_wording_date(last_wording_eli)
        return ESbirkaOpenDataWording(
            last_wording_eli=last_wording_eli,
            source_url=source_url,
            effective_from=effective_from,
            version_label=f"e-Sbírka {last_wording_eli}",
        )

    def extract_temporal_wordings(
        self,
        payload: Any,
        *,
        source_url: str,
    ) -> tuple[ESbirkaOpenDataTemporalWording, ...]:
        record = self._select_act_record(payload)
        items: list[ESbirkaOpenDataTemporalWording] = []
        seen: set[str] = set()
        for raw_value in self._find_wordings_values(record):
            wording = self._temporal_wording_from_value(raw_value, source_url=source_url)
            if wording is None or wording.source_eli in seen:
                continue
            seen.add(wording.source_eli)
            items.append(wording)
        if not items:
            last_wording = self._temporal_wording_from_value(
                self._find_last_wording_value(record),
                source_url=source_url,
            )
            if last_wording is not None:
                items.append(last_wording)
        if not items:
            raise ValueError("Neočekávaný formát odpovědi.")
        return tuple(
            sorted(
                items,
                key=lambda wording: (
                    wording.effective_from or date.min,
                    wording.source_eli,
                ),
            )
        )

    def select_in_force_wording(
        self,
        wordings: Sequence[ESbirkaOpenDataTemporalWording],
        on_date: date,
    ) -> ESbirkaOpenDataTemporalWording | None:
        applicable = [
            wording
            for wording in wordings
            if wording.effective_from is not None and wording.effective_from <= on_date
        ]
        if not applicable:
            return None
        return max(
            applicable,
            key=lambda wording: (wording.effective_from or date.min, wording.source_eli),
        )

    def select_future_wordings(
        self,
        wordings: Sequence[ESbirkaOpenDataTemporalWording],
        on_date: date,
    ) -> tuple[ESbirkaOpenDataTemporalWording, ...]:
        return tuple(
            wording
            for wording in wordings
            if wording.effective_from is not None and wording.effective_from > on_date
        )

    def extract_wording_fragments(
        self,
        payload: Any,
        *,
        source_eli: str,
        source_url: str,
    ) -> ESbirkaOpenDataWordingDocument:
        wording_eli = self.normalize_source_eli(source_eli)
        if not wording_eli:
            raise ValueError("Neočekávaný formát odpovědi.")
        record = self._select_wording_record(payload)
        raw_fragments = self._find_fragment_values(record)
        if raw_fragments is None:
            raise ValueError("Neočekávaný formát odpovědi.")
        fragments: list[ESbirkaOpenDataFragmentRef] = []
        seen: set[str] = set()
        skipped_invalid = 0
        for index, raw_value in enumerate(raw_fragments):
            fragment = self._fragment_ref_from_value(
                raw_value,
                wording_eli=wording_eli,
                list_index=index,
            )
            if fragment is None:
                skipped_invalid += 1
                continue
            if fragment.fragment_eli in seen:
                continue
            seen.add(fragment.fragment_eli)
            fragments.append(fragment)
        if not fragments:
            if raw_fragments:
                raise ValueError("Neočekávaný formát odpovědi.")
            raise ValueError("Seznam fragmentů je prázdný.")
        if skipped_invalid:
            logger.warning(
                "Open Data znění %s: přeskočeno %s neplatných IRI fragmentů",
                wording_eli,
                skipped_invalid,
            )
        effective_from = self._parse_iso_date(
            self._coerce_id_text(
                self._find_named_value(record, _EFFECTIVE_FROM_LOCAL_NAME),
            ),
        ) or self._parse_wording_date(wording_eli)
        effective_to = self._parse_iso_date(
            self._coerce_id_text(
                self._find_named_value(record, _EFFECTIVE_TO_LOCAL_NAME),
            ),
        )
        return ESbirkaOpenDataWordingDocument(
            source_eli=wording_eli,
            source_url=source_url,
            effective_from=effective_from,
            effective_to=effective_to,
            wording_type=self._wording_type_code(
                self._find_named_value(record, _WORDING_TYPE_LOCAL_NAME),
            ),
            fragments=tuple(fragments),
        )

    def normalize_fragment_eli(self, value: Any, *, wording_eli: str = "") -> str:
        text = self._coerce_id_text(value)
        if not text:
            return ""
        if not self._is_allowed_fragment_reference(text):
            return ""
        match = _FRAGMENT_ELI_RE.search(text)
        if match is None:
            return ""
        fragment_eli = match.group(1)
        expected = self.normalize_source_eli(wording_eli) if wording_eli else ""
        if expected and not (
            fragment_eli == expected or fragment_eli.startswith(f"{expected}/")
        ):
            return ""
        return fragment_eli

    def build_version_checksum(self, last_wording_eli: str) -> str:
        normalized = self.normalize_wording_eli(last_wording_eli)
        if not normalized:
            raise ValueError("Neočekávaný formát odpovědi.")
        return f"{ESBIRKA_ELI_CHECKSUM_PREFIX}{normalized}"

    def parse_version_checksum(self, checksum: str) -> str | None:
        normalized = (checksum or "").strip()
        if not normalized.startswith(ESBIRKA_ELI_CHECKSUM_PREFIX):
            return None
        payload = normalized[len(ESBIRKA_ELI_CHECKSUM_PREFIX) :].strip()
        return self.normalize_wording_eli(payload) or None

    def is_legacy_checksum(self, checksum: str) -> bool:
        normalized = (checksum or "").strip()
        return normalized.startswith(ESBIRKA_LEGACY_CHECKSUM_PREFIX) and not normalized.startswith(
            ESBIRKA_ELI_CHECKSUM_PREFIX,
        )

    def normalize_wording_eli(self, value: Any) -> str:
        text = self._coerce_id_text(value)
        if not text:
            return ""
        match = _ELI_IN_VALUE_RE.search(text)
        if match is None:
            return ""
        return match.group(1)

    def normalize_source_eli(self, value: Any) -> str:
        return self.normalize_wording_eli(value)

    def effective_from_from_source_eli(self, source_eli: str) -> date | None:
        normalized = self.normalize_source_eli(source_eli)
        if not normalized:
            return None
        return self._parse_wording_date(normalized)

    def _fetch_act_payload(
        self,
        *,
        year: int | str,
        number: str,
    ) -> tuple[Any, str]:
        url = self.build_url(year=year, number=number)
        return self._fetch_jsonld(url, max_bytes=ESBIRKA_OPENDATA_MAX_RESPONSE_BYTES)

    def _fetch_jsonld(
        self,
        url: str,
        *,
        max_bytes: int,
        timeout: float | None = None,
    ) -> tuple[Any, str]:
        try:
            result = safe_https_get(
                url,
                allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
                timeout=float(timeout if timeout is not None else _REQUEST_TIMEOUT),
                max_bytes=max_bytes,
                headers={"Accept": "application/ld+json, application/sparql-results+json, application/json"},
            )
        except SafeHttpsError as exc:
            if exc.kind in {"network", "timeout"}:
                raise ValueError("Internet není dostupný.") from exc
            raise ValueError(str(exc)) from exc

        if result.status_code == 404:
            raise ValueError("Předpis nenalezen.")
        if result.status_code != 200:
            raise ValueError("Internet není dostupný.")

        try:
            payload = json.loads(result.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Neplatné JSON-LD e-Sbírky z %s", result.final_url)
            raise ValueError("Neočekávaný formát odpovědi.") from exc
        if payload is None:
            raise ValueError("Neočekávaný formát odpovědi.")
        return payload, result.final_url

    def _fetch_sparql(self, query: str) -> Any:
        url = (
            f"{ESBIRKA_OPENDATA_SPARQL_URL}?"
            + urlencode(
                {
                    "query": query,
                    "format": "application/sparql-results+json",
                }
            )
        )
        payload, _final_url = self._fetch_jsonld(
            url,
            max_bytes=ESBIRKA_OPENDATA_SPARQL_MAX_RESPONSE_BYTES,
            timeout=_SPARQL_TIMEOUT,
        )
        return payload

    def _sparql_bindings(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        results = payload.get("results")
        if not isinstance(results, dict):
            return []
        bindings = results.get("bindings")
        if not isinstance(bindings, list):
            return []
        return [row for row in bindings if isinstance(row, dict)]

    def _sparql_binding_value(self, row: dict[str, Any], name: str) -> str:
        binding = row.get(name)
        if not isinstance(binding, dict):
            return ""
        return str(binding.get("value") or "").strip()

    def _fragment_type_code(self, value: Any) -> str:
        text = self._coerce_id_text(value)
        if not text:
            return ""
        return text.rstrip("/").rsplit("/", 1)[-1].strip()


    def _fragment_ref_from_value(
        self,
        value: Any,
        *,
        wording_eli: str,
        list_index: int,
    ) -> ESbirkaOpenDataFragmentRef | None:
        fragment_eli = self.normalize_fragment_eli(value, wording_eli=wording_eli)
        if not fragment_eli:
            return None
        document_part, path_segments, section_kind, section_number, parent_path = (
            self._parse_fragment_path(fragment_eli)
        )
        if section_kind == "":
            return None
        return ESbirkaOpenDataFragmentRef(
            fragment_eli=fragment_eli,
            source_url=f"https://{ESBIRKA_OPENDATA_HOST}/esel-esb/{fragment_eli}",
            list_index=list_index,
            document_part=document_part,
            path_segments=path_segments,
            section_kind=section_kind,
            section_number=section_number,
            parent_path=parent_path,
        )

    def _parse_fragment_path(
        self,
        fragment_eli: str,
    ) -> tuple[str, tuple[str, ...], str, str, str]:
        marker = "/dokument"
        position = fragment_eli.find(marker)
        if position < 0:
            return "", (), "dokument", "", ""
        remainder = fragment_eli[position + len(marker) :]
        if remainder == "":
            return "", (), "dokument", "", ""
        if not remainder.startswith("/"):
            return "", (), "", "", ""
        raw_segments = [item for item in remainder.strip("/").split("/") if item]
        parsed: list[tuple[str, str]] = []
        for segment in raw_segments:
            match = _PATH_SEGMENT_RE.fullmatch(segment)
            if match is None:
                return "", (), "", "", ""
            parsed.append((match.group(1).casefold(), match.group(2) or ""))
        if not parsed:
            return "", (), "dokument", "", ""
        document_part = parsed[0][0]
        path_segments = tuple(raw_segments)
        section_kind, section_number = parsed[-1]
        parent_path = "/".join(raw_segments[:-1])
        return document_part, path_segments, section_kind, section_number, parent_path

    def _is_allowed_fragment_reference(self, text: str) -> bool:
        parsed = urlparse(text)
        if parsed.scheme:
            host = (parsed.hostname or "").casefold()
            return parsed.scheme.casefold() == "https" and host == ESBIRKA_OPENDATA_HOST
        if "://" in text:
            return False
        return True

    def _select_wording_record(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and self._is_wording_record(item):
                        return item
            if self._is_wording_record(payload) or "@id" in payload:
                return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and self._is_wording_record(item):
                    return item
        raise ValueError("Neočekávaný formát odpovědi.")

    def _is_wording_record(self, record: dict[str, Any]) -> bool:
        return self._find_fragment_values(record) is not None

    def _find_fragment_values(self, record: dict[str, Any]) -> list[Any] | None:
        value = self._find_named_value(record, _FRAGMENTS_LOCAL_NAME)
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return [value]

    def _find_named_value(self, record: dict[str, Any], local_name: str) -> Any:
        for key, value in record.items():
            if self._jsonld_local_name(str(key)) == local_name:
                return value
        return None

    def _wording_type_code(self, value: Any) -> str:
        text = self._coerce_id_text(value)
        if not text:
            return ""
        local = text.rstrip("/").rsplit("/", 1)[-1]
        return local.strip()

    def _parse_iso_date(self, value: str) -> date | None:
        text = (value or "").strip()
        if not _ISO_DATE_RE.match(text):
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _temporal_wording_from_value(
        self,
        value: Any,
        *,
        source_url: str,
    ) -> ESbirkaOpenDataTemporalWording | None:
        source_eli = self.normalize_wording_eli(value)
        if not source_eli:
            return None
        effective_from = self._parse_wording_date(source_eli)
        if effective_from is None:
            return None
        return ESbirkaOpenDataTemporalWording(
            source_eli=source_eli,
            source_url=source_url,
            effective_from=effective_from,
            version_label=f"e-Sbírka {source_eli}",
        )

    def _select_act_record(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and self._is_act_record(item):
                        return item
            if self._is_act_record(payload) or "@id" in payload:
                return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and self._is_act_record(item):
                    return item
        raise ValueError("Neočekávaný formát odpovědi.")

    def _is_act_record(self, record: dict[str, Any]) -> bool:
        return (
            self._find_last_wording_value(record) is not None
            or bool(self._find_wordings_values(record))
        )

    def _find_last_wording_value(self, record: dict[str, Any]) -> Any:
        for key, value in record.items():
            if self._is_last_wording_key(str(key)):
                return value
        return None

    def _find_wordings_values(self, record: dict[str, Any]) -> list[Any]:
        for key, value in record.items():
            if self._is_wordings_key(str(key)):
                if value is None:
                    return []
                if isinstance(value, list):
                    return value
                return [value]
        return []

    def _is_last_wording_key(self, key: str) -> bool:
        return self._jsonld_local_name(key) == _LAST_WORDING_LOCAL_NAME

    def _is_wordings_key(self, key: str) -> bool:
        return self._jsonld_local_name(key) == _WORDINGS_LOCAL_NAME

    def _jsonld_local_name(self, key: str) -> str:
        local = key.rsplit("/", 1)[-1]
        return local.rsplit(":", 1)[-1]

    def _coerce_id_text(self, value: Any) -> str:
        if isinstance(value, list):
            if not value:
                return ""
            return self._coerce_id_text(value[0])
        if isinstance(value, dict):
            for key in ("@id", "id", "@value"):
                if key in value:
                    return str(value[key]).strip()
            return ""
        if value is None:
            return ""
        return str(value).strip()

    def _parse_wording_date(self, eli: str) -> date | None:
        match = _WORDING_DATE_RE.search(eli)
        if match is None:
            return None
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None


legal_document_esbirka_opendata_client = LegalDocumentESbirkaOpenDataClient()
