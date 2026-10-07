from sqlalchemy import select
from sqlalchemy.orm import Session

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
        session: Session | None = None,
    ) -> BozpInspectionVerificationOverride:
        owns = session is None
        current = SessionLocal() if owns else session
        try:
            row = current.scalars(
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
                current.add(row)
            else:
                row.override_verification_type = override_verification_type
            current.flush()
            if owns:
                current.commit()
                current.refresh(row)
                current.expunge(row)
            return row
        except Exception:
            if owns:
                current.rollback()
            raise
        finally:
            if owns:
                current.close()

    def delete(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        session: Session | None = None,
    ) -> bool:
        owns = session is None
        current = SessionLocal() if owns else session
        try:
            row = current.scalars(
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
            current.delete(row)
            current.flush()
            if owns:
                current.commit()
            return True
        except Exception:
            if owns:
                current.rollback()
            raise
        finally:
            if owns:
                current.close()

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
