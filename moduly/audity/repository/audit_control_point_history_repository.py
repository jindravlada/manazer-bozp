from dataclasses import dataclass

from sqlalchemy import select

from core.database.session import get_session
from core.shared.constants import CONTROL_RESULT_NEKONTROLOVANO, ENTITY_AUDITY
from core.shared.modely.control_result import ControlResult
from moduly.audity.modely.audit import Audit


@dataclass(frozen=True)
class AuditQuestionHistoryRecord:
    control_result: ControlResult
    audit: Audit


class AuditControlPointHistoryRepository:
    def get_for_control_point(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        workplace_id: int | None = None,
        exclude_workplace_id: int | None = None,
        exclude_audit_id: int | None = None,
        only_with_workplace: bool = False,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryRecord]:
        with get_session() as session:
            stmt = (
                select(ControlResult, Audit)
                .join(
                    Audit,
                    ControlResult.entity_id == Audit.id,
                )
                .where(
                    ControlResult.entity_type == ENTITY_AUDITY,
                    ControlResult.source_area_label == area_label.strip(),
                    ControlResult.source_section_label == section_label.strip(),
                    ControlResult.source_control_point_id == control_point_id.strip(),
                    ControlResult.result != CONTROL_RESULT_NEKONTROLOVANO,
                )
            )

            if workplace_id is not None:
                stmt = stmt.where(Audit.workplace_id == workplace_id)

            if exclude_workplace_id is not None:
                stmt = stmt.where(
                    Audit.workplace_id.isnot(None),
                    Audit.workplace_id != exclude_workplace_id,
                )

            if only_with_workplace:
                stmt = stmt.where(Audit.workplace_id.isnot(None))

            if exclude_audit_id is not None:
                stmt = stmt.where(ControlResult.entity_id != exclude_audit_id)

            stmt = stmt.order_by(
                ControlResult.recorded_at.desc(),
                ControlResult.id.desc(),
            ).limit(limit)

            rows = session.execute(stmt).all()
            return [
                AuditQuestionHistoryRecord(control_result=control_result, audit=audit)
                for control_result, audit in rows
            ]

    def get_shared_experiences(
        self,
        *,
        area_label: str,
        section_label: str,
        control_point_id: str,
        exclude_audit_id: int | None = None,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryRecord]:
        with get_session() as session:
            stmt = (
                select(ControlResult, Audit)
                .join(
                    Audit,
                    ControlResult.entity_id == Audit.id,
                )
                .where(
                    ControlResult.entity_type == ENTITY_AUDITY,
                    ControlResult.source_area_label == area_label.strip(),
                    ControlResult.source_section_label == section_label.strip(),
                    ControlResult.source_control_point_id == control_point_id.strip(),
                    ControlResult.result != CONTROL_RESULT_NEKONTROLOVANO,
                    ControlResult.shared_experience.is_(True),
                )
            )

            if exclude_audit_id is not None:
                stmt = stmt.where(ControlResult.entity_id != exclude_audit_id)

            stmt = stmt.order_by(
                ControlResult.recorded_at.desc(),
                ControlResult.id.desc(),
            ).limit(limit)

            rows = session.execute(stmt).all()
            return [
                AuditQuestionHistoryRecord(control_result=control_result, audit=audit)
                for control_result, audit in rows
            ]
