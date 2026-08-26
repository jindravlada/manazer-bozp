"""Společný generátor doporučení vedoucího auditora (UI i export)."""

from __future__ import annotations

import hashlib
import json

from core.shared.constants import ENTITY_AUDITY
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from moduly.audity.constants import (
    AUDIT_LEAD_RECOMMENDATION_STATUS_CURRENT,
    AUDIT_LEAD_RECOMMENDATION_STATUS_STALE,
    AUDIT_LEAD_RECOMMENDATION_STATUS_UNCONFIRMED,
)
from moduly.audity.modely.audit import Audit

STATUS_CURRENT = "current"
STATUS_STALE = "stale"
STATUS_UNCONFIRMED = "unconfirmed"

STATUS_LABELS = {
    STATUS_CURRENT: AUDIT_LEAD_RECOMMENDATION_STATUS_CURRENT,
    STATUS_STALE: AUDIT_LEAD_RECOMMENDATION_STATUS_STALE,
    STATUS_UNCONFIRMED: AUDIT_LEAD_RECOMMENDATION_STATUS_UNCONFIRMED,
}


def is_recommendation_blank(value) -> bool:
    if value is None:
        return True
    return not str(value).strip()


def normalize_recommendation_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return None
    return text


def _result_rows(audit_id: int) -> list[tuple[str, str, str, str]]:
    rows = control_result_service.get_for_entity(ENTITY_AUDITY, int(audit_id))
    payload = [
        (
            str(row.source_area_label or "").strip(),
            str(row.source_section_label or "").strip(),
            str(row.source_control_point_id or "").strip(),
            str(row.result or "").strip(),
        )
        for row in rows
    ]
    payload.sort()
    return payload


def compute_results_signature(audit_id: int) -> str:
    """Deterministický podpis vstupů automatického doporučení."""
    from moduly.audity.sluzby.audit_service import audit_service

    summary = audit_service.get_conclusion_summary(int(audit_id))
    payload = {
        "findings_open": int(summary["findings_open"]),
        "results": _result_rows(audit_id),
        "tasks_active": int(summary["tasks_active"]),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def generate_lead_auditor_recommendation(audit_id: int) -> str:
    """Automatický návrh podle aktuálních výsledků — BOZP i QMS ve všech větvích."""
    from moduly.audity.sluzby.audit_service import audit_service

    stats = control_activity_statistics_service.compute(ENTITY_AUDITY, int(audit_id))
    summary = audit_service.get_conclusion_summary(int(audit_id))
    sentences: list[str] = []

    if stats.ratings_nevyhovuje:
        sentences.append(
            f"Audit identifikoval {stats.ratings_nevyhovuje} neshod "
            "v systémech managementu BOZP a QMS vyžadujících bezodkladné řešení."
        )
    if stats.ratings_vyhovuje_s_doporucenim:
        sentences.append(
            f"V {stats.ratings_vyhovuje_s_doporucenim} oblastech systémů "
            "managementu BOZP a QMS byla doporučena preventivní zlepšení."
        )
    if not sentences:
        sentences.append(
            "Audit potvrdil účinnost systémů managementu BOZP a QMS "
            "bez závažných nedostatků."
        )
    if summary["findings_open"] > 0 or summary["tasks_active"] > 0:
        sentences.append(
            "Organizaci doporučujeme v systémech managementu BOZP a QMS "
            "prioritně dokončit "
            f"{summary['findings_open']} otevřených zjištění "
            f"a {summary['tasks_active']} aktivních úkolů."
        )
    else:
        sentences.append(
            "Doporučujeme průběžně sledovat plnění přijatých opatření "
            "v systémech managementu BOZP a QMS a udržovat zavedené kontroly."
        )
    return " ".join(sentences[:4])


def confirmed_recommendation_fields(
    audit_id: int,
    text: str | None = None,
) -> dict[str, str]:
    """Text + aktuální podpis pro vědomé potvrzení (uložení / dokončení)."""
    rec = text if text is not None else generate_lead_auditor_recommendation(audit_id)
    return {
        "lead_auditor_recommendation": rec,
        "lead_auditor_recommendation_results_signature": compute_results_signature(
            int(audit_id)
        ),
    }


def resolve_lead_auditor_recommendation_text(audit: Audit) -> str:
    """Uložený text, jinak automatický fallback. Bez zápisu do DB."""
    saved = getattr(audit, "lead_auditor_recommendation", None)
    if not is_recommendation_blank(saved):
        return normalize_recommendation_text(saved) or ""
    audit_id = getattr(audit, "id", None)
    if not audit_id:
        return ""
    return generate_lead_auditor_recommendation(int(audit_id))


def recommendation_status(
    audit: Audit,
    *,
    current_signature: str | None = None,
) -> str:
    saved = getattr(audit, "lead_auditor_recommendation", None)
    if is_recommendation_blank(saved):
        return STATUS_UNCONFIRMED
    saved_sig = str(
        getattr(audit, "lead_auditor_recommendation_results_signature", None) or ""
    ).strip()
    audit_id = getattr(audit, "id", None)
    if not saved_sig or not audit_id:
        return STATUS_UNCONFIRMED
    actual = current_signature or compute_results_signature(int(audit_id))
    if saved_sig == actual:
        return STATUS_CURRENT
    return STATUS_STALE


def recommendation_status_label(
    audit: Audit,
    *,
    current_signature: str | None = None,
) -> str:
    return STATUS_LABELS[recommendation_status(audit, current_signature=current_signature)]
