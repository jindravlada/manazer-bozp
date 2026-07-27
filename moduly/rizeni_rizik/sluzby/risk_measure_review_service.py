from __future__ import annotations

from datetime import date, datetime

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
)
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUSES,
)
from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
from moduly.rizeni_rizik.repository.risk_measure_review_repository import (
    RiskMeasureReviewRepository,
)


class RiskMeasureReviewError(ValueError):
    pass


class RiskMeasureReviewService:
    def __init__(self) -> None:
        self.repository = RiskMeasureReviewRepository()

    def get_all(self, *, include_archived: bool = True) -> list[RiskMeasureReview]:
        return self.repository.get_all(include_archived=include_archived)

    def get_by_id(self, review_id: int | None) -> RiskMeasureReview | None:
        if not review_id:
            return None
        return self.repository.get_by_id(review_id)

    def preview_next_number(self) -> str:
        return self.repository.allocate_next_number()

    def get_active_operations(self, *, include_inactive: bool = False) -> list:
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        operations = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_OPERATION
        ]
        return czech_sorted(operations, key=lambda item: item.name)

    def get_workplaces_for_operation(
        self,
        operation_id: int | None,
        *,
        include_inactive: bool = False,
    ) -> list:
        if not operation_id:
            return []
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        items = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE
            and workplace.parent_id == operation_id
        ]
        return czech_sorted(items, key=lambda item: item.name)

    def get_workplace_parts_for_workplace(
        self,
        workplace_id: int | None,
        *,
        include_inactive: bool = False,
    ) -> list:
        if not workplace_id:
            return []
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        items = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART
            and workplace.parent_id == workplace_id
        ]
        return czech_sorted(items, key=lambda item: item.name)

    def create_review(
        self,
        *,
        review_date: date,
        reviewer_person_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        status: str = RISK_MEASURE_REVIEW_STATUS_DRAFT,
        note: str = "",
    ) -> RiskMeasureReview:
        resolved = self._validate_and_resolve(
            review_date=review_date,
            reviewer_person_id=reviewer_person_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            status=status,
        )
        review = RiskMeasureReview(
            review_number=self.repository.allocate_next_number(review_date.year),
            review_date=review_date,
            note=note.strip(),
            archived_at=None,
            **resolved,
        )
        return self.repository.add(review)

    def update_review(
        self,
        review_id: int,
        *,
        review_date: date,
        reviewer_person_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        status: str = RISK_MEASURE_REVIEW_STATUS_DRAFT,
        note: str = "",
    ) -> RiskMeasureReview | None:
        review = self.repository.get_by_id(review_id)
        if review is None:
            return None
        if review.archived_at is not None and status != RISK_MEASURE_REVIEW_STATUS_ARCHIVED:
            # Obnova ze stavu archivace přes změnu stavu v editoru.
            review.archived_at = None
        resolved = self._validate_and_resolve(
            review_date=review_date,
            reviewer_person_id=reviewer_person_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            status=status,
        )
        review.review_date = review_date
        review.note = note.strip()
        for key, value in resolved.items():
            setattr(review, key, value)
        review.updated_at = datetime.now()
        return self.repository.update(review)

    def archive(self, review_id: int) -> bool:
        review = self.repository.get_by_id(review_id)
        if review is None:
            return False
        if review.archived_at is not None:
            return True
        review.status = RISK_MEASURE_REVIEW_STATUS_ARCHIVED
        review.archived_at = datetime.now()
        review.updated_at = datetime.now()
        self.repository.update(review)
        return True

    def restore(self, review_id: int) -> bool:
        review = self.repository.get_by_id(review_id)
        if review is None:
            return False
        if review.archived_at is None:
            return True
        review.archived_at = None
        review.status = RISK_MEASURE_REVIEW_STATUS_DRAFT
        review.updated_at = datetime.now()
        self.repository.update(review)
        return True

    def _validate_and_resolve(
        self,
        *,
        review_date: date,
        reviewer_person_id: int,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
        status: str,
    ) -> dict:
        if review_date is None:
            raise RiskMeasureReviewError("Datum přezkoumání je povinné.")
        if not reviewer_person_id:
            raise RiskMeasureReviewError("Vyberte kontrolující osobu.")
        person = person_service.get_by_id(reviewer_person_id)
        if person is None:
            raise RiskMeasureReviewError("Kontrolující osoba neexistuje.")

        if not operation_id:
            raise RiskMeasureReviewError("Vyberte provoz.")
        operation = settings_service.get_workplace_by_id(operation_id)
        if operation is None or operation.item_type != WORKPLACE_ITEM_TYPE_OPERATION:
            raise RiskMeasureReviewError("Vybraný provoz neexistuje.")

        workplace_name = ""
        workplace_part_name = ""
        resolved_workplace_id: int | None = None
        resolved_part_id: int | None = None

        if workplace_id:
            workplace = settings_service.get_workplace_by_id(workplace_id)
            if workplace is None or workplace.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE:
                raise RiskMeasureReviewError("Vybrané pracoviště neexistuje.")
            if workplace.parent_id != operation_id:
                raise RiskMeasureReviewError(
                    "Pracoviště musí patřit do zvoleného provozu."
                )
            resolved_workplace_id = workplace.id
            workplace_name = workplace.name or ""

            if workplace_part_id:
                part = settings_service.get_workplace_by_id(workplace_part_id)
                if part is None or part.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE_PART:
                    raise RiskMeasureReviewError("Vybraná část pracoviště neexistuje.")
                if part.parent_id != workplace_id:
                    raise RiskMeasureReviewError(
                        "Část pracoviště musí patřit do zvoleného pracoviště."
                    )
                resolved_part_id = part.id
                workplace_part_name = part.name or ""
        elif workplace_part_id:
            raise RiskMeasureReviewError(
                "Část pracoviště lze vybrat až po zvolení pracoviště."
            )

        editor_statuses = set(RISK_MEASURE_REVIEW_STATUSES) | {
            RISK_MEASURE_REVIEW_STATUS_ARCHIVED
        }
        if status not in editor_statuses:
            raise RiskMeasureReviewError("Neplatný stav přezkoumání.")
        if status == RISK_MEASURE_REVIEW_STATUS_COMPLETED and not isinstance(
            review_date, date
        ):
            raise RiskMeasureReviewError("Datum přezkoumání je povinné.")

        return {
            "reviewer_person_id": int(reviewer_person_id),
            "reviewer_person_name": person_service.display_name(reviewer_person_id),
            "operation_id": int(operation_id),
            "operation_name": operation.name or "",
            "workplace_id": resolved_workplace_id,
            "workplace_name": workplace_name,
            "workplace_part_id": resolved_part_id,
            "workplace_part_name": workplace_part_name,
            "status": status,
        }


risk_measure_review_service = RiskMeasureReviewService()
