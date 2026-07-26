from sqlalchemy import select

from core.database.session import SessionLocal
from moduly.proverky.modely.bozp_inspection_verification_override import (
    BozpInspectionVerificationOverride,
)


class BozpInspectionVerificationOverrideRepository:
    def list_for_inspection(
        self, inspection_id: int
    ) -> list[BozpInspectionVerificationOverride]:
        with SessionLocal() as session:
            rows = session.scalars(
                select(BozpInspectionVerificationOverride).where(
                    BozpInspectionVerificationOverride.inspection_id == inspection_id
                )
            ).all()
            session.expunge_all()
            return list(rows)

    def get(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> BozpInspectionVerificationOverride | None:
        with SessionLocal() as session:
            row = session.scalars(
                select(BozpInspectionVerificationOverride).where(
                    BozpInspectionVerificationOverride.inspection_id == inspection_id,
                    BozpInspectionVerificationOverride.source_area_id == area_id,
                    BozpInspectionVerificationOverride.source_section_id == section_id,
                    BozpInspectionVerificationOverride.source_control_point_id
                    == control_point_id,
                )
            ).first()
            if row is not None:
                session.expunge(row)
            return row

    def upsert(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        override_verification_type: str,
    ) -> BozpInspectionVerificationOverride:
        with SessionLocal() as session:
            row = session.scalars(
                select(BozpInspectionVerificationOverride).where(
                    BozpInspectionVerificationOverride.inspection_id == inspection_id,
                    BozpInspectionVerificationOverride.source_area_id == area_id,
                    BozpInspectionVerificationOverride.source_section_id == section_id,
                    BozpInspectionVerificationOverride.source_control_point_id
                    == control_point_id,
                )
            ).first()
            if row is None:
                row = BozpInspectionVerificationOverride(
                    inspection_id=inspection_id,
                    source_area_id=area_id,
                    source_section_id=section_id,
                    source_control_point_id=control_point_id,
                    override_verification_type=override_verification_type,
                )
                session.add(row)
            else:
                row.override_verification_type = override_verification_type
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def delete(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> bool:
        with SessionLocal() as session:
            row = session.scalars(
                select(BozpInspectionVerificationOverride).where(
                    BozpInspectionVerificationOverride.inspection_id == inspection_id,
                    BozpInspectionVerificationOverride.source_area_id == area_id,
                    BozpInspectionVerificationOverride.source_section_id == section_id,
                    BozpInspectionVerificationOverride.source_control_point_id
                    == control_point_id,
                )
            ).first()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def delete_for_inspection(self, inspection_id: int) -> int:
        with SessionLocal() as session:
            rows = session.scalars(
                select(BozpInspectionVerificationOverride).where(
                    BozpInspectionVerificationOverride.inspection_id == inspection_id
                )
            ).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count
