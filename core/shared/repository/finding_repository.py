from datetime import datetime

from sqlalchemy import func, select

from core.database.session import get_session
from core.shared.modely.finding import Finding


class FindingRepository:
    def get_for_entity(self, entity_type: str, entity_id: int) -> list[Finding]:
        with get_session() as session:
            stmt = (
                select(Finding)
                .where(
                    Finding.entity_type == entity_type,
                    Finding.entity_id == entity_id,
                )
                .order_by(Finding.display_order, Finding.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, finding_id: int) -> Finding | None:
        with get_session() as session:
            return session.get(Finding, finding_id)

    def get_by_task_id(self, task_id: int) -> Finding | None:
        with get_session() as session:
            stmt = select(Finding).where(Finding.task_id == task_id)
            return session.scalar(stmt)

    def save(self, finding: Finding) -> Finding:
        with get_session() as session:
            finding.updated_at = datetime.now()
            finding = session.merge(finding)
            session.commit()
            session.refresh(finding)
            return finding

    def delete(self, finding_id: int) -> bool:
        with get_session() as session:
            finding = session.get(Finding, finding_id)
            if finding is None:
                return False

            session.delete(finding)
            session.commit()
            return True

    def delete_for_entity(self, entity_type: str, entity_id: int) -> int:
        with get_session() as session:
            stmt = select(Finding).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            findings = list(session.scalars(stmt))
            for finding in findings:
                session.delete(finding)
            session.commit()
            return len(findings)

    def max_display_order(self, entity_type: str, entity_id: int) -> int:
        with get_session() as session:
            stmt = select(func.max(Finding.display_order)).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            value = session.scalar(stmt)
            return int(value or 0)

    def count_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        *,
        status: str | None = None,
        finding_type: str | None = None,
    ) -> int:
        with get_session() as session:
            stmt = select(func.count(Finding.id)).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            if status is not None:
                stmt = stmt.where(Finding.status == status)
            if finding_type is not None:
                stmt = stmt.where(Finding.finding_type == finding_type)
            return int(session.scalar(stmt) or 0)
