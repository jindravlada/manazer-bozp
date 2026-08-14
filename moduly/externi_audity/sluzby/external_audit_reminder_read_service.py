"""Čtecí API pro Nadcházející / Připomínky externích auditů (EA-0, bez Dashboard UI)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from core.database.session import get_session
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
    EXTERNAL_AUDIT_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_STATUS_PLANNED,
)
from moduly.externi_audity.modely import ExternalAudit, ExternalAuditFinding
from moduly.externi_audity.sluzby.external_audit_service import external_audit_service

_ACTIVE_AUDIT_STATUSES = frozenset(
    {
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_STATUS_IN_PROGRESS,
    }
)
_OPEN_FINDING_STATUSES = frozenset(
    {
        EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    }
)
_ACTIONABLE_FINDING_TYPES = frozenset(
    {
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    }
)


@dataclass(frozen=True)
class UpcomingExternalAuditItem:
    audit: ExternalAudit
    first_visit_date: date
    date_from: date
    date_to: date


@dataclass(frozen=True)
class ReminderExternalAuditItem:
    audit: ExternalAudit
    date_from: date | None
    date_to: date | None
    remind_effective_from: date


@dataclass(frozen=True)
class ReminderExternalFindingItem:
    finding: ExternalAuditFinding
    audit: ExternalAudit
    due_date: date


class ExternalAuditReminderReadService:
    """Pouze čtení — Dashboard UI se v EA-0 nemění."""

    def list_upcoming(self, *, as_of: date | None = None) -> list[UpcomingExternalAuditItem]:
        """
        Nadcházející: aktivní audity s programem, řazené podle první návštěvy.

        Audit bez programu nemá termín a do Nadcházejících nepatří.
        """
        today = as_of or date.today()
        items: list[UpcomingExternalAuditItem] = []
        for audit in self._list_active_audits():
            date_from, date_to = external_audit_service.derived_date_range(audit.id)
            if date_from is None or date_to is None:
                continue
            # Bez programu / minulé uzavřené termíny se neřadí mezi „nadcházející“,
            # ale aktivní audit po termínu může zůstat v Připomínkách.
            if date_from < today and date_to < today:
                continue
            items.append(
                UpcomingExternalAuditItem(
                    audit=audit,
                    first_visit_date=date_from,
                    date_from=date_from,
                    date_to=date_to,
                )
            )
        items.sort(key=lambda item: (item.first_visit_date, int(item.audit.id)))
        return items

    def list_audit_reminders(
        self, *, as_of: date | None = None
    ) -> list[ReminderExternalAuditItem]:
        """
        Připomínky auditu:
        - od remind_from, nebo od prvního dne programu (bez remind_from),
        - po termínu zůstává, dokud je Naplánováno / Probíhá,
        - Uzavřeno / Zrušeno se nepřipomíná.
        """
        today = as_of or date.today()
        items: list[ReminderExternalAuditItem] = []
        for audit in self._list_active_audits():
            date_from, date_to = external_audit_service.derived_date_range(audit.id)
            if date_from is None:
                # Bez programu nemá termín pro připomínky.
                continue
            effective = audit.remind_from if audit.remind_from is not None else date_from
            if today < effective:
                continue
            items.append(
                ReminderExternalAuditItem(
                    audit=audit,
                    date_from=date_from,
                    date_to=date_to,
                    remind_effective_from=effective,
                )
            )
        items.sort(
            key=lambda item: (
                item.remind_effective_from,
                item.date_from or date.max,
                int(item.audit.id),
            )
        )
        return items

    def list_finding_reminders(
        self, *, as_of: date | None = None
    ) -> list[ReminderExternalFindingItem]:
        """
        Neshoda / PKZ s due_date: od termínu do ručního Vypořádání.
        Silná stránka se nepřipomíná.
        """
        today = as_of or date.today()
        with get_session() as session:
            rows = list(
                session.execute(
                    select(ExternalAuditFinding, ExternalAudit)
                    .join(
                        ExternalAudit,
                        ExternalAudit.id == ExternalAuditFinding.external_audit_id,
                    )
                    .where(
                        ExternalAuditFinding.finding_type.in_(
                            list(_ACTIONABLE_FINDING_TYPES)
                        ),
                        ExternalAuditFinding.status.in_(list(_OPEN_FINDING_STATUSES)),
                        ExternalAuditFinding.due_date.is_not(None),
                    )
                    .order_by(
                        ExternalAuditFinding.due_date,
                        ExternalAuditFinding.id,
                    )
                )
            )
            items: list[ReminderExternalFindingItem] = []
            for finding, audit in rows:
                due = finding.due_date
                if due is None or today < due:
                    continue
                session.expunge(finding)
                session.expunge(audit)
                items.append(
                    ReminderExternalFindingItem(
                        finding=finding,
                        audit=audit,
                        due_date=due,
                    )
                )
            return items

    def _list_active_audits(self) -> list[ExternalAudit]:
        with get_session() as session:
            audits = list(
                session.scalars(
                    select(ExternalAudit)
                    .where(ExternalAudit.status.in_(list(_ACTIVE_AUDIT_STATUSES)))
                    .order_by(ExternalAudit.id)
                )
            )
            for audit in audits:
                session.expunge(audit)
            return audits


external_audit_reminder_read_service = ExternalAuditReminderReadService()
