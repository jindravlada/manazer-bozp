"""Čtecí API pro Nadcházející / Připomínky externích auditů (EA-0/EA-3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from core.database.session import get_session
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
    EXTERNAL_AUDIT_STATUS_CANCELLED,
    EXTERNAL_AUDIT_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_STATUS_PLANNED,
    EXTERNAL_AUDIT_TYPE_LABELS,
)
from moduly.externi_audity.modely import (
    ExternalAudit,
    ExternalAuditFinding,
    ExternalAuditVisit,
)

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
    """Jeden řádek Nadcházejících = jedinečný den programu auditu."""

    audit: ExternalAudit
    visit_date: date
    date_from: date
    date_to: date
    workplace_names: tuple[str, ...] = ()
    time_labels: tuple[str, ...] = ()

    @property
    def first_visit_date(self) -> date:
        """Zpětná kompatibilita s EA-0 testy."""
        return self.visit_date


@dataclass(frozen=True)
class ReminderExternalAuditItem:
    audit: ExternalAudit
    date_from: date | None
    date_to: date | None
    remind_effective_from: date
    workplace_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReminderExternalFindingItem:
    finding: ExternalAuditFinding
    audit: ExternalAudit
    due_date: date


@dataclass(frozen=True)
class UpcomingExternalFindingItem:
    finding: ExternalAuditFinding
    audit: ExternalAudit
    due_date: date


@dataclass
class _AuditBundle:
    audit: ExternalAudit
    visits: list[ExternalAuditVisit] = field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None


def _format_visit_time(visit: ExternalAuditVisit) -> str | None:
    tf = str(visit.time_from or "").strip()
    tt = str(visit.time_to or "").strip()
    if tf and tt:
        return f"{tf}–{tt}"
    if tf:
        return tf
    if tt:
        return tt
    return None


def _workplace_names(visits: list[ExternalAuditVisit]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for visit in visits:
        name = str(visit.workplace_name_snapshot or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return tuple(names)


class ExternalAuditReminderReadService:
    """Pouze čtení — žádný zápis při refreshi Dashboardu."""

    def list_upcoming(self, *, as_of: date | None = None) -> list[UpcomingExternalAuditItem]:
        """
        Nadcházející: jeden řádek za každý jedinečný den programu (>= today).

        Více návštěv stejného auditu ve stejný den → jeden řádek.
        Minulé dny se nezobrazují. Uzavřeno/Zrušeno / bez programu → nic.
        """
        today = as_of or date.today()
        items: list[UpcomingExternalAuditItem] = []
        for bundle in self._load_active_bundles().values():
            if bundle.date_from is None or bundle.date_to is None:
                continue
            by_day: dict[date, list[ExternalAuditVisit]] = defaultdict(list)
            for visit in bundle.visits:
                if visit.visit_date >= today:
                    by_day[visit.visit_date].append(visit)
            for visit_date in sorted(by_day):
                day_visits = by_day[visit_date]
                times = tuple(
                    label
                    for label in (_format_visit_time(visit) for visit in day_visits)
                    if label
                )
                items.append(
                    UpcomingExternalAuditItem(
                        audit=bundle.audit,
                        visit_date=visit_date,
                        date_from=bundle.date_from,
                        date_to=bundle.date_to,
                        workplace_names=_workplace_names(day_visits),
                        time_labels=times,
                    )
                )
        items.sort(
            key=lambda item: (item.visit_date, int(item.audit.id))
        )
        return items

    def list_audit_reminders(
        self, *, as_of: date | None = None
    ) -> list[ReminderExternalAuditItem]:
        """
        Připomínky auditu — jeden řádek za celý audit:
        - od remind_from, nebo od prvního dne programu,
        - bez programu se nezobrazuje,
        - po konci programu zůstává do Uzavřeno/Zrušeno.
        """
        today = as_of or date.today()
        items: list[ReminderExternalAuditItem] = []
        for bundle in self._load_active_bundles().values():
            if bundle.date_from is None:
                continue
            effective = (
                bundle.audit.remind_from
                if bundle.audit.remind_from is not None
                else bundle.date_from
            )
            if today < effective:
                continue
            items.append(
                ReminderExternalAuditItem(
                    audit=bundle.audit,
                    date_from=bundle.date_from,
                    date_to=bundle.date_to,
                    remind_effective_from=effective,
                    workplace_names=_workplace_names(bundle.visits),
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

    def list_upcoming_findings(
        self, *, as_of: date | None = None
    ) -> list[UpcomingExternalFindingItem]:
        """Neshoda/PKZ s due_date >= today, stavy Otevřeno/Řeší se; ne Zrušený audit."""
        today = as_of or date.today()
        items: list[UpcomingExternalFindingItem] = []
        for finding, audit in self._load_open_findings():
            if str(audit.status) == EXTERNAL_AUDIT_STATUS_CANCELLED:
                continue
            due = finding.due_date
            if due is None or due < today:
                continue
            items.append(
                UpcomingExternalFindingItem(
                    finding=finding,
                    audit=audit,
                    due_date=due,
                )
            )
        items.sort(key=lambda item: (item.due_date, int(item.finding.id)))
        return items

    def list_finding_reminders(
        self, *, as_of: date | None = None
    ) -> list[ReminderExternalFindingItem]:
        """
        Neshoda/PKZ: od due_date (včetně) do Vypořádáno.
        Zrušený audit → nezobrazovat. Uzavřený audit otevřené zjištění ponechá.
        """
        today = as_of or date.today()
        items: list[ReminderExternalFindingItem] = []
        for finding, audit in self._load_open_findings():
            if str(audit.status) == EXTERNAL_AUDIT_STATUS_CANCELLED:
                continue
            due = finding.due_date
            if due is None or today < due:
                continue
            items.append(
                ReminderExternalFindingItem(
                    finding=finding,
                    audit=audit,
                    due_date=due,
                )
            )
        items.sort(key=lambda item: (item.due_date, int(item.finding.id)))
        return items

    def _load_active_bundles(self) -> dict[int, _AuditBundle]:
        with get_session() as session:
            audits = list(
                session.scalars(
                    select(ExternalAudit)
                    .where(ExternalAudit.status.in_(list(_ACTIVE_AUDIT_STATUSES)))
                    .order_by(ExternalAudit.id)
                )
            )
            if not audits:
                return {}
            audit_ids = [int(audit.id) for audit in audits]
            visits = list(
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
            bundles: dict[int, _AuditBundle] = {}
            for audit in audits:
                session.expunge(audit)
                bundles[int(audit.id)] = _AuditBundle(audit=audit)
            for visit in visits:
                session.expunge(visit)
                bundle = bundles.get(int(visit.external_audit_id))
                if bundle is None:
                    continue
                bundle.visits.append(visit)
                if bundle.date_from is None or visit.visit_date < bundle.date_from:
                    bundle.date_from = visit.visit_date
                if bundle.date_to is None or visit.visit_date > bundle.date_to:
                    bundle.date_to = visit.visit_date
            return bundles

    def _load_open_findings(
        self,
    ) -> list[tuple[ExternalAuditFinding, ExternalAudit]]:
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
            result: list[tuple[ExternalAuditFinding, ExternalAudit]] = []
            seen_audit_ids: set[int] = set()
            for finding, audit in rows:
                session.expunge(finding)
                audit_id = int(audit.id)
                if audit_id not in seen_audit_ids:
                    session.expunge(audit)
                    seen_audit_ids.add(audit_id)
                result.append((finding, audit))
            return result


def audit_type_label(audit: ExternalAudit) -> str:
    return EXTERNAL_AUDIT_TYPE_LABELS.get(
        str(audit.audit_type), str(audit.audit_type or "—")
    )


external_audit_reminder_read_service = ExternalAuditReminderReadService()
