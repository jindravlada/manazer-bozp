"""Služba Ročního plánu – CRUD, opakování, výjimky výskytů, odvozené stavy."""

from __future__ import annotations

import calendar
from datetime import date, datetime

from core.shared.working_days import first_working_day
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    add_period,
    periodic_activity_service,
)
from moduly.rocni_plan.constants import (
    DEFAULT_DUE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
    DEFAULT_STATUS,
    DISPLAY_CANCELLED,
    DISPLAY_DONE,
    DISPLAY_PLANNED,
    DISPLAY_REST,
    DISPLAY_VIA_MEETING,
    DISPLAY_VIA_TASK,
    DUE_KIND_DAY,
    DUE_KIND_FIRST_WORKING_DAY,
    DUE_KIND_NONE,
    DUE_KINDS,
    ITEM_STATUSES,
    MAX_YEAR,
    MIN_YEAR,
    MONTH_ALREADY_PROCESSED_MESSAGE,
    REPEAT_UNIT_MONTHS,
    REPEAT_UNIT_NONE,
    REPEAT_UNIT_YEARS,
    REPEAT_UNITS,
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
    SOURCE_LABEL_MANUAL,
    SOURCE_LABEL_PERIODIC,
    STATUS_CANCELLED,
    STATUS_PLANNED,
    STATUS_VIA_MEETING,
    STATUS_VIA_TASK,
    YEAR_COMBO_FUTURE_YEARS,
    YEAR_COMBO_PAST_YEARS,
)
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove
from moduly.rocni_plan.modely.yearly_plan_month_status import YearlyPlanMonthStatus
from moduly.rocni_plan.modely.yearly_plan_occurrence import YearlyPlanOccurrence
from moduly.rocni_plan.modely.yearly_plan_row import YearlyPlanRow
from moduly.rocni_plan.repository.yearly_plan_repository import (
    YearlyPlanItemMoveRepository,
    YearlyPlanItemRepository,
    YearlyPlanMonthStatusRepository,
    YearlyPlanOccurrenceRepository,
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


def is_repeating(item: YearlyPlanItem) -> bool:
    every = int(getattr(item, "repeat_every", 0) or 0)
    unit = (getattr(item, "repeat_unit", None) or REPEAT_UNIT_NONE).strip()
    return every > 0 and unit in {REPEAT_UNIT_MONTHS, REPEAT_UNIT_YEARS}


def definition_occurs_in_month(item: YearlyPlanItem, year: int, month: int) -> bool:
    """True, pokud slot opakování (bez výjimek) připadá do year/month."""
    if not is_repeating(item):
        return item.year == year and item.month == month

    start_index = item.year * 12 + (item.month - 1)
    target_index = year * 12 + (month - 1)
    if target_index < start_index:
        return False

    every = int(item.repeat_every)
    unit = item.repeat_unit
    if unit == REPEAT_UNIT_MONTHS:
        return (target_index - start_index) % every == 0
    if unit == REPEAT_UNIT_YEARS:
        if month != item.month:
            return False
        return (year - item.year) % every == 0
    return False


def resolve_planned_due_date(item: YearlyPlanItem, year: int, month: int) -> date | None:
    kind = (getattr(item, "due_kind", None) or DUE_KIND_NONE).strip()
    if kind == DUE_KIND_NONE:
        return None
    if kind == DUE_KIND_FIRST_WORKING_DAY:
        return first_working_day(year, month)
    if kind == DUE_KIND_DAY:
        day = int(getattr(item, "due_day", None) or 0)
        if day < 1:
            return None
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last_day))
    return None


def resolve_display_status_fields(
    *,
    status: str,
    task_id: int | None,
    meeting_id: int | None,
    year: int,
    month: int,
    today: date | None = None,
) -> str:
    today = today or date.today()

    if (status or "") == STATUS_CANCELLED:
        return DISPLAY_CANCELLED

    base = DISPLAY_PLANNED

    if task_id is not None:
        task = task_service.get_task_by_id(task_id)
        if task is not None and task.computed_status == "Ukončeno":
            return DISPLAY_DONE
        base = DISPLAY_VIA_TASK
    elif meeting_id is not None:
        meeting = meeting_service.get_by_id(meeting_id)
        meeting_status = (meeting.status if meeting is not None else "") or ""
        if meeting_status == MEETING_CLOSED:
            return DISPLAY_DONE
        if meeting_status in {MEETING_PLANNED, MEETING_HELD}:
            base = DISPLAY_VIA_MEETING
        else:
            base = DISPLAY_PLANNED
    elif (status or "") == STATUS_VIA_TASK:
        base = DISPLAY_VIA_TASK
    elif (status or "") == STATUS_VIA_MEETING:
        base = DISPLAY_VIA_MEETING

    if month_has_ended(year, month, today=today):
        return DISPLAY_REST
    return base


