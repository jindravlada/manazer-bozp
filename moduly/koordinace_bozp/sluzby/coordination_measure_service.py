"""Služba organizačních opatření koordinace (COORD-009)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.constants import (
    DEFAULT_MEASURE_CATEGORY,
    MEASURE_CATEGORIES,
    MEASURE_CATEGORY_LABELS,
)
from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
from moduly.koordinace_bozp.repository.coordination_measure_repository import (
    CoordinationMeasureRepository,
)


class CoordinationMeasureError(ValueError):
    pass


def normalize_measure_title(value: str) -> str:
    return " ".join((value or "").strip().split())


class CoordinationMeasureService:
    def __init__(self) -> None:
        self.repository = CoordinationMeasureRepository()

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationMeasure]:
        return self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, measure_id: int | None) -> CoordinationMeasure | None:
        if not measure_id:
            return None
        return self.repository.get_by_id(measure_id)

    def category_label(self, category: str) -> str:
        return MEASURE_CATEGORY_LABELS.get(category, category or "")

    def add(
        self,
        coordination_id: int,
        *,
        title: str,
        description: str = "",
        category: str = DEFAULT_MEASURE_CATEGORY,
        active: bool = True,
    ) -> CoordinationMeasure:
        if not coordination_id:
            raise CoordinationMeasureError("Koordinace je povinná.")
        normalized_title = self._validate_title(title)
        normalized_category = self._validate_category(category)
        measure = CoordinationMeasure(
            coordination_id=coordination_id,
            title=normalized_title,
            description=(description or "").strip(),
            category=normalized_category,
            active=active,
            sort_order=self.repository.next_sort_order(coordination_id),
        )
        return self.repository.add(measure)

    def update(
        self,
        measure_id: int,
        *,
        title: str,
        description: str = "",
        category: str = DEFAULT_MEASURE_CATEGORY,
    ) -> CoordinationMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None
        measure.title = self._validate_title(title)
        measure.description = (description or "").strip()
        measure.category = self._validate_category(category)
        measure.updated_at = datetime.now()
        return self.repository.update(measure)

    def activate(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        measure.active = True
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        return True

    def deactivate(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        measure.active = False
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        return True

    def move_up(self, measure_id: int) -> bool:
        return self._move(measure_id, direction=-1)

    def move_down(self, measure_id: int) -> bool:
        return self._move(measure_id, direction=1)

    def _move(self, measure_id: int, *, direction: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        items = self.repository.list_for_coordination(
            measure.coordination_id,
            include_inactive=True,
        )
        index = next((i for i, item in enumerate(items) if item.id == measure.id), None)
        if index is None:
            return False
        new_index = index + direction
        if new_index < 0 or new_index >= len(items):
            return False

        items[index], items[new_index] = items[new_index], items[index]
        for order, item in enumerate(items, start=1):
            if item.sort_order == order:
                continue
            item.sort_order = order
            item.updated_at = datetime.now()
            self.repository.update(item)
        return True

    def _validate_title(self, title: str) -> str:
        normalized = normalize_measure_title(title)
        if not normalized:
            raise CoordinationMeasureError("Název opatření je povinný.")
        return normalized

    def _validate_category(self, category: str) -> str:
        normalized = (category or "").strip()
        if normalized not in MEASURE_CATEGORIES:
            raise CoordinationMeasureError("Neplatná kategorie opatření.")
        return normalized


coordination_measure_service = CoordinationMeasureService()
