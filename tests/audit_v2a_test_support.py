"""Pomocníci pro AUDIT-METHOD-V2a testy (bez zápisu do ostrých JSON katalogů)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.system_audit_workplace_service import (
    system_audit_workplace_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


@contextmanager
def classify_methodology_questions(question_kind: str = AUDIT_QUESTION_KIND_OPERATION):
    """Dočasně doplní question_kind aktivním otázkám (in-memory, bez zápisu JSON)."""
    original = audit_knowledge_service.get_audit_questions

    def _wrapped(section):
        items = original(section)
        enriched = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["question_kind"] = question_kind
            enriched.append(row)
        return enriched

    with patch.object(
        audit_knowledge_service,
        "get_audit_questions",
        side_effect=_wrapped,
    ):
        yield


@contextmanager
def prepare_v2_audit_create(
    *,
    question_kind: str = AUDIT_QUESTION_KIND_OPERATION,
    system_name: str = "V2a systémový provoz",
    operation_name: str = "V2a provozní provoz",
):
    """
    Připraví systémový provoz + klasifikaci otázek pro úspěšné create_audit_from_visit.

    Yield: (system_workplace, operation_workplace)
    """
    system_wp = settings_service.save_workplace(name=system_name, active=True)
    operation_wp = settings_service.save_workplace(name=operation_name, active=True)
    system_audit_workplace_service.set_system_audit_workplace_id(system_wp.id)
    with classify_methodology_questions(question_kind):
        yield system_wp, operation_wp


def kind_for_visit(*, visit_is_system: bool) -> str:
    return (
        AUDIT_QUESTION_KIND_SYSTEM
        if visit_is_system
        else AUDIT_QUESTION_KIND_OPERATION
    )
