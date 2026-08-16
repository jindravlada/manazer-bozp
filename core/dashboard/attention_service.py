"""Lehké sestavení položek panelu Nadcházející události a úkoly."""

from __future__ import annotations

from datetime import date, datetime, time

from core.dashboard.attention_item import (
    ITEM_TYPE_AUDIT,
    ITEM_TYPE_EXTERNAL_AUDIT,
    ITEM_TYPE_EXTERNAL_AUDIT_NC,
    ITEM_TYPE_EXTERNAL_AUDIT_PKZ,
    ITEM_TYPE_INSPECTION,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_OZO_CONTRACT,
    ITEM_TYPE_OZO_PERSON_CERTIFICATE,
    ITEM_TYPE_PERIODIC,
    ITEM_TYPE_QUALIFICATION_CERTIFICATE,
    ITEM_TYPE_TASK,
    ITEM_TYPE_YEARLY_PLAN_MONTH,
    SOURCE_LABEL_AUDIT,
    SOURCE_LABEL_EXTERNAL_AUDIT,
    SOURCE_LABEL_INSPECTION,
    SOURCE_LABEL_OZO_CONTRACT,
    SOURCE_LABEL_OZO_PERSON,
    SOURCE_LABEL_PERIODIC,
    SOURCE_LABEL_QUALIFICATION,
    SOURCE_LABEL_YEARLY_PLAN,
    AttentionItem,
)
from core.shared.task_source_display import task_source_short_label
from core.shared.working_days import first_working_day
from moduly.audity.sluzby.audit_service import audit_service
from moduly.periodicke_cinnosti.constants import PLACE_KIND_NONE, format_place
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    is_due_for_attention,
    periodic_activity_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.rocni_plan.constants import (
    month_planning_attention_title,
    month_planning_source_id,
)
from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
from moduly.schuzky.constants import STATUS_PLANNED
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.smlouvy_ozo.constants import STATUS_EXPIRED, UNIT_DAYS, status_label
from moduly.smlouvy_ozo.sluzby.certificate_attention import (
    is_certificate_due_for_attention,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
from moduly.smlouvy_ozo.sluzby.ozo_contract_validity import (
    is_due_for_attention as is_ozo_contract_due_for_attention,
)
from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
    qualification_certificate_service,
)
from moduly.ukoly.sluzby.task_service import task_service
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_LABELS,
    EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    EXTERNAL_AUDIT_STATUS_LABELS,
    format_display_date,
)
from moduly.externi_audity.sluzby.external_audit_reminder_read_service import (
    audit_type_label,
    external_audit_reminder_read_service,
)
from moduly.externi_audity.sluzby.external_audit_text import shorten_finding_title


def build_sort_key(
    due_date: date | None,
    *,
    item_type: str = "",
    title: str = "",
    source_id: int = 0,
    today: date | None = None,
    due_datetime: datetime | None = None,
) -> tuple:
    """Řazení: datum/čas vzestupně, potom typ, název, source_id."""
    if due_datetime is not None:
        dt_key = due_datetime
    elif due_date is None:
        dt_key = datetime.max
    else:
        dt_key = datetime.combine(due_date, time.min)

    return (
        dt_key,
        (item_type or "").casefold(),
        (title or "").casefold(),
        int(source_id),
    )


def _task_source_label(task) -> str:
    label = (task_source_short_label(task) or "").strip()
    if not label or label == "—":
        return ""
    return label


def _from_tasks(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for task in task_service.get_all_tasks():
        if task.computed_status in ("Ukončeno", "Zrušeno"):
            continue
        title = (task.title or "").strip() or f"Úkol #{task.id}"
        priority = task.priority or ""
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_TASK,
                source_type=ITEM_TYPE_TASK,
                source_id=task.id,
                title=title,
                date=task.due_date,
                subtitle=_task_source_label(task),
                status=task.computed_status or "",
                priority=priority,
                open_metadata={"source_type": ITEM_TYPE_TASK, "source_id": task.id},
                sort_key=build_sort_key(
                    task.due_date,
                    item_type=ITEM_TYPE_TASK,
                    title=title,
                    source_id=task.id,
                ),
            )
        )
    return items


def audit_title(audit) -> str:
    place = (audit.workplace_name or "").strip()
    if place:
        return f"Audit – {place}"
    number = (audit.number or "").strip()
    if number:
        return f"Audit – {number}"
    title = (audit.title or "").strip()
    if title:
        return f"Audit – {title}"
    return f"Audit #{audit.id}"


