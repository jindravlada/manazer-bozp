from __future__ import annotations

import getpass
from dataclasses import dataclass
from datetime import date, datetime

from core.services.attachment_service import attachment_service
from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    ENTITY_RISK_MEASURE_REVIEW,
    ENTITY_RISK_MEASURE_REVIEW_ITEM,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTIONS,
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    RISK_MEASURE_REVIEW_RESOLUTION_REQUIRED,
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
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


def resolve_current_thp_worker_id() -> int | None:
    """Vrátí ID aktivního THP pracovníka odpovídajícího aktuálnímu uživateli OS.

    Shoda je podle lokální části e-mailu nebo podle křestního jména / příjmení
    (case-insensitive). Při nejednoznačnosti nebo bez shody vrací ``None``.
    """
    username = (getpass.getuser() or "").strip().casefold()
    if not username:
        return None

    matches: list[int] = []
    for worker in settings_service.get_workers(include_inactive=False):
        email = (getattr(worker, "email", None) or "").strip()
        local = email.split("@", 1)[0].casefold() if email else ""
        first = (worker.first_name or "").strip().casefold()
        last = (worker.last_name or "").strip().casefold()
        candidates = {local, first, last, f"{first}.{last}".replace(" ", "")}
        candidates.discard("")
        if username in candidates:
            matches.append(int(worker.id))
    if len(matches) == 1:
        return matches[0]
    return None


