"""Business služby Externích auditů (EA-0/EA-1)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database.session import get_session
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    require_auditable_workplace_id,
)
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_ACTIONABLE_STATUSES,
    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
    EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
    EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
    EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
    EXTERNAL_AUDIT_FINDING_TYPES,
    EXTERNAL_AUDIT_PARTICIPANT_ROLES,
    EXTERNAL_AUDIT_ROLE_SOURCE_TYPES,
    EXTERNAL_AUDIT_SOURCE_PERSON,
    EXTERNAL_AUDIT_SOURCE_THP_WORKER,
    EXTERNAL_AUDIT_STATUS_LABELS,
    EXTERNAL_AUDIT_STATUSES,
    EXTERNAL_AUDIT_STATUS_CANCELLED,
    EXTERNAL_AUDIT_STATUS_CLOSED,
    EXTERNAL_AUDIT_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_STATUS_PLANNED,
    EXTERNAL_AUDIT_TYPE_LABELS,
    EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    EXTERNAL_AUDIT_TYPES,
)
from moduly.externi_audity.modely import (
    ExternalAudit,
    ExternalAuditFinding,
    ExternalAuditFindingTaskLink,
    ExternalAuditParticipant,
    ExternalAuditVisit,
    ExternalAuditVisitParticipant,
)
from moduly.externi_audity.sluzby.external_audit_draft import (
    AttachmentStagingState,
    ExternalAuditDraft,
    ParticipantDraft,
    VisitDraft,
    new_client_key,
)
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.sluzby.task_service import task_service

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class ExternalAuditError(ValueError):
    """Validační / business chyba externího auditu."""


@dataclass(frozen=True)
class ExternalAuditListItem:
    audit: ExternalAudit
    visit_count: int
    date_from: date | None
    date_to: date | None
    open_finding_count: int
    finding_count: int


@dataclass
class ExternalAuditDetail:
    audit: ExternalAudit
    visits: list[ExternalAuditVisit] = field(default_factory=list)
    participants: list[ExternalAuditParticipant] = field(default_factory=list)
    visit_participant_ids: dict[int, list[int]] = field(default_factory=dict)
    findings: list[ExternalAuditFinding] = field(default_factory=list)
    finding_task_ids: dict[int, list[int]] = field(default_factory=dict)
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class ExternalAuditOverviewRow:
    audit_id: int
    date_from: date | None
    date_to: date | None
    audit_type: str
    audit_type_label: str
    organization_name: str
    organization_ico: str
    workplaces_label: str
    status: str
    status_label: str
    remind_from: date | None


def _parse_time(value: str | None) -> time | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = _TIME_RE.match(raw)
    if not match:
        raise ExternalAuditError(f"Neplatný čas „{raw}“. Použijte formát HH:MM.")
    return time(int(match.group(1)), int(match.group(2)))


def _normalize_time(value: str | None) -> str | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def _validate_time_range(time_from: str | None, time_to: str | None) -> tuple[str | None, str | None]:
    normalized_from = _normalize_time(time_from)
    normalized_to = _normalize_time(time_to)
    if normalized_from and normalized_to:
        if _parse_time(normalized_to) < _parse_time(normalized_from):
            raise ExternalAuditError("Čas do nesmí být dříve než čas od.")
    return normalized_from, normalized_to


def _require_audit_type(audit_type: str) -> str:
    value = str(audit_type or "").strip()
    if value not in EXTERNAL_AUDIT_TYPES:
        raise ExternalAuditError(f"Neplatný typ externího auditu: {audit_type!r}")
    return value


def _require_audit_status(status: str) -> str:
    value = str(status or "").strip()
    if value not in EXTERNAL_AUDIT_STATUSES:
        raise ExternalAuditError(f"Neplatný stav externího auditu: {status!r}")
    return value


def _require_finding_type(finding_type: str) -> str:
    value = str(finding_type or "").strip()
    if value not in EXTERNAL_AUDIT_FINDING_TYPES:
        raise ExternalAuditError(f"Neplatný typ zjištění: {finding_type!r}")
    return value


def _default_finding_status(finding_type: str) -> str:
    if finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
        return EXTERNAL_AUDIT_FINDING_STATUS_RECORDED
    return EXTERNAL_AUDIT_FINDING_STATUS_OPEN


def _require_actionable_finding_status(status: str) -> str:
    value = str(status or "").strip()
    if value not in EXTERNAL_AUDIT_FINDING_ACTIONABLE_STATUSES:
        raise ExternalAuditError(f"Neplatný stav zjištění: {status!r}")
    return value


def _touch(audit: ExternalAudit) -> None:
    audit.updated_at = datetime.now()


def _organization_snapshot_payload(
    *,
    ico: str,
    name: str,
    address: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "ico": ico,
        "name": name,
        "address": address,
        "extra": extra or {},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _resolve_participant_source(
    *,
    role: str,
    source_type: str,
    source_id: int,
) -> tuple[str, int, str]:
    role_value = str(role or "").strip()
    if role_value not in EXTERNAL_AUDIT_PARTICIPANT_ROLES:
        raise ExternalAuditError(f"Neplatná role účastníka: {role!r}")
    expected_source = EXTERNAL_AUDIT_ROLE_SOURCE_TYPES[role_value]
    source_value = str(source_type or "").strip()
    if source_value != expected_source:
        raise ExternalAuditError(
            f"Role {role_value} vyžaduje zdroj {expected_source}, "
            f"dostáno {source_value!r}."
        )
    sid = int(source_id)
    if sid <= 0:
        raise ExternalAuditError("Neplatné source_id účastníka.")

    if source_value == EXTERNAL_AUDIT_SOURCE_PERSON:
        person = person_service.get_by_id(sid)
        if person is None:
            raise ExternalAuditError(f"Osoba id={sid} neexistuje.")
        display = str(getattr(person, "display_name", None) or person.full_name or "").strip()
        if not display:
            display = f"Osoba #{sid}"
        return source_value, sid, display

    if source_value == EXTERNAL_AUDIT_SOURCE_THP_WORKER:
        worker = settings_service.get_worker_by_id(sid)
        if worker is None:
            raise ExternalAuditError(f"THP pracovník id={sid} neexistuje.")
        display = str(getattr(worker, "display_name", None) or worker.full_name or "").strip()
        if not display:
            display = f"THP #{sid}"
        return source_value, sid, display

    raise ExternalAuditError(f"Neplatný source_type: {source_type!r}")


class ExternalAuditService:
    def create_audit(
        self,
        *,
        audit_type: str,
        organization_ico: str,
        organization_name: str,
        organization_address: str = "",
        organization_extra: dict[str, Any] | None = None,
        status: str = EXTERNAL_AUDIT_STATUS_PLANNED,
        remind_from: date | None = None,
        note: str | None = None,
    ) -> ExternalAudit:
        audit_type_value = _require_audit_type(audit_type)
        status_value = _require_audit_status(status)
        ico = str(organization_ico or "").strip()
        name = str(organization_name or "").strip()
        address = str(organization_address or "").strip()
        if not ico:
            raise ExternalAuditError("IČ organizace je povinné.")
        if not name:
            raise ExternalAuditError("Název organizace je povinný.")

        with get_session() as session:
            audit = ExternalAudit(
                audit_type=audit_type_value,
                status=status_value,
                remind_from=remind_from,
                organization_ico=ico,
                organization_name=name,
                organization_address=address,
                organization_snapshot_json=_organization_snapshot_payload(
                    ico=ico,
                    name=name,
                    address=address,
                    extra=organization_extra,
                ),
                note=(str(note).strip() if note else None) or None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(audit)
            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit

    def update_audit(
        self,
        audit_id: int,
        *,
        audit_type: str | None = None,
        remind_from: date | None | object = ...,
        note: str | None | object = ...,
        organization_ico: str | None = None,
        organization_name: str | None = None,
        organization_address: str | None = None,
        organization_extra: dict[str, Any] | None = None,
    ) -> ExternalAudit:
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            if audit_type is not None:
                audit.audit_type = _require_audit_type(audit_type)
            if remind_from is not ...:
                audit.remind_from = remind_from  # type: ignore[assignment]
            if note is not ...:
                audit.note = (str(note).strip() if note else None) or None
            org_changed = any(
                value is not None
                for value in (
                    organization_ico,
                    organization_name,
                    organization_address,
                    organization_extra,
                )
            )
            if org_changed:
                ico = str(
                    organization_ico
                    if organization_ico is not None
                    else audit.organization_ico
                ).strip()
                name = str(
                    organization_name
                    if organization_name is not None
                    else audit.organization_name
                ).strip()
                address = str(
                    organization_address
                    if organization_address is not None
                    else audit.organization_address
                ).strip()
                if not ico or not name:
                    raise ExternalAuditError("IČ a název organizace jsou povinné.")
                audit.organization_ico = ico
                audit.organization_name = name
                audit.organization_address = address
                audit.organization_snapshot_json = _organization_snapshot_payload(
                    ico=ico,
                    name=name,
                    address=address,
                    extra=organization_extra,
                )
            _touch(audit)
            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit

    def set_status(self, audit_id: int, status: str) -> ExternalAudit:
        status_value = _require_audit_status(status)
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            audit.status = status_value
            _touch(audit)
            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit

    def add_visit(
        self,
        audit_id: int,
        *,
        visit_date: date,
        workplace_id: int,
        time_from: str | None = None,
        time_to: str | None = None,
        note: str | None = None,
        display_order: int | None = None,
    ) -> ExternalAuditVisit:
        workplace = self._require_workplace(workplace_id)
        tf, tt = _validate_time_range(time_from, time_to)
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            order = display_order
            if order is None:
                current_max = session.scalar(
                    select(func.max(ExternalAuditVisit.display_order)).where(
                        ExternalAuditVisit.external_audit_id == audit.id
                    )
                )
                order = int(current_max or 0) + 10
            visit = ExternalAuditVisit(
                external_audit_id=audit.id,
                visit_date=visit_date,
                time_from=tf,
                time_to=tt,
                workplace_id=int(workplace.id),
                workplace_name_snapshot=str(workplace.name or "").strip(),
                workplace_address_snapshot=str(workplace.address or "").strip(),
                display_order=int(order),
                note=(str(note).strip() if note else None) or None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(visit)
            _touch(audit)
            session.commit()
            session.refresh(visit)
            session.expunge(visit)
            return visit

    def update_visit(
        self,
        visit_id: int,
        *,
        visit_date: date | None = None,
        workplace_id: int | None = None,
        time_from: str | None | object = ...,
        time_to: str | None | object = ...,
        note: str | None | object = ...,
        display_order: int | None = None,
    ) -> ExternalAuditVisit:
        with get_session() as session:
            visit = self._get_visit(session, visit_id)
            audit = self._get_audit(session, visit.external_audit_id)
            if visit_date is not None:
                visit.visit_date = visit_date
            if workplace_id is not None:
                workplace = self._require_workplace(workplace_id)
                visit.workplace_id = int(workplace.id)
                visit.workplace_name_snapshot = str(workplace.name or "").strip()
                visit.workplace_address_snapshot = str(workplace.address or "").strip()
            if time_from is not ... or time_to is not ...:
                tf = visit.time_from if time_from is ... else time_from  # type: ignore[assignment]
                tt = visit.time_to if time_to is ... else time_to  # type: ignore[assignment]
                visit.time_from, visit.time_to = _validate_time_range(tf, tt)
            if note is not ...:
                visit.note = (str(note).strip() if note else None) or None
            if display_order is not None:
                visit.display_order = int(display_order)
            visit.updated_at = datetime.now()
            _touch(audit)
            session.commit()
            session.refresh(visit)
            session.expunge(visit)
            return visit

    def remove_visit(self, visit_id: int) -> None:
        """Technické odebrání návštěvy z rozpracovaného spisu (ne mazání auditu)."""
        with get_session() as session:
            visit = self._get_visit(session, visit_id)
            audit = self._get_audit(session, visit.external_audit_id)
            links = list(
                session.scalars(
                    select(ExternalAuditVisitParticipant).where(
                        ExternalAuditVisitParticipant.visit_id == visit.id
                    )
                )
            )
            for link in links:
                session.delete(link)
            session.delete(visit)
            _touch(audit)
            session.commit()

    def add_participant(
        self,
        audit_id: int,
        *,
        role: str,
        source_type: str,
        source_id: int,
        display_order: int | None = None,
    ) -> ExternalAuditParticipant:
        source_type_value, source_id_value, display = _resolve_participant_source(
            role=role,
            source_type=source_type,
            source_id=source_id,
        )
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            order = display_order
            if order is None:
                current_max = session.scalar(
                    select(func.max(ExternalAuditParticipant.display_order)).where(
                        ExternalAuditParticipant.external_audit_id == audit.id
                    )
                )
                order = int(current_max or 0) + 10
            participant = ExternalAuditParticipant(
                external_audit_id=audit.id,
                role=str(role).strip(),
                source_type=source_type_value,
                source_id=source_id_value,
                display_name_snapshot=display,
                display_order=int(order),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(participant)
            _touch(audit)
            session.commit()
            session.refresh(participant)
            session.expunge(participant)
            return participant

    def remove_participant(self, participant_id: int) -> None:
        with get_session() as session:
            participant = self._get_participant(session, participant_id)
            audit = self._get_audit(session, participant.external_audit_id)
            links = list(
                session.scalars(
                    select(ExternalAuditVisitParticipant).where(
                        ExternalAuditVisitParticipant.participant_id == participant.id
                    )
                )
            )
            for link in links:
                session.delete(link)
            session.delete(participant)
            _touch(audit)
            session.commit()

    def set_visit_participants(
        self, visit_id: int, participant_ids: Sequence[int]
    ) -> list[int]:
        unique_ids = [int(value) for value in participant_ids]
        if len(unique_ids) != len(set(unique_ids)):
            raise ExternalAuditError("Duplicitní účastník u návštěvy.")
        with get_session() as session:
            visit = self._get_visit(session, visit_id)
            audit = self._get_audit(session, visit.external_audit_id)
            if unique_ids:
                participants = list(
                    session.scalars(
                        select(ExternalAuditParticipant).where(
                            ExternalAuditParticipant.id.in_(unique_ids)
                        )
                    )
                )
                by_id = {int(item.id): item for item in participants}
                if len(by_id) != len(unique_ids):
                    raise ExternalAuditError("Neexistující účastník auditu.")
                for pid in unique_ids:
                    if int(by_id[pid].external_audit_id) != int(audit.id):
                        raise ExternalAuditError(
                            "Účastník návštěvy musí patřit stejnému externímu auditu."
                        )
            existing = list(
                session.scalars(
                    select(ExternalAuditVisitParticipant).where(
                        ExternalAuditVisitParticipant.visit_id == visit.id
                    )
                )
            )
            for link in existing:
                session.delete(link)
            session.flush()
            for pid in unique_ids:
                session.add(
                    ExternalAuditVisitParticipant(
                        visit_id=visit.id,
                        participant_id=pid,
                        created_at=datetime.now(),
                    )
                )
            _touch(audit)
            session.commit()
            return list(unique_ids)

    def add_finding(
        self,
        audit_id: int,
        *,
        finding_type: str,
        description: str,
        status: str | None = None,
        due_date: date | None = None,
        display_order: int | None = None,
    ) -> ExternalAuditFinding:
        finding_type_value = _require_finding_type(finding_type)
        text = str(description or "").strip()
        if not text:
            raise ExternalAuditError("Popis zjištění je povinný.")
        if finding_type_value == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
            status_value = EXTERNAL_AUDIT_FINDING_STATUS_RECORDED
            due_date = None
        else:
            status_value = _require_actionable_finding_status(
                status or EXTERNAL_AUDIT_FINDING_STATUS_OPEN
            )
            if status_value == EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED:
                raise ExternalAuditError(
                    "Nové zjištění nelze založit rovnou jako Vypořádáno. "
                    "Použijte resolve_finding."
                )
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            order = display_order
            if order is None:
                current_max = session.scalar(
                    select(func.max(ExternalAuditFinding.display_order)).where(
                        ExternalAuditFinding.external_audit_id == audit.id
                    )
                )
                order = int(current_max or 0) + 10
            finding = ExternalAuditFinding(
                external_audit_id=audit.id,
                finding_type=finding_type_value,
                description=text,
                status=status_value,
                due_date=due_date,
                display_order=int(order),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(finding)
            _touch(audit)
            session.commit()
            session.refresh(finding)
            session.expunge(finding)
            return finding

    def update_finding(
        self,
        finding_id: int,
        *,
        description: str | None = None,
        status: str | None = None,
        due_date: date | None | object = ...,
        display_order: int | None = None,
    ) -> ExternalAuditFinding:
        with get_session() as session:
            finding = self._get_finding(session, finding_id)
            audit = self._get_audit(session, finding.external_audit_id)
            if finding.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
                if status is not None and status != EXTERNAL_AUDIT_FINDING_STATUS_RECORDED:
                    raise ExternalAuditError(
                        "Silná stránka nemá stavy otevřené neshody."
                    )
                if due_date is not ... and due_date is not None:
                    raise ExternalAuditError("Silná stránka nemá termín vypořádání.")
            else:
                if status is not None:
                    new_status = _require_actionable_finding_status(status)
                    if new_status == EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED:
                        raise ExternalAuditError(
                            "Pro vypořádání použijte resolve_finding s textem."
                        )
                    if (
                        finding.status == EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED
                        and new_status
                        in (
                            EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                            EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
                        )
                    ):
                        finding.resolved_at = None
                    finding.status = new_status
            if description is not None:
                text = str(description).strip()
                if not text:
                    raise ExternalAuditError("Popis zjištění je povinný.")
                finding.description = text
            if due_date is not ...:
                finding.due_date = due_date  # type: ignore[assignment]
            if display_order is not None:
                finding.display_order = int(display_order)
            finding.updated_at = datetime.now()
            _touch(audit)
            session.commit()
            session.refresh(finding)
            session.expunge(finding)
            return finding

    def resolve_finding(
        self, finding_id: int, *, resolution_text: str
    ) -> ExternalAuditFinding:
        text = str(resolution_text or "").strip()
        if not text:
            raise ExternalAuditError("Text vypořádání je povinný.")
        with get_session() as session:
            finding = self._get_finding(session, finding_id)
            if finding.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
                raise ExternalAuditError("Silná stránka se nevypořádává.")
            audit = self._get_audit(session, finding.external_audit_id)
            finding.status = EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED
            finding.resolution_text = text
            finding.resolved_at = datetime.now()
            finding.updated_at = datetime.now()
            _touch(audit)
            session.commit()
            session.refresh(finding)
            session.expunge(finding)
            return finding

    def reopen_finding(
        self,
        finding_id: int,
        *,
        status: str = EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    ) -> ExternalAuditFinding:
        status_value = _require_actionable_finding_status(status)
        if status_value == EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED:
            raise ExternalAuditError("Nelze znovuotevřít do stavu Vypořádáno.")
        with get_session() as session:
            finding = self._get_finding(session, finding_id)
            if finding.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
                raise ExternalAuditError("Silná stránka se znovu neotevírá.")
            audit = self._get_audit(session, finding.external_audit_id)
            finding.status = status_value
            finding.resolved_at = None
            finding.updated_at = datetime.now()
            _touch(audit)
            session.commit()
            session.refresh(finding)
            session.expunge(finding)
            return finding

    def link_task(self, finding_id: int, task_id: int) -> ExternalAuditFindingTaskLink:
        task = task_service.get_task_by_id(int(task_id))
        if task is None:
            raise ExternalAuditError(f"Úkol id={task_id} neexistuje.")
        with get_session() as session:
            finding = self._get_finding(session, finding_id)
            if finding.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
                raise ExternalAuditError(
                    "Silná stránka nesmí zakládat návazný úkol."
                )
            if finding.finding_type not in {
                EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            }:
                raise ExternalAuditError("Úkol lze vázat jen na Neshodu nebo PKZ.")
            existing = session.scalar(
                select(ExternalAuditFindingTaskLink).where(
                    ExternalAuditFindingTaskLink.finding_id == finding.id,
                    ExternalAuditFindingTaskLink.task_id == int(task_id),
                )
            )
            if existing is not None:
                raise ExternalAuditError("Úkol je k zjištění již připojen.")
            link = ExternalAuditFindingTaskLink(
                finding_id=finding.id,
                task_id=int(task_id),
                created_at=datetime.now(),
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            session.expunge(link)
            return link

    def list_finding_task_ids(self, finding_id: int) -> list[int]:
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(ExternalAuditFindingTaskLink.task_id)
                    .where(ExternalAuditFindingTaskLink.finding_id == int(finding_id))
                    .order_by(ExternalAuditFindingTaskLink.id)
                )
            )
            return [int(value) for value in rows]

    def derived_date_range(
        self, audit_id: int
    ) -> tuple[date | None, date | None]:
        with get_session() as session:
            return self._derived_date_range(session, int(audit_id))

    def get_detail(self, audit_id: int) -> ExternalAuditDetail:
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            visits = list(
                session.scalars(
                    select(ExternalAuditVisit)
                    .where(ExternalAuditVisit.external_audit_id == audit.id)
                    .order_by(
                        ExternalAuditVisit.visit_date,
                        ExternalAuditVisit.display_order,
                        ExternalAuditVisit.id,
                    )
                )
            )
            participants = list(
                session.scalars(
                    select(ExternalAuditParticipant)
                    .where(ExternalAuditParticipant.external_audit_id == audit.id)
                    .order_by(
                        ExternalAuditParticipant.display_order,
                        ExternalAuditParticipant.id,
                    )
                )
            )
            findings = list(
                session.scalars(
                    select(ExternalAuditFinding)
                    .where(ExternalAuditFinding.external_audit_id == audit.id)
                    .order_by(
                        ExternalAuditFinding.display_order,
                        ExternalAuditFinding.id,
                    )
                )
            )
            visit_ids = [int(visit.id) for visit in visits]
            finding_ids = [int(finding.id) for finding in findings]

            visit_participant_ids: dict[int, list[int]] = {
                vid: [] for vid in visit_ids
            }
            if visit_ids:
                for link in session.scalars(
                    select(ExternalAuditVisitParticipant).where(
                        ExternalAuditVisitParticipant.visit_id.in_(visit_ids)
                    )
                ):
                    visit_participant_ids.setdefault(int(link.visit_id), []).append(
                        int(link.participant_id)
                    )

            finding_task_ids: dict[int, list[int]] = {
                fid: [] for fid in finding_ids
            }
            if finding_ids:
                for link in session.scalars(
                    select(ExternalAuditFindingTaskLink)
                    .where(ExternalAuditFindingTaskLink.finding_id.in_(finding_ids))
                    .order_by(ExternalAuditFindingTaskLink.id)
                ):
                    finding_task_ids.setdefault(int(link.finding_id), []).append(
                        int(link.task_id)
                    )

            date_from, date_to = self._derived_date_range(session, int(audit.id))

            for item in [audit, *visits, *participants, *findings]:
                session.expunge(item)
            return ExternalAuditDetail(
                audit=audit,
                visits=visits,
                participants=participants,
                visit_participant_ids=visit_participant_ids,
                findings=findings,
                finding_task_ids=finding_task_ids,
                date_from=date_from,
                date_to=date_to,
            )

    def list_audits(self) -> list[ExternalAuditListItem]:
        with get_session() as session:
            audits = list(
                session.scalars(
                    select(ExternalAudit).order_by(
                        ExternalAudit.id.desc()
                    )
                )
            )
            if not audits:
                return []
            audit_ids = [int(audit.id) for audit in audits]

            visit_rows = session.execute(
                select(
                    ExternalAuditVisit.external_audit_id,
                    func.count(ExternalAuditVisit.id),
                    func.min(ExternalAuditVisit.visit_date),
                    func.max(ExternalAuditVisit.visit_date),
                )
                .where(ExternalAuditVisit.external_audit_id.in_(audit_ids))
                .group_by(ExternalAuditVisit.external_audit_id)
            ).all()
            visit_map = {
                int(audit_id): (int(count), min_date, max_date)
                for audit_id, count, min_date, max_date in visit_rows
            }

            findings = list(
                session.scalars(
                    select(ExternalAuditFinding).where(
                        ExternalAuditFinding.external_audit_id.in_(audit_ids)
                    )
                )
            )
            totals: dict[int, int] = {}
            opens: dict[int, int] = {}
            for finding in findings:
                aid = int(finding.external_audit_id)
                totals[aid] = totals.get(aid, 0) + 1
                if finding.status in {
                    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
                }:
                    opens[aid] = opens.get(aid, 0) + 1
            finding_map = {
                aid: (totals.get(aid, 0), opens.get(aid, 0)) for aid in audit_ids
            }

            result: list[ExternalAuditListItem] = []
            for audit in audits:
                session.expunge(audit)
                visit_count, date_from, date_to = visit_map.get(
                    int(audit.id), (0, None, None)
                )
                finding_count, open_count = finding_map.get(int(audit.id), (0, 0))
                result.append(
                    ExternalAuditListItem(
                        audit=audit,
                        visit_count=visit_count,
                        date_from=date_from,
                        date_to=date_to,
                        open_finding_count=open_count,
                        finding_count=finding_count,
                    )
                )
            return result

    def get_by_id(self, audit_id: int) -> ExternalAudit:
        with get_session() as session:
            audit = self._get_audit(session, audit_id)
            session.expunge(audit)
            return audit

    def list_attachments(self, audit_id: int):
        """Čtecí napojení na obecný attachment mechanismus (bez zápisu souborů)."""
        from core.services.attachment_service import attachment_service
        from moduly.externi_audity.constants import ENTITY_EXTERNAL_AUDIT

        self.get_by_id(audit_id)
        return attachment_service.get_for_entity(ENTITY_EXTERNAL_AUDIT, int(audit_id))

    def list_overview_rows(self) -> list[ExternalAuditOverviewRow]:
        """Batch přehled bez N+1 (audity + termíny + snapshoty provozů)."""
        with get_session() as session:
            audits = list(
                session.scalars(select(ExternalAudit).order_by(ExternalAudit.id.desc()))
            )
            if not audits:
                return []
            audit_ids = [int(audit.id) for audit in audits]
            visit_rows = list(
                session.scalars(
                    select(ExternalAuditVisit)
                    .where(ExternalAuditVisit.external_audit_id.in_(audit_ids))
                    .order_by(
                        ExternalAuditVisit.visit_date,
                        ExternalAuditVisit.display_order,
                        ExternalAuditVisit.id,
                    )
                )
            )
            range_map: dict[int, tuple[date | None, date | None]] = {}
            workplace_map: dict[int, list[str]] = {aid: [] for aid in audit_ids}
            seen_names: dict[int, set[str]] = {aid: set() for aid in audit_ids}
            for visit in visit_rows:
                aid = int(visit.external_audit_id)
                current = range_map.get(aid)
                if current is None:
                    range_map[aid] = (visit.visit_date, visit.visit_date)
                else:
                    range_map[aid] = (
                        min(current[0], visit.visit_date),
                        max(current[1], visit.visit_date),
                    )
                name = str(visit.workplace_name_snapshot or "").strip()
                if name and name not in seen_names[aid]:
                    seen_names[aid].add(name)
                    workplace_map[aid].append(name)

            rows: list[ExternalAuditOverviewRow] = []
            for audit in audits:
                date_from, date_to = range_map.get(int(audit.id), (None, None))
                rows.append(
                    ExternalAuditOverviewRow(
                        audit_id=int(audit.id),
                        date_from=date_from,
                        date_to=date_to,
                        audit_type=str(audit.audit_type),
                        audit_type_label=EXTERNAL_AUDIT_TYPE_LABELS.get(
                            audit.audit_type, audit.audit_type
                        ),
                        organization_name=str(audit.organization_name or ""),
                        organization_ico=str(audit.organization_ico or ""),
                        workplaces_label=", ".join(workplace_map.get(int(audit.id), [])),
                        status=str(audit.status),
                        status_label=EXTERNAL_AUDIT_STATUS_LABELS.get(
                            audit.status, audit.status
                        ),
                        remind_from=audit.remind_from,
                    )
                )

            dated = [row for row in rows if row.date_from is not None]
            undated = [row for row in rows if row.date_from is None]
            dated.sort(key=lambda row: (row.date_from, row.audit_id), reverse=True)
            undated.sort(key=lambda row: row.audit_id, reverse=True)
            return dated + undated

    def load_draft(self, audit_id: int | None = None) -> ExternalAuditDraft:
        if audit_id is None:
            return ExternalAuditDraft(
                audit_id=None,
                audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
                status=EXTERNAL_AUDIT_STATUS_PLANNED,
                organization_ico="",
                organization_name="",
                organization_address="",
            )
        detail = self.get_detail(int(audit_id))
        participants: list[ParticipantDraft] = []
        id_to_key: dict[int, str] = {}
        for item in detail.participants:
            key = new_client_key()
            id_to_key[int(item.id)] = key
            participants.append(
                ParticipantDraft(
                    client_key=key,
                    role=str(item.role),
                    source_type=str(item.source_type),
                    source_id=int(item.source_id),
                    display_name_snapshot=str(item.display_name_snapshot or ""),
                    display_order=int(item.display_order or 0),
                    db_id=int(item.id),
                )
            )
        visits: list[VisitDraft] = []
        for visit in detail.visits:
            keys = [
                id_to_key[pid]
                for pid in detail.visit_participant_ids.get(int(visit.id), [])
                if pid in id_to_key
            ]
            visits.append(
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=visit.visit_date,
                    workplace_id=int(visit.workplace_id),
                    workplace_name_snapshot=str(visit.workplace_name_snapshot or ""),
                    workplace_address_snapshot=str(
                        visit.workplace_address_snapshot or ""
                    ),
                    time_from=visit.time_from,
                    time_to=visit.time_to,
                    note=visit.note,
                    display_order=int(visit.display_order or 0),
                    participant_keys=keys,
                    db_id=int(visit.id),
                )
            )
        return ExternalAuditDraft(
            audit_id=int(detail.audit.id),
            audit_type=str(detail.audit.audit_type),
            status=str(detail.audit.status),
            organization_ico=str(detail.audit.organization_ico or ""),
            organization_name=str(detail.audit.organization_name or ""),
            organization_address=str(detail.audit.organization_address or ""),
            remind_from=detail.audit.remind_from,
            note=detail.audit.note,
            organization_extra={},
            participants=participants,
            visits=visits,
            attachments=AttachmentStagingState(),
        )

    def save_bundle(self, draft: ExternalAuditDraft) -> ExternalAudit:
        """Atomicky uloží spis + účastníky + program (bez zjištění)."""
        audit_type = _require_audit_type(draft.audit_type)
        status = _require_audit_status(draft.status)
        ico = str(draft.organization_ico or "").strip()
        name = str(draft.organization_name or "").strip()
        address = str(draft.organization_address or "").strip()
        if not ico:
            raise ExternalAuditError("IČ organizace je povinné.")
        if not name:
            raise ExternalAuditError("Název organizace je povinný.")

        # Validace účastníků (role/zdroj) a duplicit ve skupině.
        seen_role_source: set[tuple[str, str, int]] = set()
        for participant in draft.participants:
            source_type, source_id, display = _resolve_participant_source(
                role=participant.role,
                source_type=participant.source_type,
                source_id=participant.source_id,
            )
            key = (participant.role, source_type, source_id)
            if key in seen_role_source:
                raise ExternalAuditError(
                    "Stejná osoba je v této roli už přidaná."
                )
            seen_role_source.add(key)
            participant.source_type = source_type
            participant.source_id = source_id
            if not str(participant.display_name_snapshot or "").strip():
                participant.display_name_snapshot = display

        participant_keys = {item.client_key for item in draft.participants}
        for visit in draft.visits:
            tf, tt = _validate_time_range(visit.time_from, visit.time_to)
            visit.time_from, visit.time_to = tf, tt
            workplace = self._require_workplace(visit.workplace_id)
            # Snapshot při změně provozu obnovit z aktuálních dat, pokud ID sedí.
            if int(visit.workplace_id) == int(workplace.id):
                if not str(visit.workplace_name_snapshot or "").strip():
                    visit.workplace_name_snapshot = str(workplace.name or "").strip()
                if not str(visit.workplace_address_snapshot or "").strip():
                    visit.workplace_address_snapshot = str(
                        workplace.address or ""
                    ).strip()
            for pkey in visit.participant_keys:
                if pkey not in participant_keys:
                    raise ExternalAuditError(
                        "Účastník návštěvy musí patřit stejnému externímu auditu."
                    )
                participant = draft.participant_by_key(pkey)
                if participant is None:
                    raise ExternalAuditError(
                        "Účastník návštěvy musí patřit stejnému externímu auditu."
                    )

        with get_session() as session:
            now = datetime.now()
            if draft.audit_id is None:
                audit = ExternalAudit(
                    audit_type=audit_type,
                    status=status,
                    remind_from=draft.remind_from,
                    organization_ico=ico,
                    organization_name=name,
                    organization_address=address,
                    organization_snapshot_json=_organization_snapshot_payload(
                        ico=ico,
                        name=name,
                        address=address,
                        extra=draft.organization_extra,
                    ),
                    note=(str(draft.note).strip() if draft.note else None) or None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(audit)
                session.flush()
            else:
                audit = self._get_audit(session, int(draft.audit_id))
                audit.audit_type = audit_type
                audit.status = status
                audit.remind_from = draft.remind_from
                audit.organization_ico = ico
                audit.organization_name = name
                audit.organization_address = address
                audit.organization_snapshot_json = _organization_snapshot_payload(
                    ico=ico,
                    name=name,
                    address=address,
                    extra=draft.organization_extra,
                )
                audit.note = (str(draft.note).strip() if draft.note else None) or None
                audit.updated_at = now

                existing_visits = list(
                    session.scalars(
                        select(ExternalAuditVisit).where(
                            ExternalAuditVisit.external_audit_id == audit.id
                        )
                    )
                )
                visit_ids = [int(item.id) for item in existing_visits]
                if visit_ids:
                    for link in session.scalars(
                        select(ExternalAuditVisitParticipant).where(
                            ExternalAuditVisitParticipant.visit_id.in_(visit_ids)
                        )
                    ):
                        session.delete(link)
                    session.flush()
                for visit in existing_visits:
                    session.delete(visit)
                session.flush()
                for participant in session.scalars(
                    select(ExternalAuditParticipant).where(
                        ExternalAuditParticipant.external_audit_id == audit.id
                    )
                ):
                    session.delete(participant)
                session.flush()

            key_to_db_id: dict[str, int] = {}
            for index, participant in enumerate(draft.participants):
                row = ExternalAuditParticipant(
                    external_audit_id=int(audit.id),
                    role=participant.role,
                    source_type=participant.source_type,
                    source_id=int(participant.source_id),
                    display_name_snapshot=str(
                        participant.display_name_snapshot or ""
                    ).strip(),
                    display_order=int(participant.display_order or (index + 1) * 10),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                key_to_db_id[participant.client_key] = int(row.id)
                participant.db_id = int(row.id)

            for index, visit in enumerate(draft.visits):
                row = ExternalAuditVisit(
                    external_audit_id=int(audit.id),
                    visit_date=visit.visit_date,
                    time_from=visit.time_from,
                    time_to=visit.time_to,
                    workplace_id=int(visit.workplace_id),
                    workplace_name_snapshot=str(
                        visit.workplace_name_snapshot or ""
                    ).strip(),
                    workplace_address_snapshot=str(
                        visit.workplace_address_snapshot or ""
                    ).strip(),
                    display_order=int(visit.display_order or (index + 1) * 10),
                    note=(str(visit.note).strip() if visit.note else None) or None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                visit.db_id = int(row.id)
                for pkey in visit.participant_keys:
                    session.add(
                        ExternalAuditVisitParticipant(
                            visit_id=int(row.id),
                            participant_id=key_to_db_id[pkey],
                            created_at=now,
                        )
                    )

            session.commit()
            session.refresh(audit)
            draft.audit_id = int(audit.id)
            session.expunge(audit)
            return audit

    def flush_attachment_staging(
        self,
        audit_id: int,
        staging: AttachmentStagingState,
    ) -> None:
        """Aplikuje odložené přílohy po úspěšném DB uložení spisu."""
        from core.services.attachment_service import attachment_service
        from moduly.externi_audity.constants import ENTITY_EXTERNAL_AUDIT

        entity_type = ENTITY_EXTERNAL_AUDIT
        for attachment_id in list(staging.pending_remove_ids):
            attachment_service.delete(int(attachment_id))
        for path in list(staging.pending_add_paths):
            created = attachment_service.add_file(entity_type, int(audit_id), path)
            if created is None:
                raise ExternalAuditError(
                    f"Nepodařilo se uložit přílohu: {path}"
                )
        staging.clear()

    @staticmethod
    def _require_workplace(workplace_id: int):
        try:
            return require_auditable_workplace_id(workplace_id)
        except ValueError as exc:
            raise ExternalAuditError(str(exc)) from exc

    def _get_audit(self, session: Session, audit_id: int) -> ExternalAudit:
        audit = session.get(ExternalAudit, int(audit_id))
        if audit is None:
            raise ExternalAuditError(f"Externí audit id={audit_id} neexistuje.")
        return audit

    def _get_visit(self, session: Session, visit_id: int) -> ExternalAuditVisit:
        visit = session.get(ExternalAuditVisit, int(visit_id))
        if visit is None:
            raise ExternalAuditError(f"Návštěva id={visit_id} neexistuje.")
        return visit

    def _get_participant(
        self, session: Session, participant_id: int
    ) -> ExternalAuditParticipant:
        participant = session.get(ExternalAuditParticipant, int(participant_id))
        if participant is None:
            raise ExternalAuditError(f"Účastník id={participant_id} neexistuje.")
        return participant

    def _get_finding(
        self, session: Session, finding_id: int
    ) -> ExternalAuditFinding:
        finding = session.get(ExternalAuditFinding, int(finding_id))
        if finding is None:
            raise ExternalAuditError(f"Zjištění id={finding_id} neexistuje.")
        return finding

    def _derived_date_range(
        self, session: Session, audit_id: int
    ) -> tuple[date | None, date | None]:
        row = session.execute(
            select(
                func.min(ExternalAuditVisit.visit_date),
                func.max(ExternalAuditVisit.visit_date),
            ).where(ExternalAuditVisit.external_audit_id == int(audit_id))
        ).one()
        return row[0], row[1]


external_audit_service = ExternalAuditService()
