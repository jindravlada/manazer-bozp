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
    ENTITY_RISK_MEASURE_REVIEW,
    ENTITY_RISK_MEASURE_REVIEW_ITEM,
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
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
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service
from core.services.attachment_service import attachment_service


class RiskMeasureReviewError(ValueError):
    pass


@dataclass(frozen=True)
class RiskMeasureReviewChecklistRow:
    item_id: int
    follow_up_measure_id: int
    measure_title: str
    result: str
    note: str
    photo_count: int
    has_photo: bool
    sort_order: int

    @property
    def compliant(self) -> bool:
        return self.result == RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT

    @property
    def non_compliant(self) -> bool:
        return self.result == RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT

    @property
    def result_text(self) -> str:
        """Zpětná kompatibilita – dříve „výsledek“, nyní poznámka."""
        return self.note


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

    def get_tasks_for_review(self, review_id: int) -> list[Task]:
        """Úkoly navázané na přezkoumání (source_module + source_record_id)."""
        tasks = task_service.repository.list_by_source(
            source_module=ENTITY_RISK_MEASURE_REVIEW,
            source_record_id=review_id,
        )
        return sorted(tasks, key=lambda item: (item.due_date or date.max, item.id))

    def create_task_for_review(
        self,
        review_id: int,
        *,
        title: str,
        description: str = "",
        due_date: date | None = None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
        source_check_code: str = "",
    ) -> Task:
        """
        Vytvoří úkol navázaný na přezkoumání.
        source_check_code připravuje budoucí vazbu na kontrolní bod checklistu.
        """
        review = self.repository.get_by_id(review_id)
        if review is None:
            raise RiskMeasureReviewError("Přezkoumání nebylo nalezeno.")
        cleaned_title = (title or "").strip()
        if not cleaned_title:
            raise RiskMeasureReviewError("Název úkolu je povinný.")
        return task_service.create_task(
            title=cleaned_title[:200],
            description=(description or "").strip(),
            due_date=due_date,
            responsible_person_id=responsible_person_id,
            workplace_id=workplace_id if workplace_id is not None else review.workplace_id,
            source_module=ENTITY_RISK_MEASURE_REVIEW,
            source_record_id=review_id,
            source_check_code=(source_check_code or "").strip()[:100],
        )

    def list_checklist_rows(self, review_id: int) -> list[RiskMeasureReviewChecklistRow]:
        items = self.item_repository.list_for_review(review_id)
        rows: list[RiskMeasureReviewChecklistRow] = []
        for item in items:
            measure = hazard_required_measure_service.get_by_id(item.follow_up_measure_id)
            measure_title = measure.display_title() if measure is not None else "—"
            result = self._normalize_item_result(item)
            photo_count = len(
                attachment_service.get_for_entity(
                    ENTITY_RISK_MEASURE_REVIEW_ITEM,
                    int(item.id),
                )
            )
            rows.append(
                RiskMeasureReviewChecklistRow(
                    item_id=int(item.id),
                    follow_up_measure_id=int(item.follow_up_measure_id),
                    measure_title=measure_title,
                    result=result,
                    note=(item.note or "").strip(),
                    photo_count=photo_count,
                    has_photo=photo_count > 0 or bool(getattr(item, "has_photo", False)),
                    sort_order=int(item.sort_order or 0),
                )
            )
        return rows

    def ensure_checklist(self, review_id: int) -> list[RiskMeasureReviewChecklistRow]:
        """Načte/vygeneruje checklist pro provedení přezkoumání."""
        review = self.repository.get_by_id(review_id)
        if review is None:
            return []
        self._generate_checklist(review)
        return self.list_checklist_rows(review_id)

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
                    compliant=False,
                    note_number="",
                    has_photo=False,
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
            result = self._result_from_payload(payload, item)
            item.result = result
            item.compliant = result == RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
            if "note" in payload:
                item.note = str(payload.get("note") or "").strip()
            elif "result_text" in payload:
                item.note = str(payload.get("result_text") or "").strip()
            if "has_photo" in payload:
                item.has_photo = bool(payload.get("has_photo"))
            elif "photo_count" in payload:
                item.has_photo = int(payload.get("photo_count") or 0) > 0
            item.updated_at = datetime.now()
            changed.append(item)
        for item in changed:
            self.item_repository.update(item)

    @staticmethod
    def _normalize_item_result(item: RiskMeasureReviewItem) -> str:
        result = str(getattr(item, "result", "") or "").strip()
        if result in {
            RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
            RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
            RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        }:
            return result
        if bool(getattr(item, "compliant", False)):
            return RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
        return RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED

    @classmethod
    def _result_from_payload(cls, payload: dict, item: RiskMeasureReviewItem) -> str:
        if "result" in payload:
            result = str(payload.get("result") or "").strip()
            if result in {
                RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
                RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
            }:
                return result
        if "compliant" in payload and "non_compliant" in payload:
            if bool(payload.get("compliant")):
                return RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
            if bool(payload.get("non_compliant")):
                return RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT
            return RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
        if "compliant" in payload:
            return (
                RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
                if bool(payload.get("compliant"))
                else RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT
            )
        return cls._normalize_item_result(item)

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
