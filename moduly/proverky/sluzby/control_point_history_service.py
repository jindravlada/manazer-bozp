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
    workplace_id: int | None
    workplace_name: str
    finding: Finding | None


class ControlPointHistoryService:
    def __init__(self):
        self.repository = ControlPointHistoryRepository()

    def get_workplace_history(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        workplace_id: int | None,
        exclude_inspection_id: int | None = None,
        limit: int = 5,
    ) -> list[ControlPointHistoryEntry]:
        if not control_point_id or workplace_id is None:
            return []

        return self._to_entries(
            self.repository.get_for_control_point(
                area_label=area_label,
                section_label=section_label,
                control_point_id=control_point_id,
                workplace_id=workplace_id,
                exclude_inspection_id=exclude_inspection_id,
                limit=limit,
            ),
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
        )

    def get_shared_experiences(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        exclude_inspection_id: int | None = None,
        limit: int = 5,
    ) -> list[ControlPointHistoryEntry]:
        if not control_point_id:
            return []

        return self._to_entries(
            self.repository.get_shared_experiences(
                area_label=area_label,
                section_label=section_label,
                control_point_id=control_point_id,
                exclude_inspection_id=exclude_inspection_id,
                limit=limit,
            ),
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
        )

    def get_similar_elsewhere_history(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        workplace_id: int | None,
        exclude_inspection_id: int | None = None,
        limit: int = 5,
    ) -> list[ControlPointHistoryEntry]:
        if not control_point_id:
            return []

        return self._to_entries(
            self.repository.get_for_control_point(
                area_label=area_label,
                section_label=section_label,
                control_point_id=control_point_id,
                exclude_workplace_id=workplace_id,
                exclude_inspection_id=exclude_inspection_id,
                only_with_workplace=True,
                limit=limit,
            ),
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
        )

    def _to_entries(
        self,
        records,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
    ) -> list[ControlPointHistoryEntry]:
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
                    workplace_id=record.inspection.workplace_id,
                    workplace_name=str(record.inspection.workplace_name or "").strip(),
                    finding=finding,
                )
            )
        return entries

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
        """Zpětná kompatibilita — historie aktuálního pracoviště."""
        return self.get_workplace_history(
            area_label=area_label,
            section_label=section_label,
            control_point_id=control_point_id,
            workplace_id=workplace_id,
            exclude_inspection_id=exclude_inspection_id,
            limit=limit,
        )


control_point_history_service = ControlPointHistoryService()
