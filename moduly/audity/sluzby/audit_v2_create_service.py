"""Atomické založení auditu rovnou jako snapshot v2 (AUDIT-SNAPSHOT-URGENT-2).

Společná cesta pro Program auditů i ruční „Nový audit“.
Nevytváří live audit s dodatečným přepnutím na snapshot.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Collection

from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.constants import (
    AUDIT_METHODOLOGY_GENERATION_V2,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    EXTRAORDINARY_SNAPSHOT_ORDER_BASE,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_commission_member import AuditCommissionMember
from moduly.audity.modely.audit_program import AuditProgramVisit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_knowledge_service import (
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_question_snapshot_service import (
    AuditV2SnapshotError,
    audit_question_snapshot_service,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.audit_snapshot_integrity_service import (
    apply_snapshot_integrity_manifest,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    AUDITABLE_WORKPLACE_REQUIRED_MESSAGE,
    require_auditable_workplace_id,
)
from moduly.audity.sluzby.audit_extraordinary_assignment_service import (
    audit_extraordinary_assignment_service,
)
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    AuditExtraordinaryError,
)
from moduly.audity.sluzby.system_audit_workplace_service import (
    SystemAuditWorkplaceError,
    system_audit_workplace_service,
)


class AuditV2CreateError(ValueError):
    """Chyba atomického založení auditu v2."""


def create_audit_with_v2_snapshot(
    *,
    fields: dict,
    workplace_id: int,
    planned_process_ids: Collection[str] | None = None,
    commission_members: list[dict] | None = None,
    link_visit_id: int | None = None,
    knowledge_tree: list[KnowledgeTreeNode] | None = None,
    ensure_knowledge: bool = True,
) -> Audit:
    """
    Vytvoří audit + filtrovaný snapshot v2 + markery + manifest (+ komise) v jedné TX.

    ``planned_process_ids=None`` = všechny aktivní procesy (ruční audit),
    následně povinný filtr Systém/Provoz podle provozu.
    """
    if workplace_id is None or int(workplace_id) <= 0:
        raise AuditV2CreateError("Auditovaný provoz není zvolen.")

    try:
        require_auditable_workplace_id(int(workplace_id))
    except ValueError as exc:
        raise AuditV2CreateError(str(exc) or AUDITABLE_WORKPLACE_REQUIRED_MESSAGE) from exc

    try:
        system_workplace_id = (
            system_audit_workplace_service.require_system_audit_workplace_id()
        )
    except SystemAuditWorkplaceError:
        raise

    roots = knowledge_tree
    if roots is None:
        roots = audit_knowledge_service.get_knowledge_tree(ensure=ensure_knowledge)

    planned: set[str] | None
    if planned_process_ids is None:
        planned = None
    else:
        planned = {
            str(item).strip() for item in planned_process_ids if str(item or "").strip()
        }

    validated = audit_service._validated_fields(dict(fields))
    validated["workplace_id"] = int(workplace_id)
    if not str(validated.get("workplace_name") or "").strip():
        validated["workplace_name"] = audit_service.resolve_workplace_name(
            int(workplace_id)
        )

    if commission_members is not None:
        # Validace před zápisem — při chybě žádný audit.
        validated_members = audit_commission_service.validate_members(commission_members)
    else:
        validated_members = None

    frozen_at = datetime.now()
    with get_session() as session:
        try:
            if link_visit_id is not None:
                visit_db = session.get(AuditProgramVisit, int(link_visit_id))
                if visit_db is None:
                    raise AuditV2CreateError(
                        f"Návštěva {link_visit_id} neexistuje."
                    )
                if visit_db.audit_id is not None:
                    from moduly.audity.constants import AUDIT_PROGRAM_VISIT_HAS_AUDIT

                    raise AuditV2CreateError(AUDIT_PROGRAM_VISIT_HAS_AUDIT)

            audit = Audit(**validated)
            audit.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            audit.questions_frozen_at = frozen_at
            audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_V2
            audit.created_at = frozen_at
            audit.updated_at = frozen_at
            session.add(audit)
            session.flush()

            audit.number = audit_service._make_number(audit.id, audit.year)

            drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
                audit.id,
                workplace_id=int(workplace_id),
                system_workplace_id=int(system_workplace_id),
                planned_process_ids=planned,
                ensure=False,
                knowledge_tree=roots,
            )
            from moduly.audity.sluzby.audit_extraordinary_assignment_service import (
                audit_extraordinary_assignment_service,
            )

            assignments = (
                audit_extraordinary_assignment_service.require_assignable_for_workplace(
                    session, int(workplace_id)
                )
            )
            order_start = EXTRAORDINARY_SNAPSHOT_ORDER_BASE
            if drafts:
                order_start = max(int(d.display_order) for d in drafts) + 1
                order_start = max(order_start, EXTRAORDINARY_SNAPSHOT_ORDER_BASE)
            extraordinary_drafts = (
                audit_extraordinary_assignment_service.build_snapshot_drafts(
                    assignments,
                    audit_id=int(audit.id),
                    display_order_start=order_start,
                )
            )
            all_drafts = list(drafts) + extraordinary_drafts
            for draft in all_drafts:
                session.add(
                    AuditQuestionSnapshot(
                        audit_id=audit.id,
                        process_id=draft.process_id,
                        process_name=draft.process_name,
                        section_id=draft.section_id,
                        section_name=draft.section_name,
                        assertion_id=draft.assertion_id,
                        assertion_text=draft.assertion_text,
                        verification_type=draft.verification_type,
                        severity=draft.severity,
                        question_kind=draft.question_kind,
                        display_order=draft.display_order,
                        is_in_scope=True,
                        created_at=frozen_at,
                    )
                )

            session.flush()
            written = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            apply_snapshot_integrity_manifest(audit, written)

            if extraordinary_drafts:
                audit_extraordinary_assignment_service.mark_assigned(
                    session,
                    assignments,
                    audit_id=int(audit.id),
                    when=frozen_at,
                )

            if validated_members is not None:
                for member_data in validated_members:
                    session.add(
                        AuditCommissionMember(
                            audit_id=audit.id,
                            record_type=member_data["record_type"],
                            thp_worker_id=member_data.get("thp_worker_id"),
                            person_id=member_data.get("person_id"),
                            display_name=member_data["display_name"],
                            role_text=member_data.get("role_text"),
                            note_text=member_data.get("note_text"),
                            display_order=int(member_data.get("display_order") or 0),
                            active=bool(member_data.get("active", True)),
                        )
                    )

            if link_visit_id is not None:
                visit_db = session.get(AuditProgramVisit, int(link_visit_id))
                assert visit_db is not None
                visit_db.audit_id = audit.id

            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit
        except (AuditV2SnapshotError, SystemAuditWorkplaceError, AuditV2CreateError):
            session.rollback()
            raise
        except AuditExtraordinaryError:
            session.rollback()
            raise
        except ValueError:
            session.rollback()
            raise
        except Exception as exc:
            session.rollback()
            raise AuditV2CreateError(
                f"Nepodařilo se založit audit se snapshotem v2: {exc}"
            ) from exc


def create_manual_audit_with_v2_snapshot(
    *,
    fields: dict,
    commission_members: list[dict] | None = None,
) -> Audit:
    """Ruční audit z přehledu: všechny aktivní procesy + filtr Systém/Provoz."""
    workplace_id = fields.get("workplace_id")
    if workplace_id is None or int(workplace_id) <= 0:
        raise AuditV2CreateError("Auditovaný provoz není zvolen.")
    payload = dict(fields)
    if not payload.get("year"):
        payload["year"] = date.today().year
    if payload.get("started_at") is None and payload.get("audit_date") is None:
        payload["started_at"] = date.today()
    return create_audit_with_v2_snapshot(
        fields=payload,
        workplace_id=int(workplace_id),
        planned_process_ids=None,
        commission_members=commission_members,
        link_visit_id=None,
        ensure_knowledge=True,
    )
