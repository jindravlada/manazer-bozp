from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

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
_ELI_IN_VALUE_RE = re.compile(r"(eli/cz/sb/\d{4}/\d+/\d{4}-\d{2}-\d{2})")
_WORDING_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")


@dataclass(frozen=True)
class ESbirkaOpenDataWording:
    last_wording_eli: str
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

        return self.extract_latest_wording(payload, source_url=url)

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

    def _select_act_record(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and self._find_last_wording_value(item) is not None:
                        return item
            if self._find_last_wording_value(payload) is not None or "@id" in payload:
                return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and self._find_last_wording_value(item) is not None:
                    return item
        raise ValueError("Neočekávaný formát odpovědi.")

    def _find_last_wording_value(self, record: dict[str, Any]) -> Any:
        for key, value in record.items():
            if self._is_last_wording_key(str(key)):
                return value
        return None

    def _is_last_wording_key(self, key: str) -> bool:
        local = key.rsplit("/", 1)[-1]
        local = local.rsplit(":", 1)[-1]
        return local == _LAST_WORDING_LOCAL_NAME

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