def _from_audits(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for audit in audit_service.get_all():
        due_date = audit.started_at
        if due_date is None:
            continue
        if audit.finished_at is not None:
            continue
        title = audit_title(audit)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_AUDIT,
                source_type=ITEM_TYPE_AUDIT,
                source_id=audit.id,
                title=title,
                date=due_date,
                subtitle=SOURCE_LABEL_AUDIT,
                status=audit.status or "",
                priority="",
                open_metadata={"source_type": ITEM_TYPE_AUDIT, "source_id": audit.id},
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_AUDIT,
                    title=title,
                    source_id=audit.id,
                ),
            )
        )
    return items


def inspection_title(inspection) -> str:
    place = (inspection.workplace_name or "").strip()
    if place:
        return f"Prověrka BOZP – {place}"
    number = (inspection.number or "").strip()
    if number:
        return f"Prověrka BOZP – {number}"
    title = (inspection.title or "").strip()
    if title:
        return f"Prověrka BOZP – {title}"
    return f"Prověrka BOZP #{inspection.id}"


def _from_inspections(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for inspection in bozp_inspection_service.get_all():
        due_date = inspection.started_at
        if due_date is None:
            continue
        if inspection.finished_at is not None:
            continue
        title = inspection_title(inspection)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_INSPECTION,
                source_type=ITEM_TYPE_INSPECTION,
                source_id=inspection.id,
                title=title,
                date=due_date,
                subtitle=SOURCE_LABEL_INSPECTION,
                status=inspection.status or "",
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_INSPECTION,
                    "source_id": inspection.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_INSPECTION,
                    title=title,
                    source_id=inspection.id,
                ),
            )
        )
    return items


def _meeting_subtitle(meeting) -> str:
    parts: list[str] = []
    location = (meeting.location or "").strip()
    organizer = (meeting.organizer_name or "").strip()
    if location:
        parts.append(location)
    if organizer:
        parts.append(organizer)
    return " · ".join(parts)


def _from_meetings(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for meeting in meeting_service.get_all():
        if (meeting.status or "") != STATUS_PLANNED:
            continue
        starts_at = meeting.starts_at
        if starts_at is None:
            continue
        title = (meeting.title or "").strip() or "Bez názvu"
        event_type = (getattr(meeting, "event_type", None) or "").strip()
        if event_type:
            title = f"{event_type} – {title}"
        ends_at = meeting.ends_at
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_MEETING,
                source_type=ITEM_TYPE_MEETING,
                source_id=meeting.id,
                title=title,
                date=starts_at.date(),
                subtitle=_meeting_subtitle(meeting),
                status=meeting.status or "",
                priority="",
                event_at=starts_at,
                ends_at=ends_at,
                open_metadata={
                    "source_type": ITEM_TYPE_MEETING,
                    "source_id": meeting.id,
                },
                sort_key=build_sort_key(
                    starts_at.date(),
                    item_type=ITEM_TYPE_MEETING,
                    title=title,
                    source_id=meeting.id,
                    due_datetime=starts_at,
                ),
            )
        )
    return items


def _periodic_place_label(activity) -> str:
    kind = getattr(activity, "place_kind", PLACE_KIND_NONE) or PLACE_KIND_NONE
    if kind == PLACE_KIND_NONE:
        return ""
    return (format_place(activity) or "").strip()


def _periodic_subtitle(activity) -> str:
    place = _periodic_place_label(activity)
    if place:
        return f"{SOURCE_LABEL_PERIODIC} · {place}"
    return SOURCE_LABEL_PERIODIC


def _from_periodics(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for activity in periodic_activity_service.get_all(active_only=True):
        if not is_due_for_attention(
            next_due_date=activity.next_due_date,
            notify_every=activity.notify_every,
            notify_unit=activity.notify_unit,
            active=bool(activity.active),
            today=today,
        ):
            continue
        title = (activity.title or "").strip() or f"Periodická činnost #{activity.id}"
        due_date = activity.next_due_date
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_PERIODIC,
                source_type=ITEM_TYPE_PERIODIC,
                source_id=activity.id,
                title=title,
                date=due_date,
                subtitle=_periodic_subtitle(activity),
                status="Aktivní",
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_PERIODIC,
                    "source_id": activity.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_PERIODIC,
                    title=title,
                    source_id=activity.id,
                ),
            )
        )
    return items


