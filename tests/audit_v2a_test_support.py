"""Pomocníci pro AUDIT-METHOD-V2a/V2b testy (bez zápisu do ostrých JSON katalogů)."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch

from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    AuditKnowledgeService,
    audit_knowledge_service,
)
from moduly.audity.sluzby.system_audit_workplace_service import (
    system_audit_workplace_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


@contextmanager
def stub_pre_v2_backup():
    """Jednorázovou mbbackup nahraď rychlým stub souborem."""
    from moduly.audity.sluzby.audit_method_v2_backup_service import (
        pre_v2_backup_exists,
    )
    from core.services.storage_service import storage_service

    def fake_ensure(**_kwargs):
        if pre_v2_backup_exists():
            return None
        target = storage_service.backups_dir / "pre_audit_method_v2_stub.mbbackup"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MBBACKUP-STUB")
        return target

    with patch(
        "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
        side_effect=fake_ensure,
    ):
        yield


@contextmanager
def classify_methodology_questions(question_kind: str = AUDIT_QUESTION_KIND_OPERATION):
    """Dočasně doplní question_kind aktivním otázkám (in-memory, bez zápisu JSON)."""
    original = AuditKnowledgeService.get_audit_questions

    def _wrapped(self, section):
        items = original(self, section)
        enriched = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["question_kind"] = question_kind
            enriched.append(row)
        return enriched

    with patch.object(AuditKnowledgeService, "get_audit_questions", _wrapped):
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
    with ExitStack() as stack:
        stack.enter_context(stub_pre_v2_backup())
        system_wp = settings_service.save_workplace(name=system_name, active=True)
        operation_wp = settings_service.save_workplace(name=operation_name, active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(system_wp.id)
        stack.enter_context(classify_methodology_questions(question_kind))
        yield system_wp, operation_wp


def kind_for_visit(*, visit_is_system: bool) -> str:
    return (
        AUDIT_QUESTION_KIND_SYSTEM
        if visit_is_system
        else AUDIT_QUESTION_KIND_OPERATION
    )
