from datetime import date, datetime

from core.shared.constants import (
    ENTITY_PROVERKY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
)
from core.shared.modely.finding import Finding
from core.shared.sluzby.finding_service import finding_service
from core.shared.sluzby.control_result_service import control_result_service
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_SPIS_STATUS,
    DEFAULT_INSPECTION_TYPE,
    INSPECTION_SPIS_STATUSES,
    INSPECTION_TYPES,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.repository.bozp_inspection_repository import BozpInspectionRepository
from moduly.nastaveni.sluzby.settings_service import settings_service

_OPEN_FINDING_STATUSES = frozenset(
    {
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
    }
)


class BozpInspectionService:
    def __init__(self):
        self.repository = BozpInspectionRepository()

    def get_all(self) -> list[BozpInspection]:
        return self.repository.get_all()

    def get_by_id(self, inspection_id: int) -> BozpInspection | None:
        return self.repository.get_by_id(inspection_id)

    def create_inspection(self, **fields) -> BozpInspection:
        data = self._validated_fields(fields)
        inspection = BozpInspection(**data)
        saved = self.repository.add(inspection)
        saved.number = self._make_number(saved.id, saved.year)
        return self.repository.update(saved)

    def update_inspection(self, inspection_id: int, **fields) -> BozpInspection | None:
        inspection = self.repository.get_by_id(inspection_id)
        if inspection is None:
            return None

        data = self._validated_fields(fields)
        for key, value in data.items():
            setattr(inspection, key, value)
        inspection.updated_at = datetime.now()
        return self.repository.update(inspection)

    def delete_inspection(self, inspection_id: int) -> bool:
        finding_service.delete_for_entity(ENTITY_PROVERKY, inspection_id)
        control_result_service.delete_for_entity(ENTITY_PROVERKY, inspection_id)
        return self.repository.delete(inspection_id)

    def resolve_workplace_name(self, workplace_id: int | None) -> str:
        if not workplace_id:
            return ""

        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""

    def resolve_workplace_id_by_name(self, workplace_name: str) -> int | None:
        name = str(workplace_name or "").strip()
        if not name:
            return None

        for workplace in settings_service.get_workplaces(include_inactive=True):
            if workplace.name == name:
                return workplace.id
        return None

    def findings_count(self, inspection_id: int) -> int:
        return len(finding_service.get_for_entity(ENTITY_PROVERKY, inspection_id))

    def finding_for_control_point(
        self,
        inspection_id: int,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
    ) -> Finding | None:
        if not control_point_id:
            return None

        for finding in finding_service.get_for_entity(ENTITY_PROVERKY, inspection_id):
            if self._matches_control_point(
                finding,
                area_label=area_label,
                section_label=section_label,
                control_point_id=control_point_id,
            ):
                return finding
        return None

    def open_finding_for_control_point(
        self,
        inspection_id: int,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
    ) -> Finding | None:
        finding = self.finding_for_control_point(
            inspection_id,
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
        )
        if finding is None or finding.status not in _OPEN_FINDING_STATUSES:
            return None
        return finding

    @staticmethod
    def _matches_control_point(
        finding: Finding,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
    ) -> bool:
        return (
            str(finding.source_control_point_id or "").strip() == control_point_id
            and str(finding.source_area_label or "").strip() == area_label.strip()
            and str(finding.source_section_label or "").strip() == section_label.strip()
        )

    def _validated_fields(self, fields: dict) -> dict:
        data = dict(fields)

        status = data.get("status", DEFAULT_INSPECTION_SPIS_STATUS)
        if status not in INSPECTION_SPIS_STATUSES:
            raise ValueError(f"Neplatný stav prověrky: {status}")

        inspection_type = data.get("inspection_type", DEFAULT_INSPECTION_TYPE)
        if inspection_type not in INSPECTION_TYPES:
            raise ValueError(f"Neplatný typ prověrky: {inspection_type}")

        if data.get("year") is None:
            data["year"] = date.today().year

        workplace_id = data.get("workplace_id")
        if workplace_id is not None:
            data["workplace_id"] = int(workplace_id)
        else:
            data["workplace_id"] = None

        data["workplace_name"] = str(data.get("workplace_name") or "").strip()
        data["title"] = str(data.get("title") or "").strip()

        return {
            "year": data.get("year"),
            "planned_month": data.get("planned_month"),
            "inspection_date": data.get("inspection_date"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "status": status,
            "inspection_type": inspection_type,
            "workplace_id": data.get("workplace_id"),
            "workplace_name": data["workplace_name"],
            "title": data["title"],
        }

    @staticmethod
    def _make_number(inspection_id: int, year: int | None) -> str:
        number_year = year or date.today().year
        return f"{inspection_id}/{number_year}"


bozp_inspection_service = BozpInspectionService()