def _from_yearly_plan_month(today: date) -> list[AttentionItem]:
    if not yearly_plan_service.should_show_month_planning_attention(today=today):
        return []
    year = today.year
    month = today.month
    title = month_planning_attention_title(year, month)
    source_id = month_planning_source_id(year, month)
    due_date = first_working_day(year, month)
    return [
        AttentionItem(
            item_type=ITEM_TYPE_YEARLY_PLAN_MONTH,
            source_type=ITEM_TYPE_YEARLY_PLAN_MONTH,
            source_id=source_id,
            title=title,
            date=due_date,
            subtitle=SOURCE_LABEL_YEARLY_PLAN,
            status="",
            priority="",
            open_metadata={
                "source_type": ITEM_TYPE_YEARLY_PLAN_MONTH,
                "source_id": source_id,
                "year": year,
                "month": month,
            },
            sort_key=build_sort_key(
                due_date,
                item_type=ITEM_TYPE_YEARLY_PLAN_MONTH,
                title=title,
                source_id=source_id,
            ),
        )
    ]


def _ozo_contract_subtitle(contract, *, expired: bool) -> str:
    """Zdroj = Smlouvy OZO; číslo smlouvy a Po platnosti v subtitulku (sloupec Zdroj / Co hoří)."""
    number = (contract.contract_number or "").strip()
    base = (
        f"{SOURCE_LABEL_OZO_CONTRACT} · {number}"
        if number
        else SOURCE_LABEL_OZO_CONTRACT
    )
    if expired:
        return f"{status_label(STATUS_EXPIRED)} · {base}"
    return base


def _from_ozo_contracts(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for contract in ozo_contract_service.get_all(active_only=True):
        if not is_ozo_contract_due_for_attention(
            active=bool(contract.active),
            indefinite=bool(contract.indefinite),
            valid_to=contract.valid_to,
            notify_before_value=int(contract.notify_before_value or 0),
            notify_before_unit=contract.notify_before_unit or "",
            today=today,
        ):
            continue
        title = (contract.employer_name or "").strip() or f"Smlouva OZO #{contract.id}"
        due_date = contract.valid_to
        expired = bool(due_date is not None and today > due_date)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_OZO_CONTRACT,
                source_type=ITEM_TYPE_OZO_CONTRACT,
                source_id=contract.id,
                title=title,
                date=due_date,
                subtitle=_ozo_contract_subtitle(contract, expired=expired),
                status=status_label(STATUS_EXPIRED) if expired else "",
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_OZO_CONTRACT,
                    "source_id": contract.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_OZO_CONTRACT,
                    title=title,
                    source_id=contract.id,
                ),
            )
        )
    return items


def _certificate_subtitle(source_label: str, number: str, *, expired: bool) -> str:
    number = (number or "").strip()
    base = f"{source_label} · {number}" if number else source_label
    if expired:
        return f"{status_label(STATUS_EXPIRED)} · {base}"
    return base


def _from_ozo_person_certificates(today: date) -> list[AttentionItem]:
    period = ozo_person_service.get_open_period()
    if period is None:
        return []
    if not is_certificate_due_for_attention(
        indefinite=False,
        certificate_valid_to=period.certificate_valid_to,
        notify_before_value=int(getattr(period, "notify_before_value", 0) or 0),
        notify_before_unit=getattr(period, "notify_before_unit", None) or UNIT_DAYS,
        today=today,
    ):
        return []
    due_date = period.certificate_valid_to
    expired = bool(due_date is not None and today > due_date)
    title = ozo_person_service.full_name(period) or "OZO v prevenci rizik"
    number = (period.certificate_number or "").strip()
    person = ozo_person_service.get()
    source_id = person.id if person is not None else period.id
    return [
        AttentionItem(
            item_type=ITEM_TYPE_OZO_PERSON_CERTIFICATE,
            source_type=ITEM_TYPE_OZO_PERSON_CERTIFICATE,
            source_id=source_id,
            title=title,
            date=due_date,
            subtitle=_certificate_subtitle(
                SOURCE_LABEL_OZO_PERSON, number, expired=expired
            ),
            status=status_label(STATUS_EXPIRED) if expired else "",
            priority="",
            open_metadata={
                "source_type": ITEM_TYPE_OZO_PERSON_CERTIFICATE,
                "source_id": source_id,
            },
            sort_key=build_sort_key(
                due_date,
                item_type=ITEM_TYPE_OZO_PERSON_CERTIFICATE,
                title=title,
                source_id=source_id,
            ),
        )
    ]