def resolve_display_status(item: YearlyPlanItem, *, today: date | None = None) -> str:
    """Odvozený stav pro jednorázovou položku."""
    return resolve_display_status_fields(
        status=item.status or "",
        task_id=item.task_id,
        meeting_id=item.meeting_id,
        year=item.year,
        month=item.month,
        today=today,
    )


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


def _link_text(task_id: int | None, meeting_id: int | None) -> str:
    if task_id is not None:
        return f"Úkol #{task_id}"
    if meeting_id is not None:
        return f"Událost #{meeting_id}"
    return "—"


def _manual_row_from_fields(
    *,
    item: YearlyPlanItem,
    year: int,
    month: int,
    status: str,
    task_id: int | None,
    meeting_id: int | None,
    today: date,
    slot_year: int | None = None,
    slot_month: int | None = None,
    is_recurring: bool = False,
    occurrence_id: int | None = None,
) -> YearlyPlanRow:
    return YearlyPlanRow(
        kind=ROW_KIND_MANUAL,
        title=(item.title or "").strip() or f"Položka #{item.id}",
        note=(item.note or "").strip(),
        display_status=resolve_display_status_fields(
            status=status,
            task_id=task_id,
            meeting_id=meeting_id,
            year=year,
            month=month,
            today=today,
        ),
        link_text=_link_text(task_id, meeting_id),
        source_label=SOURCE_LABEL_MANUAL,
        plan_item_id=item.id,
        planned_due_date=resolve_planned_due_date(item, year, month),
        occurrence_id=occurrence_id,
        slot_year=slot_year if slot_year is not None else year,
        slot_month=slot_month if slot_month is not None else month,
        is_recurring=is_recurring,
    )


