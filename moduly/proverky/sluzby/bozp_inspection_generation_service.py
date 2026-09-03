from dataclasses import dataclass
from datetime import date
import logging

from moduly.nastaveni.constants.workplace_audit_constants import DEFAULT_PREFERRED_AUDIT_MONTHS
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPES,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.nastaveni.sluzby.workplace_audit_planning import (
    parse_preferred_months_json,
    plan_visit_months,
)
from moduly.proverky.constants import DEFAULT_INSPECTION_TYPE
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service

ANNUAL_INSPECTION_INTERVAL_MONTHS = 12

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InspectionGenerationResult:
    created: tuple[BozpInspection, ...]
    skipped_existing: int


class BozpInspectionGenerationService:
    def generate_for_year(self, year: int) -> InspectionGenerationResult:
        workplaces = settings_service.get_workplaces(include_inactive=False)
        existing_operation_ids = self._operations_with_inspection_for_year(year)
        month_usage = self._month_usage_for_year(year)

        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        created: list[BozpInspection] = []
        skipped = 0

        operations = [
            workplace
            for workplace in workplaces
            if self._is_generatable_operation(workplace)
        ]
        operations.sort(key=lambda item: (item.id or 0, str(item.name or "")))

        for workplace in operations:
            workplace_id = workplace.id
            if workplace_id is None:
                continue
            if workplace_id in existing_operation_ids:
                skipped += 1
                continue

            preferred = parse_preferred_months_json(workplace.preferred_months_json)
            if not preferred:
                preferred = DEFAULT_PREFERRED_AUDIT_MONTHS

            planned = plan_visit_months(
                date_from,
                date_to,
                ANNUAL_INSPECTION_INTERVAL_MONTHS,
                preferred,
                month_usage=month_usage,
                workplace_key=workplace_id,
            )
            if not planned:
                month = ((len(created) % 12) + 1)
                planned = [(year, month)]

            planned_year, planned_month = planned[0]
            inspection = bozp_inspection_service.create_inspection(
                year=planned_year,
                planned_month=planned_month,
                workplace_id=workplace_id,
                workplace_name=workplace.name,
                title=f"Prověrka BOZP – {workplace.name}",
                inspection_type=DEFAULT_INSPECTION_TYPE,
            )
            created.append(inspection)
            existing_operation_ids.add(workplace_id)
            month_usage[(planned_year, planned_month)] = month_usage.get((planned_year, planned_month), 0) + 1

        return InspectionGenerationResult(
            created=tuple(created),
            skipped_existing=skipped,
        )

    def _is_generatable_operation(self, workplace) -> bool:
        if workplace is None:
            return False
        item_type = str(getattr(workplace, "item_type", "") or "").strip()
        if item_type not in WORKPLACE_ITEM_TYPES:
            logger.warning(
                "Generování prověrek: vynechán záznam id=%s name=%r item_type=%r "
                "(nejednoznačná úroveň hierarchie).",
                getattr(workplace, "id", None),
                getattr(workplace, "name", ""),
                item_type,
            )
            return False
        if item_type != WORKPLACE_ITEM_TYPE_OPERATION:
            return False
        return bool(getattr(workplace, "active", True))

    def _operations_with_inspection_for_year(self, year: int) -> set[int]:
        workplace_ids: set[int] = set()
        for inspection in bozp_inspection_service.get_for_year(year):
            if inspection.workplace_id is not None:
                workplace_ids.add(inspection.workplace_id)
        return workplace_ids

    def _month_usage_for_year(self, year: int) -> dict[tuple[int, int], int]:
        usage: dict[tuple[int, int], int] = {}
        for inspection in bozp_inspection_service.get_for_year(year):
            if inspection.planned_month is None:
                continue
            planned_year = inspection.year or year
            key = (planned_year, inspection.planned_month)
            usage[key] = usage.get(key, 0) + 1
        return usage


bozp_inspection_generation_service = BozpInspectionGenerationService()
