from dataclasses import dataclass
from datetime import datetime

from core.shared.modely.finding import Finding
from moduly.proverky.repository.control_point_history_repository import ControlPointHistoryRepository
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


@dataclass(frozen=True)
class ControlPointHistoryEntry:
    recorded_at: datetime | None
    result: str
    note: str
    inspection_id: int
    inspection_number: str
    finding: Finding | None


class ControlPointHistoryService:
    def __init__(self):
        self.repository = ControlPointHistoryRepository()

    def get_history(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        workplace_id: int | None = None,
        exclude_inspection_id: int | None = None,
        limit: int = 5,
    ) -> list[ControlPointHistoryEntry]:
        if not control_point_id:
            return []

        records = self.repository.get_for_control_point(
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
            workplace_id=workplace_id,
            exclude_inspection_id=exclude_inspection_id,
            limit=limit,
        )

        entries: list[ControlPointHistoryEntry] = []
        for record in records:
            finding = bozp_inspection_service.finding_for_control_point(
                record.inspection.id,
                area_label=area_label,
                section_label=section_label,
                control_point_id=control_point_id,
            )
            entries.append(
                ControlPointHistoryEntry(
                    recorded_at=record.control_result.recorded_at,
                    result=record.control_result.result,
                    note=record.control_result.note or "",
                    inspection_id=record.inspection.id,
                    inspection_number=str(record.inspection.number or "").strip(),
                    finding=finding,
                )
            )
        return entries


control_point_history_service = ControlPointHistoryService()