def _from_qualification_certificates(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for certificate in qualification_certificate_service.get_all(active_only=True):
        period = qualification_certificate_service.get_open_period(certificate)
        if period is None:
            continue
        if not is_certificate_due_for_attention(
            indefinite=bool(period.indefinite),
            certificate_valid_to=period.certificate_valid_to,
            notify_before_value=int(period.notify_before_value or 0),
            notify_before_unit=period.notify_before_unit or UNIT_DAYS,
            today=today,
        ):
            continue
        due_date = period.certificate_valid_to
        expired = bool(due_date is not None and today > due_date)
        title = (certificate.name or "").strip() or f"Osvědčení #{certificate.id}"
        number = (period.certificate_number or "").strip()
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_QUALIFICATION_CERTIFICATE,
                source_type=ITEM_TYPE_QUALIFICATION_CERTIFICATE,
                source_id=certificate.id,
                title=title,
                date=due_date,
                subtitle=_certificate_subtitle(
                    SOURCE_LABEL_QUALIFICATION, number, expired=expired
                ),
                status=status_label(STATUS_EXPIRED) if expired else "",
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_QUALIFICATION_CERTIFICATE,
                    "source_id": certificate.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_QUALIFICATION_CERTIFICATE,
                    title=title,
                    source_id=certificate.id,
                ),
            )
        )
    return items


def _external_audit_status_label(audit) -> str:
    return EXTERNAL_AUDIT_STATUS_LABELS.get(
        str(audit.status), str(audit.status or "")
    )


def _external_finding_item_type(finding_type: str) -> str:
    if finding_type == EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT:
        return ITEM_TYPE_EXTERNAL_AUDIT_PKZ
    return ITEM_TYPE_EXTERNAL_AUDIT_NC


def _external_audit_day_tooltip(item) -> str:
    audit = item.audit
    workplaces = ", ".join(item.workplace_names) if item.workplace_names else "—"
    times = ", ".join(item.time_labels) if item.time_labels else "—"
    return "\n".join(
        [
            audit_type_label(audit),
            f"Organizace: {audit.organization_name or '—'}",
            f"IČ: {audit.organization_ico or '—'}",
            f"Provozy: {workplaces}",
            f"Čas: {times}",
            f"Stav: {_external_audit_status_label(audit)}",
        ]
    )


def _external_audit_reminder_tooltip(item) -> str:
    audit = item.audit
    workplaces = ", ".join(item.workplace_names) if item.workplace_names else "—"
    date_range = (
        f"{format_display_date(item.date_from)} – {format_display_date(item.date_to)}"
        if item.date_from is not None
        else "—"
    )
    return "\n".join(
        [
            audit_type_label(audit),
            f"Organizace: {audit.organization_name or '—'}",
            f"IČ: {audit.organization_ico or '—'}",
            f"Termín: {date_range}",
            f"Provozy: {workplaces}",
            f"Stav: {_external_audit_status_label(audit)}",
        ]
    )


def _external_finding_tooltip(finding, audit) -> str:
    resolution = str(getattr(finding, "resolution_text", None) or "").strip()
    lines = [
        str(finding.description or "").strip() or "—",
        "",
        f"Typ auditu: {audit_type_label(audit)}",
        f"Organizace: {audit.organization_name or '—'}",
        f"Stav zjištění: {EXTERNAL_AUDIT_FINDING_STATUS_LABELS.get(str(finding.status), finding.status)}",
        f"Termín: {format_display_date(finding.due_date)}",
    ]
    if resolution:
        lines.append(f"Způsob vypořádání: {resolution}")
    return "\n".join(lines)


def _from_external_audit_days(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for day in external_audit_reminder_read_service.list_upcoming(as_of=today):
        audit_id = int(day.audit.id)
        identity = f"external-audit:{audit_id}:{day.visit_date.isoformat()}"
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_EXTERNAL_AUDIT,
                source_type=ITEM_TYPE_EXTERNAL_AUDIT,
                source_id=audit_id,
                title="Externí audit",
                date=day.visit_date,
                subtitle=SOURCE_LABEL_EXTERNAL_AUDIT,
                status=_external_audit_status_label(day.audit),
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_EXTERNAL_AUDIT,
                    "source_id": audit_id,
                    "visit_date": day.visit_date.isoformat(),
                    "focus_tab": "program",
                    "identity": identity,
                },
                sort_key=build_sort_key(
                    day.visit_date,
                    item_type=ITEM_TYPE_EXTERNAL_AUDIT,
                    title="Externí audit",
                    source_id=audit_id,
                ),
                detail_tooltip=_external_audit_day_tooltip(day),
                identity_key=identity,
            )
        )
    return items


