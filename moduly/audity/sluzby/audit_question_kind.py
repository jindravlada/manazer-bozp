"""Normalizace a validace ``question_kind`` (AUDIT-METHOD-V2a)."""

from __future__ import annotations

from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_LEGACY,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    AUDIT_QUESTION_KINDS_LIVE_METHODOLOGY,
    AUDIT_QUESTION_KINDS_V2,
    AUDIT_QUESTION_KINDS_V2_SNAPSHOT,
)


class AuditQuestionKindError(ValueError):
    """Neplatný nebo zakázaný druh auditní otázky."""


def interpret_question_kind(raw_value) -> str:
    """
    Interpretace druhu otázky z živé metodiky.

    Chybějící / prázdná hodnota → ``unclassified``.
    """
    if raw_value is None:
        return AUDIT_QUESTION_KIND_UNCLASSIFIED
    text = str(raw_value).strip()
    if not text:
        return AUDIT_QUESTION_KIND_UNCLASSIFIED
    return normalize_question_kind(text)


def normalize_question_kind(value: str) -> str:
    """Normalizuje známý druh; neznámá hodnota vyvolá chybu."""
    kind = str(value or "").strip().casefold()
    aliases = {
        AUDIT_QUESTION_KIND_SYSTEM: AUDIT_QUESTION_KIND_SYSTEM,
        AUDIT_QUESTION_KIND_OPERATION: AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_EXTRAORDINARY: AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_UNCLASSIFIED: AUDIT_QUESTION_KIND_UNCLASSIFIED,
        AUDIT_QUESTION_KIND_LEGACY: AUDIT_QUESTION_KIND_LEGACY,
        # Historické rezervované aliasy (před V2a).
        "provoz": AUDIT_QUESTION_KIND_OPERATION,
        "mimoradne": AUDIT_QUESTION_KIND_EXTRAORDINARY,
    }
    normalized = aliases.get(kind)
    if normalized is None:
        raise AuditQuestionKindError(f"Neplatný question_kind: {value!r}")
    return normalized


def validate_question_kind(
    raw_value,
    *,
    allow_legacy: bool = False,
    allow_missing: bool = True,
) -> str:
    """
    Validuje druh otázky.

    - ``allow_missing``: prázdná hodnota → unclassified (živá metodika).
    - ``allow_legacy``: povolí ``legacy`` (jen historické snapshoty / backfill).
    - Nová metodika (`allow_legacy=False`) ``legacy`` odmítne.
    """
    if raw_value is None or str(raw_value).strip() == "":
        if allow_missing:
            return AUDIT_QUESTION_KIND_UNCLASSIFIED
        raise AuditQuestionKindError("question_kind je povinný.")

    kind = normalize_question_kind(str(raw_value))
    if kind == AUDIT_QUESTION_KIND_LEGACY and not allow_legacy:
        raise AuditQuestionKindError(
            "question_kind „legacy“ není povolen v nové metodice."
        )
    if kind not in AUDIT_QUESTION_KINDS_V2:
        raise AuditQuestionKindError(f"Neplatný question_kind: {raw_value!r}")
    if not allow_legacy and kind not in AUDIT_QUESTION_KINDS_LIVE_METHODOLOGY:
        raise AuditQuestionKindError(f"question_kind „{kind}“ není povolen v metodice.")
    return kind


def is_v2_snapshot_kind(kind: str) -> bool:
    return kind in AUDIT_QUESTION_KINDS_V2_SNAPSHOT


def target_kind_for_workplace(
    *,
    workplace_id: int,
    system_workplace_id: int,
) -> str:
    """Vrátí ``system`` nebo ``operation`` podle cílového provozu auditu."""
    if int(workplace_id) == int(system_workplace_id):
        return AUDIT_QUESTION_KIND_SYSTEM
    return AUDIT_QUESTION_KIND_OPERATION


def format_unclassified_diagnostics(
    items: list[tuple[str, str, str, str, str]],
) -> str:
    """
    ``items``: (process_id, process_name, section_id/section_name, assertion_id, assertion_text)
    """
    lines = [
        "Audit nelze založit: v plánovaných procesech jsou nezařazené otázky "
        f"({AUDIT_QUESTION_KIND_UNCLASSIFIED}):"
    ]
    for process_id, process_name, section_label, assertion_id, assertion_text in items:
        process_label = process_name or process_id
        text_preview = (assertion_text or "").strip()
        if len(text_preview) > 80:
            text_preview = text_preview[:77] + "…"
        lines.append(
            f"- proces „{process_label}“ ({process_id}), "
            f"sekce „{section_label}“, "
            f"otázka „{assertion_id}“"
            + (f": {text_preview}" if text_preview else "")
        )
    return "\n".join(lines)
