from sqlalchemy import func, select

from core.database.session import get_session
from moduly.proverky.modely.bozp_inspection_commission_member import BozpInspectionCommissionMember


class BozpInspectionCommissionRepository:
    def get_for_inspection(
        self,
        inspection_id: int,
        *,
        active_only: bool = False,
    ) -> list[BozpInspectionCommissionMember]:
        with get_session() as session:
            stmt = (
                select(BozpInspectionCommissionMember)
                .where(BozpInspectionCommissionMember.inspection_id == inspection_id)
                .order_by(
                    BozpInspectionCommissionMember.display_order,
                    BozpInspectionCommissionMember.id,
                )
            )
            if active_only:
                stmt = stmt.where(BozpInspectionCommissionMember.active.is_(True))
            return list(session.scalars(stmt))

    def add(self, member: BozpInspectionCommissionMember) -> BozpInspectionCommissionMember:
        with get_session() as session:
            session.add(member)
            session.commit()
            session.refresh(member)
            return member

    def delete_for_inspection(self, inspection_id: int) -> int:
        with get_session() as session:
            stmt = select(BozpInspectionCommissionMember).where(
                BozpInspectionCommissionMember.inspection_id == inspection_id,
            )
            members = list(session.scalars(stmt))
            for member in members:
                session.delete(member)
            session.commit()
            return len(members)

    def max_display_order(self, inspection_id: int, record_type: str) -> int:
        with get_session() as session:
            stmt = select(func.max(BozpInspectionCommissionMember.display_order)).where(
                BozpInspectionCommissionMember.inspection_id == inspection_id,
                BozpInspectionCommissionMember.record_type == record_type,
            )
            value = session.scalar(stmt)
            return int(value or 0)
