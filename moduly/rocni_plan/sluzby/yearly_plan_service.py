"""Služba Ročního plánu – CRUD, zrušení, přesun, validace, odvozené stavy."""

from __future__ import annotations

import calendar
from datetime import date, datetime

from moduly.rocni_plan.constants import (
    DEFAULT_STATUS,
    DISPLAY_CANCELLED,
    DISPLAY_DONE,
    DISPLAY_PLANNED,
    DISPLAY_REST,
    DISPLAY_VIA_MEETING,
    DISPLAY_VIA_TASK,
    ITEM_STATUSES,
    MAX_YEAR,
    MIN_YEAR,
    MONTH_ALREADY_PROCESSED_MESSAGE,
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
    SOURCE_LABEL_MANUAL,
    SOURCE_LABEL_PERIODIC,
    STATUS_CANCELLED,
    STATUS_PLANNED,
    STATUS_VIA_MEETING,
    STATUS_VIA_TASK,
    link_label,
)
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove
from moduly.rocni_plan.modely.yearly_plan_month_status import YearlyPlanMonthStatus
from moduly.rocni_plan.modely.yearly_plan_row import YearlyPlanRow
from moduly.rocni_plan.repository.yearly_plan_repository import (
    YearlyPlanItemMoveRepository,
    YearlyPlanItemRepository,
    YearlyPlanMonthStatusRepository,
)
from core.shared.working_days import first_working_day
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    add_period,
    periodic_activity_service,
)
from moduly.schuzky.constants import (
    STATUS_CLOSED as MEETING_CLOSED,
)
from moduly.schuzky.constants import (
    STATUS_HELD as MEETING_HELD,
)
from moduly.schuzky.constants import (
    STATUS_PLANNED as MEETING_PLANNED,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.ukoly.sluzby.task_service import task_service

_MAX_PERIODIC_PROJECTIONS = 5000


class YearlyPlanValidationError(ValueError):
    """Neplatná data položky Ročního plánu."""


def month_has_ended(year: int, month: int, *, today: date | None = None) -> bool:
    """True, pokud kalendářní měsíc year/month už skončil vůči today."""
    today = today or date.today()
    last_day = calendar.monthrange(year, month)[1]
    return today > date(year, month, last_day)


def resolve_display_status(item: YearlyPlanItem, *, today: date | None = None) -> str:
    """
    Odvozený stav pro UI.

    Splněno a Rest se neukládají – vždy z Úkolu/Události a data.
    """
    today = today or date.today()

    if (item.status or "") == STATUS_CANCELLED:
        return DISPLAY_CANCELLED

    base = DISPLAY_PLANNED

    if item.task_id is not None:
        task = task_service.get_task_by_id(item.task_id)
        if task is not None and task.computed_status == "Ukončeno":
            return DISPLAY_DONE
        base = DISPLAY_VIA_TASK
    elif item.meeting_id is not None:
        meeting = meeting_service.get_by_id(item.meeting_id)
        meeting_status = (meeting.status if meeting is not None else "") or ""
        if meeting_status == MEETING_CLOSED:
            return DISPLAY_DONE
        if meeting_status in {MEETING_PLANNED, MEETING_HELD}:
            base = DISPLAY_VIA_MEETING
        else:
            # Zrušená / neznámá Událost → nevyřízená, ne Splněno.
            base = DISPLAY_PLANNED
    elif (item.status or "") == STATUS_VIA_TASK:
        base = DISPLAY_VIA_TASK
    elif (item.status or "") == STATUS_VIA_MEETING:
        base = DISPLAY_VIA_MEETING

    if month_has_ended(item.year, item.month, today=today):
        return DISPLAY_REST
    return base


def summarize_display_statuses(statuses: list[str]) -> dict[str, int]:
    """Souhrn odvozených stavů pro měsíc."""
    summary = {
        "total": len(statuses),
        "done": 0,
        "in_progress": 0,
        "rest": 0,
        "cancelled": 0,
        "planned": 0,
    }
    for status in statuses:
        if status == DISPLAY_DONE:
            summary["done"] += 1
        elif status in {DISPLAY_VIA_TASK, DISPLAY_VIA_MEETING}:
            summary["in_progress"] += 1
        elif status == DISPLAY_REST:
            summary["rest"] += 1
        elif status == DISPLAY_CANCELLED:
            summary["cancelled"] += 1
        elif status == DISPLAY_PLANNED:
            summary["planned"] += 1
    return summary


def _manual_row(item: YearlyPlanItem, *, today: date) -> YearlyPlanRow:
    return YearlyPlanRow(
        kind=ROW_KIND_MANUAL,
        title=(item.title or "").strip() or f"Položka #{item.id}",
        note=(item.note or "").strip(),
        display_status=resolve_display_status(item, today=today),
        link_text=link_label(item),
        source_label=SOURCE_LABEL_MANUAL,
        plan_item_id=item.id,
    )


def _periodic_display_status(planned_due: date, *, has_occurrence: bool, today: date) -> str:
    if has_occurrence:
        return DISPLAY_DONE
    if month_has_ended(planned_due.year, planned_due.month, today=today):
        return DISPLAY_REST
    return DISPLAY_PLANNED


def list_periodic_rows_for_month(
    year: int,
    month: int,
    *,
    today: date | None = None,
) -> list[YearlyPlanRow]:
    """Projekce aktivních Periodických činností do měsíce (bez kopírování do DB)."""
    today = today or date.today()
    rows: list[YearlyPlanRow] = []
    seen: set[tuple[int, date]] = set()

    for activity in periodic_activity_service.get_all(active_only=True):
        title = (activity.title or "").strip() or f"Periodická činnost #{activity.id}"
        note = (activity.note or "").strip()

        for occurrence in periodic_activity_service.list_occurrences(activity.id):
            planned = occurrence.planned_due_date
            if planned is None:
                continue
            if planned.year != year or planned.month != month:
                continue
            key = (activity.id, planned)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                YearlyPlanRow(
                    kind=ROW_KIND_PERIODIC,
                    title=title,
                    note=note,
                    display_status=DISPLAY_DONE,
                    link_text="—",
                    source_label=SOURCE_LABEL_PERIODIC,
                    activity_id=activity.id,
                    planned_due_date=planned,
                    occurrence_id=occurrence.id,
                )
            )

        due = activity.next_due_date
        if due is None:
            continue

        candidate = due
        for _ in range(_MAX_PERIODIC_PROJECTIONS):
            if candidate.year > year:
                break
            if candidate.year == year and candidate.month == month:
                key = (activity.id, candidate)
                if key not in seen:
                    seen.add(key)
                    rows.append(
                        YearlyPlanRow(
                            kind=ROW_KIND_PERIODIC,
                            title=title,
                            note=note,
                            display_status=_periodic_display_status(
                                candidate,
                                has_occurrence=False,
                                today=today,
                            ),
                            link_text="—",
                            source_label=SOURCE_LABEL_PERIODIC,
                            activity_id=activity.id,
                            planned_due_date=candidate,
                        )
                    )
            try:
                nxt = add_period(
                    candidate,
                    activity.repeat_every,
                    activity.repeat_unit,
                )
            except Exception:
                break
            if nxt <= candidate:
                break
            candidate = nxt

    return rows


