from sqlalchemy import func, select

from core.database.session import get_session
from moduly.audity.modely.audit_commission_member import AuditCommissionMember


class AuditCommissionRepository:
    def get_for_audit(
        self,
        audit_id: int,
        *,
        active_only: bool = False,
    ) -> list[AuditCommissionMember]:
        with get_session() as session:
            stmt = (
                select(AuditCommissionMember)
                .where(AuditCommissionMember.audit_id == audit_id)
                .order_by(
                    AuditCommissionMember.display_order,
                    AuditCommissionMember.id,
                )
            )
            if active_only:
                stmt = stmt.where(AuditCommissionMember.active.is_(True))
            return list(session.scalars(stmt))

    def add(self, member: AuditCommissionMember) -> AuditCommissionMember:
        with get_session() as session:
            session.add(member)
            session.commit()
            session.refresh(member)
            return member

    def delete_for_audit(self, audit_id: int) -> int:
        with get_session() as session:
            stmt = select(AuditCommissionMember).where(
                AuditCommissionMember.audit_id == audit_id,
            )
            members = list(session.scalars(stmt))
            for member in members:
                session.delete(member)
            session.commit()
            return len(members)

    def max_display_order(self, audit_id: int, record_type: str) -> int:
        with get_session() as session:
            stmt = select(func.max(AuditCommissionMember.display_order)).where(
                AuditCommissionMember.audit_id == audit_id,
                AuditCommissionMember.record_type == record_type,
            )
            value = session.scalar(stmt)
            return int(value or 0)
