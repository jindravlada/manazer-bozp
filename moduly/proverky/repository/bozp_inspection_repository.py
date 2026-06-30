from sqlalchemy import select

from core.database.session import get_session
from moduly.proverky.modely.bozp_inspection import BozpInspection


class BozpInspectionRepository:
    def get_all(self) -> list[BozpInspection]:
        with get_session() as session:
            stmt = select(BozpInspection).order_by(
                BozpInspection.inspection_date.desc(),
                BozpInspection.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, inspection_id: int) -> BozpInspection | None:
        with get_session() as session:
            return session.get(BozpInspection, inspection_id)

    def add(self, inspection: BozpInspection) -> BozpInspection:
        with get_session() as session:
            session.add(inspection)
            session.commit()
            session.refresh(inspection)
            return inspection

    def update(self, inspection: BozpInspection) -> BozpInspection:
        with get_session() as session:
            inspection = session.merge(inspection)
            session.commit()
            session.refresh(inspection)
            return inspection

    def delete(self, inspection_id: int) -> bool:
        with get_session() as session:
            inspection = session.get(BozpInspection, inspection_id)
            if inspection is None:
                return False

            session.delete(inspection)
            session.commit()
            return True
