from __future__ import annotations

from dataclasses import dataclass
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
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    RISK_MEASURE_REVIEW_ITEM_RESULTS,
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUSES,
)
from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
from moduly.rizeni_rizik.repository.risk_measure_review_item_repository import (
    RiskMeasureReviewItemRepository,
)
from moduly.rizeni_rizik.repository.risk_measure_review_repository import (
    RiskMeasureReviewRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)


class RiskMeasureReviewError(ValueError):
    pass


@dataclass(frozen=True)
class RiskMeasureReviewChecklistRow:
    item_id: int
    follow_up_measure_id: int
    risk_label: str
    measure_title: str
    result: str
    note: str
    sort_order: int


class RiskMeasureReviewService:
    def __init__(self) -> None:
        self.repository = RiskMeasureReviewRepository()
        self.item_repository = RiskMeasureReviewItemRepository()

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
        created = self.repository.add(review)
        self._generate_checklist(created)
        return created

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
        checklist_updates: list[dict] | None = None,
    ) -> RiskMeasureReview | None:
        review = self.repository.get_by_id(review_id)
        if review is None:
            return None
        if review.archived_at is not None and status != RISK_MEASURE_REVIEW_STATUS_ARCHIVED:
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
        updated = self.repository.update(review)
        if checklist_updates is not None:
            self._apply_checklist_updates(updated.id, checklist_updates)
        return updated

    def list_checklist_rows(self, review_id: int) -> list[RiskMeasureReviewChecklistRow]:
        items = self.item_repository.list_for_review(review_id)
        rows: list[RiskMeasureReviewChecklistRow] = []
        for item in items:
            measure = hazard_required_measure_service.get_by_id(item.follow_up_measure_id)
            measure_title = measure.display_title() if measure is not None else "—"
            risk_label = self._risk_label_for_measure(measure) if measure is not None else "—"
            rows.append(
                RiskMeasureReviewChecklistRow(
                    item_id=int(item.id),
                    follow_up_measure_id=int(item.follow_up_measure_id),
                    risk_label=risk_label,
                    measure_title=measure_title,
                    result=item.result or RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
                    note=item.note or "",
                    sort_order=int(item.sort_order or 0),
                )
            )
        return rows

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

    def collect_follow_up_measures_for_scope(
        self,
        *,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
    ) -> list:
        """Aktivní navazující opatření v rozsahu (bez duplicit dle measure.id)."""
        if workplace_id is None:
            workplace_part_id = None

        collected: list = []
        seen_ids: set[int] = set()
        for identification in hazard_identification_service.get_all(include_inactive=False):
            if not self._identification_in_scope(
                identification,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
            ):
                continue
            for row in hazard_risk_assessment_service.get_for_identification(
                identification.id,
                include_inactive=False,
            ):
                assessment = row.assessment
                if not assessment.active:
                    continue
                for measure in hazard_required_measure_service.get_for_assessment(
                    assessment.id,
                    include_inactive=False,
                ):
                    if measure.id in seen_ids:
                        continue
                    seen_ids.add(measure.id)
                    collected.append(measure)
        return collected

    def _generate_checklist(self, review: RiskMeasureReview) -> list[RiskMeasureReviewItem]:
        existing = self.item_repository.list_for_review(review.id)
        if existing:
            return existing

        measures = self.collect_follow_up_measures_for_scope(
            operation_id=review.operation_id,
            workplace_id=review.workplace_id,
            workplace_part_id=review.workplace_part_id,
        )
        items: list[RiskMeasureReviewItem] = []
        for index, measure in enumerate(measures):
            items.append(
                RiskMeasureReviewItem(
                    review_id=review.id,
                    follow_up_measure_id=int(measure.id),
                    result=RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
                    note="",
                    sort_order=index + 1,
                )
            )
        if items:
            self.item_repository.replace_items(review.id, items)
        return self.item_repository.list_for_review(review.id)

    def _apply_checklist_updates(self, review_id: int, updates: list[dict]) -> None:
        by_id = {item.id: item for item in self.item_repository.list_for_review(review_id)}
        changed: list[RiskMeasureReviewItem] = []
        for payload in updates:
            item_id = payload.get("item_id")
            if item_id is None:
                continue
            item = by_id.get(int(item_id))
            if item is None:
                continue
            result = payload.get("result", item.result)
            if result not in RISK_MEASURE_REVIEW_ITEM_RESULTS:
                raise RiskMeasureReviewError("Neplatný výsledek položky checklistu.")
            item.result = result
            item.note = str(payload.get("note", item.note) or "").strip()
            item.updated_at = datetime.now()
            changed.append(item)
        for item in changed:
            self.item_repository.update(item)

    @staticmethod
    def _risk_label_for_measure(measure) -> str:
        assessment = hazard_risk_assessment_service.get_by_id(measure.hazard_risk_assessment_id)
        if assessment is None:
            return "—"
        event = hazard_event_service.get_by_id(assessment.hazard_event_id)
        if event is None:
            return "—"
        item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        item_name = (item.name if item is not None else "") or "—"
        event_name = (event.name or "").strip() or "—"
        return f"{item_name} — {event_name}"

    @staticmethod
    def _identification_in_scope(
        identification,
        *,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> bool:
        if identification.operation_id != operation_id:
            return False
        if workplace_part_id is not None:
            return identification.workplace_part_id == workplace_part_id
        if workplace_id is not None:
            return identification.workplace_id == workplace_id
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
