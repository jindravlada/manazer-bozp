from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

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
_REQUEST_TIMEOUT = 30
_LAST_WORDING_LOCAL_NAME = "má-poslední-znění"
_WORDINGS_LOCAL_NAME = "má-znění"
_ELI_IN_VALUE_RE = re.compile(r"(eli/cz/sb/\d{4}/\d+/\d{4}-\d{2}-\d{2})")
_WORDING_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")


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
        try:
            result = safe_https_get(
                url,
                allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
                timeout=_REQUEST_TIMEOUT,
                max_bytes=ESBIRKA_OPENDATA_MAX_RESPONSE_BYTES,
                headers={"Accept": "application/ld+json, application/json"},
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
        return payload, url

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