class YearlyPlanService:
    def __init__(self) -> None:
        self.repository = YearlyPlanItemRepository()
        self.move_repository = YearlyPlanItemMoveRepository()
        self.month_status_repository = YearlyPlanMonthStatusRepository()

    def get_by_id(self, item_id: int) -> YearlyPlanItem | None:
        return self.repository.get_by_id(item_id)

    def list_for_month(self, year: int, month: int) -> list[YearlyPlanItem]:
        self._validate_year_month(year, month)
        return self.repository.list_for_month(year, month)

    def list_for_year(self, year: int) -> list[YearlyPlanItem]:
        self._validate_year(year)
        return self.repository.list_for_year(year)

    def get_move_history(self, item_id: int) -> list[YearlyPlanItemMove]:
        return self.move_repository.list_for_item(item_id)

    def create(
        self,
        *,
        year: int,
        month: int,
        title: str,
        note: str = "",
        status: str = DEFAULT_STATUS,
        task_id: int | None = None,
        meeting_id: int | None = None,
    ) -> YearlyPlanItem:
        data = self._validated_fields(
            year=year,
            month=month,
            title=title,
            note=note,
            status=status,
            task_id=task_id,
            meeting_id=meeting_id,
        )
        item = YearlyPlanItem(**data)
        return self.repository.add(item)

    def update(
        self,
        item_id: int,
        *,
        year: int,
        month: int,
        title: str,
        note: str = "",
        status: str = DEFAULT_STATUS,
        task_id: int | None = None,
        meeting_id: int | None = None,
    ) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")

        data = self._validated_fields(
            year=year,
            month=month,
            title=title,
            note=note,
            status=status,
            task_id=task_id,
            meeting_id=meeting_id,
        )
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def cancel(self, item_id: int) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")
        item.status = STATUS_CANCELLED
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def move_to_month(
        self,
        item_id: int,
        *,
        to_year: int,
        to_month: int,
    ) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")

        self._validate_year_month(to_year, to_month)
        if item.year == to_year and item.month == to_month:
            raise YearlyPlanValidationError(
                "Položka už je v cílovém měsíci."
            )

        from_year = item.year
        from_month = item.month

        move = YearlyPlanItemMove(
            item_id=item.id,
            from_year=from_year,
            from_month=from_month,
            to_year=to_year,
            to_month=to_month,
            moved_at=datetime.now(),
        )
        self.move_repository.add(move)

        item.year = to_year
        item.month = to_month
        if item.task_id is not None:
            item.status = STATUS_VIA_TASK
        elif item.meeting_id is not None:
            item.status = STATUS_VIA_MEETING
        else:
            item.status = STATUS_PLANNED
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def link_task(self, item_id: int, task_id: int) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")
        if item.status == STATUS_CANCELLED:
            raise YearlyPlanValidationError("Zrušenou položku nelze navázat na Úkol.")
        if item.task_id is not None or item.meeting_id is not None:
            raise YearlyPlanValidationError(
                "Položka už má vazbu na Úkol nebo Událost."
            )
        if not task_id:
            raise YearlyPlanValidationError("Úkol nebyl vytvořen.")

        item.task_id = int(task_id)
        item.meeting_id = None
        item.status = STATUS_VIA_TASK
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def link_meeting(self, item_id: int, meeting_id: int) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")
        if item.status == STATUS_CANCELLED:
            raise YearlyPlanValidationError("Zrušenou položku nelze navázat na Událost.")
        if item.task_id is not None or item.meeting_id is not None:
            raise YearlyPlanValidationError(
                "Položka už má vazbu na Úkol nebo Událost."
            )
        if not meeting_id:
            raise YearlyPlanValidationError("Událost nebyla vytvořena.")

        item.meeting_id = int(meeting_id)
        item.task_id = None
        item.status = STATUS_VIA_MEETING
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def _validate_year(self, year: int) -> None:
        if not isinstance(year, int) or isinstance(year, bool):
            raise YearlyPlanValidationError("Rok musí být celé číslo.")
        if year < MIN_YEAR or year > MAX_YEAR:
            raise YearlyPlanValidationError(
                f"Rok musí být v rozmezí {MIN_YEAR}–{MAX_YEAR}."
            )

    def _validate_month(self, month: int) -> None:
        if not isinstance(month, int) or isinstance(month, bool):
            raise YearlyPlanValidationError("Měsíc musí být celé číslo.")
        if month < 1 or month > 12:
            raise YearlyPlanValidationError("Měsíc musí být v rozmezí 1–12.")

    def _validate_year_month(self, year: int, month: int) -> None:
        self._validate_year(year)
        self._validate_month(month)

    def _validated_fields(
        self,
        *,
        year: int,
        month: int,
        title: str,
        note: str,
        status: str,
        task_id: int | None,
        meeting_id: int | None,
    ) -> dict:
        self._validate_year_month(year, month)

        clean_title = (title or "").strip()
        if not clean_title:
            raise YearlyPlanValidationError("Název nesmí být prázdný.")

        if status not in ITEM_STATUSES:
            raise YearlyPlanValidationError(
                f"status musí být jeden z: {', '.join(ITEM_STATUSES)}."
            )

        if task_id is not None and meeting_id is not None:
            raise YearlyPlanValidationError(
                "Položka nesmí současně odkazovat na Úkol i Událost."
            )

        return {
            "year": int(year),
            "month": int(month),
            "title": clean_title,
            "note": (note or "").strip(),
            "status": status,
            "task_id": task_id,
            "meeting_id": meeting_id,
        }

    def resolve_display_status(
        self,
        item: YearlyPlanItem,
        *,
        today: date | None = None,
    ) -> str:
        return resolve_display_status(item, today=today)

    def list_month_rows(
        self,
        year: int,
        month: int,
        *,
        today: date | None = None,
    ) -> list[YearlyPlanRow]:
        """Ruční položky + Periodické činnosti pro měsíc."""
        today = today or date.today()
        self._validate_year_month(year, month)
        manual = [
            _manual_row(item, today=today)
            for item in self.list_for_month(year, month)
        ]
        periodic = list_periodic_rows_for_month(year, month, today=today)
        rows = manual + periodic
        rows.sort(
            key=lambda row: (
                (row.title or "").casefold(),
                0 if row.is_manual else 1,
                row.plan_item_id or 0,
                row.activity_id or 0,
                row.planned_due_date or date.min,
            )
        )
        return rows

    def month_summary(
        self,
        items: list[YearlyPlanItem] | list[YearlyPlanRow],
        *,
        today: date | None = None,
    ) -> dict[str, int]:
        today = today or date.today()
        statuses: list[str] = []
        for item in items:
            if isinstance(item, YearlyPlanRow):
                statuses.append(item.display_status)
            else:
                statuses.append(resolve_display_status(item, today=today))
        return summarize_display_statuses(statuses)

    def get_month_status(self, year: int, month: int) -> YearlyPlanMonthStatus | None:
        self._validate_year_month(year, month)
        return self.month_status_repository.get_for_month(year, month)

    def is_month_processed(self, year: int, month: int) -> bool:
        return self.get_month_status(year, month) is not None

    def mark_month_processed(
        self,
        year: int,
        month: int,
        *,
        processed_at: datetime | None = None,
    ) -> YearlyPlanMonthStatus:
        """Označí měsíc jako zpracovaný. Nemění stavy položek."""
        self._validate_year_month(year, month)
        existing = self.month_status_repository.get_for_month(year, month)
        if existing is not None:
            raise YearlyPlanValidationError(MONTH_ALREADY_PROCESSED_MESSAGE)
        status = YearlyPlanMonthStatus(
            year=year,
            month=month,
            processed_at=processed_at or datetime.now(),
        )
        return self.month_status_repository.add(status)

    def should_show_month_planning_attention(
        self,
        *,
        today: date | None = None,
    ) -> bool:
        """
        True od prvního pracovního dne aktuálního měsíce,
        dokud měsíc není označen jako zpracovaný.
        """
        today = today or date.today()
        if today < first_working_day(today.year, today.month):
            return False
        return not self.is_month_processed(today.year, today.month)


yearly_plan_service = YearlyPlanService()
