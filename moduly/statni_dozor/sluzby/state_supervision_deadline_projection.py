"""Read-only projekce termínových položek Státního dozoru (DEADLINE-PROJECTION-6B1).

Nezapisuje, nenačítá Tasky a neváže se na dashboardové položky pozornosti.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from core.shared.constants import ENTITY_STATE_SUPERVISION, FINDING_STATUS_VYPORADANO
from moduly.agenda.constants import PRIORITY_CRITICAL
from moduly.statni_dozor.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    TAB_ANNOUNCEMENT,
    TAB_CONCLUSION,
    TAB_COURSE,
    TAB_SUBJECT_PREPARATION,
)

KIND_PLANNED_START = "planned_start"
KIND_DOCUMENT = "document"
KIND_OBJECTIONS = "objections"
KIND_FINDING = "finding"

TYPE_LABEL_PLANNED_START = "Státní dozor"
TYPE_LABEL_DOCUMENT = "Doklad státního dozoru"
TYPE_LABEL_OBJECTIONS = "Námitky – Státní dozor"
TYPE_LABEL_FINDING = "Zjištění státního dozoru"

TYPE_LABELS = {
    KIND_PLANNED_START: TYPE_LABEL_PLANNED_START,
    KIND_DOCUMENT: TYPE_LABEL_DOCUMENT,
    KIND_OBJECTIONS: TYPE_LABEL_OBJECTIONS,
    KIND_FINDING: TYPE_LABEL_FINDING,
}

LoadSupervisions = Callable[[], Sequence[Any]]
LoadDocuments = Callable[[Sequence[int]], Sequence[Any]]
LoadFindings = Callable[[Sequence[int]], Sequence[Any]]


@dataclass(frozen=True)
class StateSupervisionDeadlineItem:
    """Doménová termínová položka Státního dozoru — bez Qt a bez živé session."""

    identity_key: str
    supervision_id: int
    kind: str
    child_id: int | None
    title: str
    type_label: str
    due_date: date
    event_at: datetime | None
    priority: str
    target_tab: str
    include_in_upcoming: bool
    include_in_reminders: bool
    detail: str = ""


def planned_start_identity(supervision_id: int) -> str:
    return f"ss:{int(supervision_id)}:start"


def document_identity(supervision_id: int, document_id: int) -> str:
    return f"ss:{int(supervision_id)}:doc:{int(document_id)}"


def objections_identity(supervision_id: int) -> str:
    return f"ss:{int(supervision_id)}:objections"


def finding_identity(supervision_id: int, finding_id: int) -> str:
    return f"ss:{int(supervision_id)}:finding:{int(finding_id)}"


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _status_of(record: Any) -> str:
    return str(getattr(record, "status", "") or "").strip()


def _is_cancelled(record: Any) -> bool:
    return _status_of(record) == STATUS_CANCELLED


def _is_closed(record: Any) -> bool:
    return _status_of(record) == STATUS_CLOSED


def _control_label(record: Any) -> str:
    authority = str(getattr(record, "authority_name", "") or "").strip() or "Státní dozor"
    workplace = str(getattr(record, "workplace_name_snapshot", "") or "").strip()
    subject = str(getattr(record, "subject", "") or "").strip()
    extra = workplace or subject
    if extra:
        return f"{authority} – {extra}"
    return authority


def _group_by_supervision_id(rows: Sequence[Any]) -> dict[int, list[Any]]:
    grouped: dict[int, list[Any]] = {}
    for row in rows:
        key = getattr(row, "state_supervision_id", None)
        if key is None:
            key = getattr(row, "entity_id", None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(row)
    return grouped


def _default_load_supervisions() -> Sequence[Any]:
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )

    return state_supervision_service.list_supervisions()


def _default_load_documents(supervision_ids: Sequence[int]) -> Sequence[Any]:
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )

    return state_supervision_required_document_service.list_for_supervisions(
        supervision_ids
    )


def _default_load_findings(supervision_ids: Sequence[int]) -> Sequence[Any]:
    from core.shared.sluzby.finding_service import finding_service

    return finding_service.get_for_entities(
        ENTITY_STATE_SUPERVISION,
        list(supervision_ids),
    )


def _item(
    *,
    identity_key: str,
    supervision_id: int,
    kind: str,
    child_id: int | None,
    title: str,
    due_date: date,
    event_at: datetime | None,
    target_tab: str,
    include_in_upcoming: bool,
    include_in_reminders: bool,
    detail: str = "",
) -> StateSupervisionDeadlineItem:
    return StateSupervisionDeadlineItem(
        identity_key=identity_key,
        supervision_id=int(supervision_id),
        kind=kind,
        child_id=child_id,
        title=title,
        type_label=TYPE_LABELS[kind],
        due_date=due_date,
        event_at=event_at,
        priority=PRIORITY_CRITICAL,
        target_tab=target_tab,
        include_in_upcoming=include_in_upcoming,
        include_in_reminders=include_in_reminders,
        detail=detail,
    )


def _planned_start_item(record: Any) -> StateSupervisionDeadlineItem | None:
    if _is_cancelled(record) or _is_closed(record):
        return None
    if getattr(record, "started_at", None) is not None:
        return None
    if getattr(record, "ended_at", None) is not None:
        return None
    stamp = _as_datetime(getattr(record, "planned_start_at", None))
    if stamp is None:
        return None
    label = _control_label(record)
    return _item(
        identity_key=planned_start_identity(int(record.id)),
        supervision_id=int(record.id),
        kind=KIND_PLANNED_START,
        child_id=None,
        title=label,
        due_date=stamp.date(),
        event_at=stamp,
        target_tab=TAB_ANNOUNCEMENT,
        include_in_upcoming=True,
        include_in_reminders=True,
        detail=label,
    )


def _document_item(record: Any, document: Any) -> StateSupervisionDeadlineItem | None:
    if not bool(getattr(document, "active", True)):
        return None
    if getattr(document, "submitted_at", None) is not None:
        return None
    stamp = _as_datetime(getattr(document, "due_at", None))
    if stamp is None:
        return None
    document_id = getattr(document, "id", None)
    if document_id is None:
        return None
    doc_title = str(getattr(document, "title", "") or "").strip() or "Doklad"
    label = _control_label(record)
    return _item(
        identity_key=document_identity(int(record.id), int(document_id)),
        supervision_id=int(record.id),
        kind=KIND_DOCUMENT,
        child_id=int(document_id),
        title=f"{doc_title} – {label}",
        due_date=stamp.date(),
        event_at=stamp,
        target_tab=TAB_SUBJECT_PREPARATION,
        include_in_upcoming=False,
        include_in_reminders=True,
        detail=label,
    )


def _objections_item(record: Any) -> StateSupervisionDeadlineItem | None:
    if _is_cancelled(record):
        return None
    if getattr(record, "objections_submitted_at", None) is not None:
        return None
    stamp = _as_datetime(getattr(record, "objections_due_at", None))
    if stamp is None:
        return None
    label = _control_label(record)
    return _item(
        identity_key=objections_identity(int(record.id)),
        supervision_id=int(record.id),
        kind=KIND_OBJECTIONS,
        child_id=None,
        title=f"Námitky – {label}",
        due_date=stamp.date(),
        event_at=stamp,
        target_tab=TAB_CONCLUSION,
        include_in_upcoming=True,
        include_in_reminders=True,
        detail=label,
    )


def _finding_has_task_id(finding: Any) -> bool:
    return getattr(finding, "task_id", None) is not None


def _finding_item(record: Any, finding: Any) -> StateSupervisionDeadlineItem | None:
    if _finding_has_task_id(finding):
        return None
    status = str(getattr(finding, "status", "") or "").strip()
    if status == FINDING_STATUS_VYPORADANO:
        return None
    due = _as_date(getattr(finding, "due_date", None))
    if due is None:
        return None
    finding_id = getattr(finding, "id", None)
    if finding_id is None:
        return None
    description = str(getattr(finding, "description", "") or "").strip() or "Zjištění"
    label = _control_label(record)
    return _item(
        identity_key=finding_identity(int(record.id), int(finding_id)),
        supervision_id=int(record.id),
        kind=KIND_FINDING,
        child_id=int(finding_id),
        title=f"{description} – {label}",
        due_date=due,
        event_at=None,
        target_tab=TAB_COURSE,
        include_in_upcoming=False,
        include_in_reminders=True,
        detail=label,
    )


def _sort_key(item: StateSupervisionDeadlineItem) -> tuple:
    event = item.event_at
    if event is None:
        event = datetime.combine(item.due_date, time.min)
    return (
        item.due_date,
        event,
        item.type_label.casefold(),
        item.title.casefold(),
        item.identity_key,
    )


class StateSupervisionDeadlineProjectionService:
    """Dávková read-only projekce termínů Státního dozoru."""

    def list_items(
        self,
        *,
        today: date | None = None,
        load_supervisions: LoadSupervisions | None = None,
        load_documents: LoadDocuments | None = None,
        load_findings: LoadFindings | None = None,
    ) -> list[StateSupervisionDeadlineItem]:
        """Vrátí seřazené termínové položky. ``today`` se nepoužívá k filtrování."""
        del today
        supervisions_loader = load_supervisions or _default_load_supervisions
        documents_loader = load_documents or _default_load_documents
        findings_loader = load_findings or _default_load_findings

        records = list(supervisions_loader())
        if not records:
            return []

        candidates = [
            record
            for record in records
            if getattr(record, "id", None) is not None and not _is_cancelled(record)
        ]
        if not candidates:
            return []

        ids = [int(record.id) for record in candidates]
        documents_by_id = _group_by_supervision_id(documents_loader(ids))
        findings_by_id = _group_by_supervision_id(findings_loader(ids))

        items: list[StateSupervisionDeadlineItem] = []
        for record in candidates:
            numeric_id = int(record.id)
            planned = _planned_start_item(record)
            if planned is not None:
                items.append(planned)
            objections = _objections_item(record)
            if objections is not None:
                items.append(objections)
            for document in documents_by_id.get(numeric_id, ()):
                document_item = _document_item(record, document)
                if document_item is not None:
                    items.append(document_item)
            for finding in findings_by_id.get(numeric_id, ()):
                finding_item = _finding_item(record, finding)
                if finding_item is not None:
                    items.append(finding_item)

        items.sort(key=_sort_key)
        return items


state_supervision_deadline_projection_service = (
    StateSupervisionDeadlineProjectionService()
)


def list_state_supervision_deadline_items(
    *,
    today: date | None = None,
    load_supervisions: LoadSupervisions | None = None,
    load_documents: LoadDocuments | None = None,
    load_findings: LoadFindings | None = None,
) -> list[StateSupervisionDeadlineItem]:
    """Veřejné API projekce. Nic nezapisuje a nenačítá Tasky."""
    return state_supervision_deadline_projection_service.list_items(
        today=today,
        load_supervisions=load_supervisions,
        load_documents=load_documents,
        load_findings=load_findings,
    )
