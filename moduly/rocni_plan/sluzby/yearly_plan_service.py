"""Služba Ročního plánu – CRUD, zrušení, přesun, validace."""

from __future__ import annotations

from datetime import datetime

from moduly.rocni_plan.constants import (
    DEFAULT_STATUS,
    ITEM_STATUSES,
    MAX_YEAR,
    MIN_YEAR,
    STATUS_CANCELLED,
    STATUS_PLANNED,
)
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove
from moduly.rocni_plan.repository.yearly_plan_repository import (
    YearlyPlanItemMoveRepository,
    YearlyPlanItemRepository,
)


class YearlyPlanValidationError(ValueError):
    """Neplatná data položky Ročního plánu."""


class YearlyPlanService:
    def __init__(self) -> None:
        self.repository = YearlyPlanItemRepository()
        self.move_repository = YearlyPlanItemMoveRepository()

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
        item.status = STATUS_PLANNED
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


yearly_plan_service = YearlyPlanService()