def get_external_audit_reminder_items(
    *, today: date | None = None
) -> list[AttentionItem]:
    """Připomínky externích auditů — jeden řádek za audit."""
    today = today or date.today()
    items: list[AttentionItem] = []
    for row in external_audit_reminder_read_service.list_audit_reminders(as_of=today):
        audit_id = int(row.audit.id)
        identity = f"external-audit:{audit_id}"
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_EXTERNAL_AUDIT,
                source_type=ITEM_TYPE_EXTERNAL_AUDIT,
                source_id=audit_id,
                title="Externí audit",
                date=row.date_from,
                subtitle=SOURCE_LABEL_EXTERNAL_AUDIT,
                status=_external_audit_status_label(row.audit),
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_EXTERNAL_AUDIT,
                    "source_id": audit_id,
                    "focus_tab": "spis",
                    "identity": identity,
                },
                sort_key=build_sort_key(
                    row.date_from,
                    item_type=ITEM_TYPE_EXTERNAL_AUDIT,
                    title="Externí audit",
                    source_id=audit_id,
                ),
                detail_tooltip=_external_audit_reminder_tooltip(row),
                identity_key=identity,
            )
        )
    return items


def get_external_finding_reminder_items(
    *, today: date | None = None
) -> list[AttentionItem]:
    """Připomínky Neshod/PKZ od termínu do Vypořádáno."""
    today = today or date.today()
    items: list[AttentionItem] = []
    for row in external_audit_reminder_read_service.list_finding_reminders(as_of=today):
        finding = row.finding
        audit = row.audit
        finding_id = int(finding.id)
        item_type = _external_finding_item_type(str(finding.finding_type))
        title = shorten_finding_title(finding.description) or "—"
        identity = f"external-audit-finding:{finding_id}"
        items.append(
            AttentionItem(
                item_type=item_type,
                source_type=item_type,
                source_id=finding_id,
                title=title,
                date=row.due_date,
                subtitle=SOURCE_LABEL_EXTERNAL_AUDIT,
                status=EXTERNAL_AUDIT_FINDING_STATUS_LABELS.get(
                    str(finding.status), str(finding.status or "")
                ),
                priority="",
                open_metadata={
                    "source_type": item_type,
                    "source_id": finding_id,
                    "audit_id": int(audit.id),
                    "finding_type": str(finding.finding_type),
                    "focus_tab": "findings",
                    "identity": identity,
                },
                sort_key=build_sort_key(
                    row.due_date,
                    item_type=item_type,
                    title=title,
                    source_id=finding_id,
                ),
                detail_tooltip=_external_finding_tooltip(finding, audit),
                identity_key=identity,
            )
        )
    return items


def get_periodic_reminder_items(*, today: date | None = None) -> list[AttentionItem]:
    """Periodické činnosti od data připomenutí — pro panel Připomínky."""
    today = today or date.today()
    return _from_periodics(today)


def get_yearly_plan_month_reminder_items(
    *,
    today: date | None = None,
) -> list[AttentionItem]:
    """Připomínka zpracování měsíce od prvního pracovního dne — pro Připomínky."""
    today = today or date.today()
    return _from_yearly_plan_month(today)


def get_attention_items(*, today: date | None = None) -> list[AttentionItem]:
    """Vrátí položky pro Nadcházející (včetně periodik a měsíčního plánu).

    Externí Neshody/PKZ sem nepatří — jen dny programu auditu a úkoly Agendy.
    Připomínky findings berou get_external_finding_reminder_items.
    """
    today = today or date.today()
    items = (
        _from_tasks(today)
        + _from_audits(today)
        + _from_external_audit_days(today)
        + _from_inspections(today)
        + _from_meetings(today)
        + _from_periodics(today)
        + _from_yearly_plan_month(today)
        + _from_ozo_contracts(today)
        + _from_ozo_person_certificates(today)
        + _from_qualification_certificates(today)
    )
    items.sort(key=lambda item: item.sort_key)
    return items