def split_checklist_measure_lines(text: str) -> list[str]:
    """Rozdělí text navazujícího opatření na kontrolní body (RISK-CHECKLIST-1/2).

    Hranice = Enter (``\\n`` / ``\\r\\n`` / ``\\r``). Prázdné řádky a okolní
    mezery se vynechají / oříznou.
    """
    if not text:
        return []
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            lines.append(line)
    return lines


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
    resolution: str = RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED

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

    @property
    def is_resolved(self) -> bool:
        return self.resolution in {
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK,
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
        }


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
        if checklist_updates is not None:
            self._apply_checklist_updates(review_id, checklist_updates)
        resolved = self._validate_and_resolve(
            review_date=review_date,
            reviewer_person_id=reviewer_person_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            status=status,
        )
        if status == RISK_MEASURE_REVIEW_STATUS_COMPLETED:
            self.assert_non_compliant_points_resolved(review_id)
        review.review_date = review_date
        review.note = note.strip()
        for key, value in resolved.items():
            setattr(review, key, value)
        review.updated_at = datetime.now()
        return self.repository.update(review)

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
        remind_from: date | None = None,
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
            remind_from=remind_from,
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
            measure_title = self._checklist_item_title(measure, item)
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
                    resolution=self._normalize_item_resolution(item, result=result),
                )
            )
        return rows

    def list_non_compliant_rows(
        self,
        review_id: int,
    ) -> list[RiskMeasureReviewChecklistRow]:
        """Nevyhovující kontrolní body pro záložku Úkoly."""
        return [row for row in self.list_checklist_rows(review_id) if row.non_compliant]

    def set_item_resolution(self, item_id: int, resolution: str) -> RiskMeasureReviewItem:
        item = self.item_repository.get_by_id(item_id)
        if item is None:
            raise RiskMeasureReviewError("Kontrolní bod nebyl nalezen.")
        cleaned = str(resolution or "").strip()
        if cleaned not in RISK_MEASURE_REVIEW_ITEM_RESOLUTIONS:
            raise RiskMeasureReviewError("Neplatný způsob řešení kontrolního bodu.")
        result = self._normalize_item_result(item)
        if cleaned and result != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
            raise RiskMeasureReviewError(
                "Způsob řešení lze nastavit jen u nevyhovujícího kontrolního bodu."
            )
        item.resolution = cleaned
        item.updated_at = datetime.now()
        return self.item_repository.update(item)

    def create_task_for_checklist_item(
        self,
        review_id: int,
        item_id: int,
        *,
        title: str,
        description: str = "",
        due_date: date | None = None,
        remind_from: date | None = None,
        responsible_person_id: int | None = None,
        workplace_id: int | None = None,
    ) -> Task:
        """Založí úkol k nevyhovujícímu bodu a označí řešení jako úkol."""
        item = self.item_repository.get_by_id(item_id)
        if item is None or int(item.review_id) != int(review_id):
            raise RiskMeasureReviewError("Kontrolní bod nepatří k tomuto přezkoumání.")
        if self._normalize_item_result(item) != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
            raise RiskMeasureReviewError(
                "Úkol lze založit jen u nevyhovujícího kontrolního bodu."
            )
        task = self.create_task_for_review(
            review_id,
            title=title,
            description=description,
            due_date=due_date,
            remind_from=remind_from,
            responsible_person_id=responsible_person_id,
            workplace_id=workplace_id,
            source_check_code=f"item:{int(item_id)}",
        )
        self.set_item_resolution(item_id, RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK)
        return task

    def mark_measure_revision_for_item(self, item_id: int) -> RiskMeasureReviewItem:
        """Označí, že uživatel zvolil revizi opatření proti riziku."""
        return self.set_item_resolution(
            item_id,
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
        )

    def resolve_context_for_measure(self, follow_up_measure_id: int) -> dict:
        """Vrátí identifikaci / posouzení pro otevření revize opatření."""
        measure = hazard_required_measure_service.get_by_id(follow_up_measure_id)
        if measure is None:
            raise RiskMeasureReviewError("Navazující opatření nebylo nalezeno.")
        assessment = hazard_risk_assessment_service.get_by_id(
            measure.hazard_risk_assessment_id
        )
        if assessment is None:
            raise RiskMeasureReviewError("Posouzení rizika nebylo nalezeno.")
        event = hazard_event_service.get_by_id(assessment.hazard_event_id)
        if event is None:
            raise RiskMeasureReviewError("Událost rizika nebyla nalezena.")
        inventory_item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        if inventory_item is None:
            raise RiskMeasureReviewError("Zdroj rizika nebyl nalezen.")
        identification = hazard_identification_service.get_by_id(
            inventory_item.hazard_identification_id
        )
        if identification is None:
            raise RiskMeasureReviewError("Identifikace rizik nebyla nalezena.")
        return {
            "measure": measure,
            "assessment": assessment,
            "event": event,
            "inventory_item": inventory_item,
            "identification": identification,
        }

    def assert_non_compliant_points_resolved(self, review_id: int) -> None:
        unresolved = [
            row
            for row in self.list_non_compliant_rows(review_id)
            if not row.is_resolved
        ]
        if unresolved:
            raise RiskMeasureReviewError(RISK_MEASURE_REVIEW_RESOLUTION_REQUIRED)

    def ensure_checklist(self, review_id: int) -> list[RiskMeasureReviewChecklistRow]:
        """Načte/vygeneruje checklist pro provedení přezkoumání."""
        review = self.repository.get_by_id(review_id)
        if review is None:
            return []
        items = self._generate_checklist(review)
        self._repair_accidental_all_non_compliant(items)
        return self.list_checklist_rows(review_id)

    def _repair_accidental_all_non_compliant(
        self,
        items: list[RiskMeasureReviewItem],
    ) -> None:
        """Oprava historického defaultu: všechno „Nevyhovuje“ bez poznámek/fotek."""
        if not items:
            return
        if any(
            self._normalize_item_result(item)
            != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT
            for item in items
        ):
            return
        if any((item.note or "").strip() or bool(item.has_photo) for item in items):
            return
        for item in items:
            item.result = RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
            item.compliant = False
            item.updated_at = datetime.now()
            self.item_repository.update(item)

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
        sort_order = 0
        for measure in measures:
            lines = split_checklist_measure_lines(measure.display_title())
            if not lines:
                lines = ["—"]
            multi = len(lines) > 1
            for line_index, _line in enumerate(lines):
                sort_order += 1
                items.append(
                    RiskMeasureReviewItem(
                        review_id=review.id,
                        follow_up_measure_id=int(measure.id),
                        compliant=False,
                        # Index řádku v rámci víceřádkového opatření (RISK-CHECKLIST-2).
                        note_number=str(line_index) if multi else "",
                        has_photo=False,
                        result=RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
                        note="",
                        sort_order=sort_order,
                    )
                )
        if items:
            self.item_repository.replace_items(review.id, items)
        return self.item_repository.list_for_review(review.id)

    @staticmethod
    def _checklist_item_title(measure, item: RiskMeasureReviewItem) -> str:
        """Text kontrolního bodu – u víceřádkových opatření jeden řádek."""
        if measure is None:
            return "—"
        full_title = measure.display_title()
        lines = split_checklist_measure_lines(full_title)
        line_key = (item.note_number or "").strip()
        if line_key.isdigit() and lines:
            index = int(line_key)
            if 0 <= index < len(lines):
                return lines[index]
            return lines[0]
        if len(lines) == 1:
            return lines[0]
        if lines:
            # Starší checklist (jedna položka na celé opatření) – ponechat celý text.
            return full_title
        return "—"

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
            if result != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
                item.resolution = RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED
            elif "resolution" in payload:
                cleaned = str(payload.get("resolution") or "").strip()
                if cleaned in RISK_MEASURE_REVIEW_ITEM_RESOLUTIONS:
                    item.resolution = cleaned
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
    def _normalize_item_resolution(
        item: RiskMeasureReviewItem,
        *,
        result: str | None = None,
    ) -> str:
        normalized_result = result or RiskMeasureReviewService._normalize_item_result(item)
        if normalized_result != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
            return RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED
        value = str(getattr(item, "resolution", "") or "").strip()
        if value in RISK_MEASURE_REVIEW_ITEM_RESOLUTIONS:
            return value
        return RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED

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
            # Samotné compliant=False už neznamená „Nevyhovuje“ (tri-state).
            return (
                RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
                if bool(payload.get("compliant"))
                else RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
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
        reviewer_name = self._resolve_reviewer_display_name(reviewer_person_id)
        if not reviewer_name:
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
            "reviewer_person_name": reviewer_name,
            "operation_id": int(operation_id),
            "operation_name": operation.name or "",
            "workplace_id": resolved_workplace_id,
            "workplace_name": workplace_name,
            "workplace_part_id": resolved_part_id,
            "workplace_part_name": workplace_part_name,
            "status": status,
        }

    @staticmethod
    def _resolve_reviewer_display_name(reviewer_person_id: int) -> str:
        """Jméno kontrolujícího z číselníku THP (stejné ID jako v dialogu)."""
        worker = settings_service.get_worker_by_id(reviewer_person_id)
        if worker is None:
            return ""
        return (worker.display_name or "").strip()


risk_measure_review_service = RiskMeasureReviewService()
