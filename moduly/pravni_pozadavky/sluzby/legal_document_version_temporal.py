from datetime import date

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    legal_document_esbirka_opendata_client,
)

TEMPORAL_STATE_LEGACY = "legacy"
TEMPORAL_STATE_FUTURE = "future"
TEMPORAL_STATE_IN_FORCE = "in_force"

SOURCE_ELI_UNSET = object()


def normalize_stored_source_eli(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = legal_document_esbirka_opendata_client.normalize_source_eli(text)
    if not normalized:
        raise ValueError("Neplatné ELI časového znění.")
    return normalized


def is_identified_temporal_version(version) -> bool:
    source_eli = (getattr(version, "source_eli", None) or "").strip()
    return bool(source_eli) and getattr(version, "effective_from", None) is not None


def classify_temporal_wording(*, effective_from: date | None, on_date: date) -> str:
    if effective_from is None:
        return TEMPORAL_STATE_LEGACY
    if effective_from > on_date:
        return TEMPORAL_STATE_FUTURE
    return TEMPORAL_STATE_IN_FORCE


def select_effective_version(
    versions,
    on_date: date,
    *,
    include_pending: bool = False,
):
    candidates = [
        version
        for version in versions
        if include_pending or not bool(getattr(version, "pending_adoption", False))
    ]
    identified = [
        version
        for version in candidates
        if is_identified_temporal_version(version)
        and not bool(getattr(version, "future_wording", False))
    ]
    applicable = [
        version
        for version in identified
        if version.effective_from is not None and version.effective_from <= on_date
    ]
    if applicable:
        return max(applicable, key=lambda version: (version.effective_from, version.id))

    legacy = [version for version in candidates if not is_identified_temporal_version(version)]
    if not legacy:
        return None
    return max(legacy, key=lambda version: version.id)
