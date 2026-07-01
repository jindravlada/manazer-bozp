from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from core.shared.constants import CONTROL_RESULT_NEKONTROLOVANO, ENTITY_PROVERKY
from core.shared.modely.control_result import ControlResult
from moduly.proverky.modely.bozp_inspection import BozpInspection


@dataclass(frozen=True)
class ControlPointHistoryRecord:
    control_result: ControlResult
    inspection: BozpInspection


class ControlPointHistoryRepository:
    def get_for_control_point(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        workplace_id: int | None = None,
        exclude_workplace_id: int | None = None,
        exclude_inspection_id: int | None = None,
        only_with_workplace: bool = False,
        limit: int = 5,
    ) -> list[ControlPointHistoryRecord]:
        with get_session() as session:
            stmt = (
                select(ControlResult, BozpInspection)
                .join(
                    BozpInspection,
                    ControlResult.entity_id == BozpInspection.id,
                )
                .where(
                    ControlResult.entity_type == ENTITY_PROVERKY,
                    ControlResult.source_area_label == area_label.strip(),
                    ControlResult.source_section_label == section_label.strip(),
                    ControlResult.source_control_point_id == control_point_id.strip(),
                    ControlResult.result != CONTROL_RESULT_NEKONTROLOVANO,
                )
            )

            if workplace_id is not None:
                stmt = stmt.where(BozpInspection.workplace_id == workplace_id)

            if exclude_workplace_id is not None:
                stmt = stmt.where(
                    BozpInspection.workplace_id.isnot(None),
                    BozpInspection.workplace_id != exclude_workplace_id,
                )

            if only_with_workplace:
                stmt = stmt.where(BozpInspection.workplace_id.isnot(None))

            if exclude_inspection_id is not None:
                stmt = stmt.where(ControlResult.entity_id != exclude_inspection_id)

            stmt = stmt.order_by(
                ControlResult.recorded_at.desc(),
                ControlResult.id.desc(),
            ).limit(limit)

            rows = session.execute(stmt).all()
            return [
                ControlPointHistoryRecord(control_result=control_result, inspection=inspection)
                for control_result, inspection in rows
            ]