def _manual_row(item: YearlyPlanItem, *, today: date) -> YearlyPlanRow:
    return _manual_row_from_fields(
        item=item,
        year=item.year,
        month=item.month,
        status=item.status or DEFAULT_STATUS,
        task_id=item.task_id,
        meeting_id=item.meeting_id,
        today=today,
        is_recurring=False,
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
        self.occurrence_repository = YearlyPlanOccurrenceRepository()

    def get_by_id(self, item_id: int) -> YearlyPlanItem | None:
        return self.repository.get_by_id(item_id)

    def list_for_month(self, year: int, month: int) -> list[YearlyPlanItem]:
        self._validate_year_month(year, month)
        return self.repository.list_for_month(year, month)

    def list_for_year(self, year: int) -> list[YearlyPlanItem]:
        self._validate_year(year)
        return self.repository.list_for_year(year)

    def list_used_years(self) -> list[int]:
        return self.repository.list_used_years()

    def years_for_year_combo(self, *, today: date | None = None) -> list[int]:
        """Roky pro combo Agendy: aktuální −5 … +10 plus skutečně použité roky."""
        today = today or date.today()
        years = set(
            range(
                today.year - YEAR_COMBO_PAST_YEARS,
                today.year + YEAR_COMBO_FUTURE_YEARS + 1,
            )
        )
        years.update(self.list_used_years())
        return sorted(year for year in years if MIN_YEAR <= year <= MAX_YEAR)

    def get_move_history(self, item_id: int) -> list[YearlyPlanItemMove]:
        return self.move_repository.list_for_item(item_id)

    def get_occurrence(
        self,
        definition_id: int,
        year: int,
        month: int,
    ) -> YearlyPlanOccurrence | None:
        return self.occurrence_repository.get_slot(definition_id, year, month)

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
        repeat_every: int = DEFAULT_REPEAT_EVERY,
        repeat_unit: str = DEFAULT_REPEAT_UNIT,
        due_kind: str = DEFAULT_DUE_KIND,
        due_day: int | None = None,
    ) -> YearlyPlanItem:
        data = self._validated_fields(
            year=year,
            month=month,
            title=title,
            note=note,
            status=status,
            task_id=task_id,
            meeting_id=meeting_id,
            repeat_every=repeat_every,
            repeat_unit=repeat_unit,
            due_kind=due_kind,
            due_day=due_day,
        )
        if data["repeat_every"] > 0 and data["repeat_unit"] != REPEAT_UNIT_NONE:
            # Vazby patří na výskyty, ne na definici řady.
            data["task_id"] = None
            data["meeting_id"] = None
            data["status"] = DEFAULT_STATUS
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
        repeat_every: int | None = None,
        repeat_unit: str | None = None,
        due_kind: str | None = None,
        due_day: int | None = None,
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
            task_id=task_id if task_id is not None else item.task_id,
            meeting_id=meeting_id if meeting_id is not None else item.meeting_id,
            repeat_every=(
                item.repeat_every if repeat_every is None else repeat_every
            ),
            repeat_unit=(
                item.repeat_unit if repeat_unit is None else repeat_unit
            ),
            due_kind=item.due_kind if due_kind is None else due_kind,
            due_day=(
                item.due_day
                if due_kind is None and due_day is None
                else due_day
            ),
        )
        becoming_repeating = (
            data["repeat_every"] > 0 and data["repeat_unit"] != REPEAT_UNIT_NONE
        )
        if becoming_repeating and (data["task_id"] or data["meeting_id"]):
            self._ensure_occurrence(
                item.id,
                year=data["year"],
                month=data["month"],
                status=data["status"],
                task_id=data["task_id"],
                meeting_id=data["meeting_id"],
            )
            data["task_id"] = None
            data["meeting_id"] = None
            data["status"] = DEFAULT_STATUS

        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def cancel(self, item_id: int) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")
        if is_repeating(item):
            raise YearlyPlanValidationError(
                "Opakovanou řadu nelze zrušit najednou. Zrušte jednotlivý výskyt."
            )
        item.status = STATUS_CANCELLED
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def cancel_occurrence(
        self,
        definition_id: int,
        *,
        year: int,
        month: int,
    ) -> YearlyPlanOccurrence:
        item = self.repository.get_by_id(definition_id)
        if item is None or not is_repeating(item):
            raise YearlyPlanValidationError("Opakovaná položka nebyla nalezena.")
        self._validate_year_month(year, month)
        if not definition_occurs_in_month(item, year, month):
            raise YearlyPlanValidationError("Výskyt nepatří do této opakované řady.")
        return self._ensure_occurrence(
            definition_id,
            year=year,
            month=month,
            status=STATUS_CANCELLED,
            keep_links=True,
        )

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
        if is_repeating(item):
            raise YearlyPlanValidationError(
                "Opakovanou řadu nelze přesunout najednou. Přesuňte jednotlivý výskyt."
            )

        self._validate_year_month(to_year, to_month)
        if item.year == to_year and item.month == to_month:
            raise YearlyPlanValidationError("Položka už je v cílovém měsíci.")

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

    def move_occurrence(
        self,
        definition_id: int,
        *,
        year: int,
        month: int,
        to_year: int,
        to_month: int,
    ) -> YearlyPlanOccurrence:
        item = self.repository.get_by_id(definition_id)
        if item is None or not is_repeating(item):
            raise YearlyPlanValidationError("Opakovaná položka nebyla nalezena.")
        self._validate_year_month(year, month)
        self._validate_year_month(to_year, to_month)
        if year == to_year and month == to_month:
            raise YearlyPlanValidationError("Položka už je v cílovém měsíci.")
        if not definition_occurs_in_month(item, year, month):
            existing = self.occurrence_repository.get_slot(definition_id, year, month)
            if existing is None:
                raise YearlyPlanValidationError("Výskyt nepatří do této opakované řady.")

        occurrence = self._ensure_occurrence(definition_id, year=year, month=month)
        if occurrence.status == STATUS_CANCELLED:
            raise YearlyPlanValidationError("Zrušený výskyt nelze přesunout.")

        from_year = occurrence.display_year
        from_month = occurrence.display_month
        if from_year == to_year and from_month == to_month:
            raise YearlyPlanValidationError("Položka už je v cílovém měsíci.")

        self.move_repository.add(
            YearlyPlanItemMove(
                item_id=definition_id,
                from_year=from_year,
                from_month=from_month,
                to_year=to_year,
                to_month=to_month,
                moved_at=datetime.now(),
            )
        )
        occurrence.display_year = to_year
        occurrence.display_month = to_month
        occurrence.updated_at = datetime.now()
        return self.occurrence_repository.update(occurrence)

    def link_task(self, item_id: int, task_id: int) -> YearlyPlanItem:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise YearlyPlanValidationError("Položka Ročního plánu nebyla nalezena.")
        if is_repeating(item):
            raise YearlyPlanValidationError(
                "Úkol navazujte na konkrétní výskyt opakované položky."
            )
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
        if is_repeating(item):
            raise YearlyPlanValidationError(
                "Událost navazujte na konkrétní výskyt opakované položky."
            )
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

    def link_task_occurrence(
        self,
        definition_id: int,
        *,
        year: int,
        month: int,
        task_id: int,
    ) -> YearlyPlanOccurrence:
        item = self.repository.get_by_id(definition_id)
        if item is None or not is_repeating(item):
            raise YearlyPlanValidationError("Opakovaná položka nebyla nalezena.")
        if not task_id:
            raise YearlyPlanValidationError("Úkol nebyl vytvořen.")
        occurrence = self._occurrence_for_action(item, year, month)
        if occurrence.task_id is not None or occurrence.meeting_id is not None:
            raise YearlyPlanValidationError(
                "Položka už má vazbu na Úkol nebo Událost."
            )
        occurrence.task_id = int(task_id)
        occurrence.meeting_id = None
        occurrence.status = STATUS_VIA_TASK
        occurrence.updated_at = datetime.now()
        return self.occurrence_repository.update(occurrence)

    def link_meeting_occurrence(
        self,
        definition_id: int,
        *,
        year: int,
        month: int,
        meeting_id: int,
    ) -> YearlyPlanOccurrence:
        item = self.repository.get_by_id(definition_id)
        if item is None or not is_repeating(item):
            raise YearlyPlanValidationError("Opakovaná položka nebyla nalezena.")
        if not meeting_id:
            raise YearlyPlanValidationError("Událost nebyla vytvořena.")
        occurrence = self._occurrence_for_action(item, year, month)
        if occurrence.task_id is not None or occurrence.meeting_id is not None:
            raise YearlyPlanValidationError(
                "Položka už má vazbu na Úkol nebo Událost."
            )
        occurrence.meeting_id = int(meeting_id)
        occurrence.task_id = None
        occurrence.status = STATUS_VIA_MEETING
        occurrence.updated_at = datetime.now()
        return self.occurrence_repository.update(occurrence)

    def _occurrence_for_action(
        self,
        item: YearlyPlanItem,
        year: int,
        month: int,
    ) -> YearlyPlanOccurrence:
        self._validate_year_month(year, month)
        occurrence = self.occurrence_repository.get_slot(item.id, year, month)
        if occurrence is None:
            if not definition_occurs_in_month(item, year, month):
                raise YearlyPlanValidationError("Výskyt nepatří do této opakované řady.")
            occurrence = self._ensure_occurrence(item.id, year=year, month=month)
        if occurrence.status == STATUS_CANCELLED:
            raise YearlyPlanValidationError("Zrušenou položku nelze upravit touto akcí.")
        return occurrence

    def _ensure_occurrence(
        self,
        definition_id: int,
        *,
        year: int,
        month: int,
        status: str | None = None,
        task_id: int | None = None,
        meeting_id: int | None = None,
        keep_links: bool = False,
    ) -> YearlyPlanOccurrence:
        existing = self.occurrence_repository.get_slot(definition_id, year, month)
        if existing is None:
            return self.occurrence_repository.add(
                YearlyPlanOccurrence(
                    definition_id=definition_id,
                    year=year,
                    month=month,
                    display_year=year,
                    display_month=month,
                    status=status or DEFAULT_STATUS,
                    task_id=None if keep_links and status == STATUS_CANCELLED else task_id,
                    meeting_id=(
                        None if keep_links and status == STATUS_CANCELLED else meeting_id
                    ),
                )
            )
        if status is not None:
            existing.status = status
        if not keep_links and (task_id is not None or meeting_id is not None):
            existing.task_id = task_id
            existing.meeting_id = meeting_id
        existing.updated_at = datetime.now()
        return self.occurrence_repository.update(existing)

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
        repeat_every: int,
        repeat_unit: str,
        due_kind: str,
        due_day: int | None,
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

        every = int(repeat_every or 0)
        unit = (repeat_unit or REPEAT_UNIT_NONE).strip()
        if unit not in REPEAT_UNITS:
            raise YearlyPlanValidationError(
                f"repeat_unit musí být jeden z: {', '.join(REPEAT_UNITS)}."
            )
        if unit == REPEAT_UNIT_NONE:
            every = 0
        elif every <= 0:
            raise YearlyPlanValidationError("Počet opakování musí být větší než 0.")

        kind = (due_kind or DEFAULT_DUE_KIND).strip()
        if kind not in DUE_KINDS:
            raise YearlyPlanValidationError(
                f"due_kind musí být jeden z: {', '.join(DUE_KINDS)}."
            )
        resolved_day: int | None = None
        if kind == DUE_KIND_DAY:
            if due_day is None or int(due_day) < 1 or int(due_day) > 31:
                raise YearlyPlanValidationError("Zadejte den v měsíci (1–31).")
            resolved_day = int(due_day)
        elif kind == DUE_KIND_NONE:
            resolved_day = None
        else:
            resolved_day = None

        return {
            "year": int(year),
            "month": int(month),
            "title": clean_title,
            "note": (note or "").strip(),
            "status": status,
            "task_id": task_id,
            "meeting_id": meeting_id,
            "repeat_every": every,
            "repeat_unit": unit,
            "due_kind": kind,
            "due_day": resolved_day,
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
        """Jednorázové + opakované ruční položky + Periodické činnosti."""
        today = today or date.today()
        self._validate_year_month(year, month)

        rows: list[YearlyPlanRow] = []
        seen_slots: set[tuple[int, int, int]] = set()

        for item in self.repository.list_oneshots_for_month(year, month):
            rows.append(_manual_row(item, today=today))
            seen_slots.add((item.id, year, month))

        definitions = {item.id: item for item in self.repository.list_repeating()}

        for item in definitions.values():
            if not definition_occurs_in_month(item, year, month):
                continue
            occurrence = self.occurrence_repository.get_slot(item.id, year, month)
            if occurrence is not None and (
                occurrence.display_year != year or occurrence.display_month != month
            ):
                # Přesunuto pryč – v původním měsíci se nezobrazuje.
                continue
            if occurrence is None:
                rows.append(
                    _manual_row_from_fields(
                        item=item,
                        year=year,
                        month=month,
                        status=DEFAULT_STATUS,
                        task_id=None,
                        meeting_id=None,
                        today=today,
                        slot_year=year,
                        slot_month=month,
                        is_recurring=True,
                    )
                )
            else:
                rows.append(
                    _manual_row_from_fields(
                        item=item,
                        year=occurrence.display_year,
                        month=occurrence.display_month,
                        status=occurrence.status or DEFAULT_STATUS,
                        task_id=occurrence.task_id,
                        meeting_id=occurrence.meeting_id,
                        today=today,
                        slot_year=occurrence.year,
                        slot_month=occurrence.month,
                        is_recurring=True,
                        occurrence_id=occurrence.id,
                    )
                )
            seen_slots.add((item.id, year, month))

        for occurrence in self.occurrence_repository.list_displayed_in_month(year, month):
            slot_key = (occurrence.definition_id, occurrence.year, occurrence.month)
            if slot_key in seen_slots:
                continue
            if occurrence.year == year and occurrence.month == month:
                continue
            item = definitions.get(occurrence.definition_id) or self.repository.get_by_id(
                occurrence.definition_id
            )
            if item is None or not is_repeating(item):
                continue
            rows.append(
                _manual_row_from_fields(
                    item=item,
                    year=occurrence.display_year,
                    month=occurrence.display_month,
                    status=occurrence.status or DEFAULT_STATUS,
                    task_id=occurrence.task_id,
                    meeting_id=occurrence.meeting_id,
                    today=today,
                    slot_year=occurrence.year,
                    slot_month=occurrence.month,
                    is_recurring=True,
                    occurrence_id=occurrence.id,
                )
            )
            seen_slots.add(slot_key)

        periodic = list_periodic_rows_for_month(year, month, today=today)
        rows.extend(periodic)
        rows.sort(
            key=lambda row: (
                (row.title or "").casefold(),
                0 if row.is_manual else 1,
                row.plan_item_id or 0,
                row.slot_year or 0,
                row.slot_month or 0,
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
        today = today or date.today()
        if today < first_working_day(today.year, today.month):
            return False
        return not self.is_month_processed(today.year, today.month)


yearly_plan_service = YearlyPlanService()
