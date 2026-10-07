from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import SessionLocal
from moduly.audity.modely.audit_verification_override import AuditVerificationOverride


class AuditVerificationOverrideRepository:
    def list_for_audit(self, audit_id: int) -> list[AuditVerificationOverride]:
        with SessionLocal() as session:
            rows = session.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id
                )
            ).all()
            session.expunge_all()
            return list(rows)

    def get(
        self,
        audit_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> AuditVerificationOverride | None:
        with SessionLocal() as session:
            row = session.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id,
                    AuditVerificationOverride.source_area_id == area_id,
                    AuditVerificationOverride.source_section_id == section_id,
                    AuditVerificationOverride.source_control_point_id == control_point_id,
                )
            ).first()
            if row is not None:
                session.expunge(row)
            return row

    def upsert(
        self,
        audit_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        override_verification_type: str,
        session: Session | None = None,
    ) -> AuditVerificationOverride:
        owns = session is None
        current = SessionLocal() if owns else session
        try:
            row = current.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id,
                    AuditVerificationOverride.source_area_id == area_id,
                    AuditVerificationOverride.source_section_id == section_id,
                    AuditVerificationOverride.source_control_point_id == control_point_id,
                )
            ).first()
            if row is None:
                row = AuditVerificationOverride(
                    audit_id=audit_id,
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
        audit_id: int,
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
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id,
                    AuditVerificationOverride.source_area_id == area_id,
                    AuditVerificationOverride.source_section_id == section_id,
                    AuditVerificationOverride.source_control_point_id == control_point_id,
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

    def delete_for_audit(self, audit_id: int) -> int:
        with SessionLocal() as session:
            rows = session.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id
                )
            ).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count
