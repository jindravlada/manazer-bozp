from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session, open_session
from core.shared.modely.control_result import ControlResult


class ControlResultRepository:
    def get_for_entity(self, entity_type: str, entity_id: int) -> list[ControlResult]:
        with get_session() as session:
            stmt = (
                select(ControlResult)
                .where(
                    ControlResult.entity_type == entity_type,
                    ControlResult.entity_id == entity_id,
                )
                .order_by(ControlResult.id)
            )
            return list(session.scalars(stmt))

    def get_for_control_point(
        self,
        entity_type: str,
        entity_id: int,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        session: Session | None = None,
    ) -> ControlResult | None:
        with open_session(session) as (current, owns):
            stmt = select(ControlResult).where(
                ControlResult.entity_type == entity_type,
                ControlResult.entity_id == entity_id,
                ControlResult.source_area_label == area_label.strip(),
                ControlResult.source_section_label == section_label.strip(),
                ControlResult.source_control_point_id == control_point_id.strip(),
            )
            row = current.scalar(stmt)
            if row is not None and owns:
                current.expunge(row)
            return row

    def save(
        self,
        control_result: ControlResult,
        *,
        session: Session | None = None,
    ) -> ControlResult:
        with open_session(session) as (current, owns):
            control_result.updated_at = datetime.now()
            control_result = current.merge(control_result)
            current.flush()
            if owns:
                current.commit()
                current.refresh(control_result)
                current.expunge(control_result)
            return control_result

    def delete_for_entity(self, entity_type: str, entity_id: int) -> int:
        with get_session() as session:
            stmt = select(ControlResult).where(
                ControlResult.entity_type == entity_type,
                ControlResult.entity_id == entity_id,
            )
            rows = list(session.scalars(stmt))
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)
