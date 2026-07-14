from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_identification_photo import HazardIdentificationPhoto


class HazardIdentificationPhotoRepository:
    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardIdentificationPhoto]:
        with get_session() as session:
            stmt = select(HazardIdentificationPhoto).where(
                HazardIdentificationPhoto.hazard_identification_id
                == hazard_identification_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardIdentificationPhoto.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardIdentificationPhoto.sort_order,
                HazardIdentificationPhoto.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, photo_id: int) -> HazardIdentificationPhoto | None:
        with get_session() as session:
            return session.get(HazardIdentificationPhoto, photo_id)

    def add(self, photo: HazardIdentificationPhoto) -> HazardIdentificationPhoto:
        with get_session() as session:
            session.add(photo)
            session.commit()
            session.refresh(photo)
            return photo

    def update(self, photo: HazardIdentificationPhoto) -> HazardIdentificationPhoto:
        with get_session() as session:
            photo = session.merge(photo)
            session.commit()
            session.refresh(photo)
            return photo

    def next_sort_order(self, hazard_identification_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardIdentificationPhoto.sort_order)
                .where(
                    HazardIdentificationPhoto.hazard_identification_id
                    == hazard_identification_id
                )
                .order_by(HazardIdentificationPhoto.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1

    def count_for_identification(self, hazard_identification_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardIdentificationPhoto)
                .where(
                    HazardIdentificationPhoto.hazard_identification_id
                    == hazard_identification_id
                )
            )
            return int(session.scalar(stmt) or 0)
