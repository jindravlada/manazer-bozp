"""Založení auditu a zmrazení metodiky v2.

Program i ruční Nový audit se nejdřív ukládají jako planned-unfrozen-v1.
Snapshot vznikne až explicitní přípravou. create_audit_with_v2_snapshot
zůstává pro cesty, které snapshot potřebují hned.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Collection

from sqlalchemy import select

from core.database.session import get_session
from core.shared.section_summary import NOTES_MODE_SECTION_SUMMARY_V1
from moduly.audity.constants import (
    AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
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


def is_planned_unfrozen(audit) -> bool:
    generation = str(getattr(audit, "methodology_generation", "") or "").strip()
    return generation == AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1


def _attach_v2_snapshot(
    session,
    audit: Audit,
    *,
    workplace_id: int,
    system_workplace_id: int,
    planned: set[str] | None,
    roots: list[KnowledgeTreeNode] | None,
    frozen_at: datetime,
) -> None:
    """Stejný zápis snapshotu v2 jako u ručního založení. Nemění started_at ani audit_date."""
    drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
        audit.id,
        workplace_id=int(workplace_id),
        system_workplace_id=int(system_workplace_id),
        planned_process_ids=planned,
        ensure=False,
        knowledge_tree=roots,
    )
    assignments = audit_extraordinary_assignment_service.require_assignable_for_workplace(
        session, int(workplace_id)
    )
    order_start = EXTRAORDINARY_SNAPSHOT_ORDER_BASE
    if drafts:
        order_start = max(int(d.display_order) for d in drafts) + 1
        order_start = max(order_start, EXTRAORDINARY_SNAPSHOT_ORDER_BASE)
    extraordinary_drafts = audit_extraordinary_assignment_service.build_snapshot_drafts(
        assignments,
        audit_id=int(audit.id),
        display_order_start=order_start,
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
            select(AuditQuestionSnapshot).where(AuditQuestionSnapshot.audit_id == audit.id)
        )
    )
    apply_snapshot_integrity_manifest(audit, written)

    from moduly.audity.sluzby.audit_method_support_snapshot_service import (
        audit_method_support_snapshot_service,
    )

    audit_method_support_snapshot_service.build_rows_for_new_audit(
        session,
        audit=audit,
        question_rows=written,
        knowledge_tree=roots,
        when=frozen_at,
    )

    if extraordinary_drafts:
        audit_extraordinary_assignment_service.mark_assigned(
            session,
            assignments,
            audit_id=int(audit.id),
            when=frozen_at,
        )


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
                    from moduly.audity.constants import (
                        AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE,
                    )

                    raise AuditV2CreateError(AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE)

            audit = Audit(**validated)
            audit.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            audit.questions_frozen_at = frozen_at
            audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_V2
            audit.notes_mode = NOTES_MODE_SECTION_SUMMARY_V1
            audit.created_at = frozen_at
            audit.updated_at = frozen_at
            session.add(audit)
            session.flush()

            audit.number = audit_service._make_number(audit.id, audit.year)

            _attach_v2_snapshot(
                session,
                audit,
                workplace_id=int(workplace_id),
                system_workplace_id=int(system_workplace_id),
                planned=planned,
                roots=roots,
                frozen_at=frozen_at,
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
    scope_processes: list[dict] | None = None,
) -> Audit:
    """Ruční audit z přehledu: plán bez snapshotu. Rozsah se ukládá v téže transakci."""
    workplace_id = fields.get("workplace_id")
    if workplace_id is None or int(workplace_id) <= 0:
        raise AuditV2CreateError("Auditovaný provoz není zvolen.")
    payload = dict(fields)
    if not payload.get("year"):
        payload["year"] = date.today().year
    return create_unfrozen_program_audit(
        fields=payload,
        workplace_id=int(workplace_id),
        commission_members=commission_members,
        link_visit_id=None,
        scope_processes=scope_processes,
    )


def create_unfrozen_program_audit(
    *,
    fields: dict,
    workplace_id: int,
    commission_members: list[dict] | None = None,
    link_visit_id: int | None = None,
    scope_processes: list[dict] | None = None,
) -> Audit:
    """Plán z programu: audit, číslo, komise a vazba. Bez snapshotu a bez Mimořádných ověření."""
    if workplace_id is None or int(workplace_id) <= 0:
        raise AuditV2CreateError("Auditovaný provoz není zvolen.")
    try:
        require_auditable_workplace_id(int(workplace_id))
    except ValueError as exc:
        raise AuditV2CreateError(str(exc) or AUDITABLE_WORKPLACE_REQUIRED_MESSAGE) from exc

    validated = audit_service._validated_fields(dict(fields))
    validated["workplace_id"] = int(workplace_id)
    if not str(validated.get("workplace_name") or "").strip():
        validated["workplace_name"] = audit_service.resolve_workplace_name(int(workplace_id))

    validated_members = (
        audit_commission_service.validate_members(commission_members)
        if commission_members is not None
        else None
    )
    now = datetime.now()
    with get_session() as session:
        try:
            if link_visit_id is not None:
                visit_db = session.get(AuditProgramVisit, int(link_visit_id))
                if visit_db is None:
                    raise AuditV2CreateError(f"Návštěva {link_visit_id} neexistuje.")
                if visit_db.audit_id is not None:
                    from moduly.audity.constants import AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE

                    raise AuditV2CreateError(AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE)

            audit = Audit(**validated)
            audit.methodology_source = None
            audit.questions_frozen_at = None
            audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1
            audit.snapshot_question_count = None
            audit.notes_mode = NOTES_MODE_SECTION_SUMMARY_V1
            audit.created_at = now
            audit.updated_at = now
            session.add(audit)
            session.flush()
            audit.number = audit_service._make_number(audit.id, audit.year)

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

            if scope_processes is not None:
                from moduly.audity.sluzby.audit_scope_service import write_scope_processes

                write_scope_processes(session, int(audit.id), scope_processes)

            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit
        except AuditV2CreateError:
            session.rollback()
            raise
        except ValueError:
            session.rollback()
            raise
        except Exception as exc:
            session.rollback()
            raise AuditV2CreateError(f"Nepodařilo se založit plán auditu: {exc}") from exc


def prepare_planned_audit(
    audit_id: int,
    *,
    planned_process_ids: Collection[str] | None,
    knowledge_tree: list[KnowledgeTreeNode] | None = None,
) -> Audit:
    """Zmrazí metodiku existujícího plánu. started_at ani audit_date nemění."""
    try:
        system_workplace_id = system_audit_workplace_service.require_system_audit_workplace_id()
    except SystemAuditWorkplaceError:
        raise

    roots = knowledge_tree
    if roots is None:
        roots = audit_knowledge_service.get_knowledge_tree(ensure=True)

    planned: set[str] | None
    if planned_process_ids is None:
        planned = None
    else:
        planned = {str(item).strip() for item in planned_process_ids if str(item or "").strip()}

    frozen_at = datetime.now()
    with get_session() as session:
        try:
            audit = session.get(Audit, int(audit_id))
            if audit is None:
                raise AuditV2CreateError(f"Audit {audit_id} neexistuje.")
            if not is_planned_unfrozen(audit):
                raise AuditV2CreateError("Audit už je připravený.")
            if audit.questions_frozen_at is not None:
                raise AuditV2CreateError("Audit už je připravený.")
            existing = session.scalar(
                select(AuditQuestionSnapshot.id).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
            if existing is not None:
                raise AuditV2CreateError("Audit už má snapshot.")

            workplace_id = int(audit.workplace_id or 0)
            require_auditable_workplace_id(workplace_id)
            started_at = audit.started_at
            audit_date = audit.audit_date
            audit.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            audit.questions_frozen_at = frozen_at
            audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_V2
            audit.started_at = started_at
            audit.audit_date = audit_date
            audit.updated_at = frozen_at

            _attach_v2_snapshot(
                session,
                audit,
                workplace_id=workplace_id,
                system_workplace_id=int(system_workplace_id),
                planned=planned,
                roots=roots,
                frozen_at=frozen_at,
            )

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
            raise AuditV2CreateError(f"Nepodařilo se připravit audit: {exc}") from exc
