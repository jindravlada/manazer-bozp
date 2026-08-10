from sqlalchemy import select

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
    ) -> AuditVerificationOverride:
        with SessionLocal() as session:
            row = session.scalars(
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
                session.add(row)
            else:
                row.override_verification_type = override_verification_type
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def delete(
        self,
        audit_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> bool:
        with SessionLocal() as session:
            row = session.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit_id,
                    AuditVerificationOverride.source_area_id == area_id,
                    AuditVerificationOverride.source_section_id == section_id,
                    AuditVerificationOverride.source_control_point_id == control_point_id,
                )
            ).first()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

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
