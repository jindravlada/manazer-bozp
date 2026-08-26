from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from core.shared.section_summary import (
    normalize_section_summary_text,
    section_summary_key,
)
from moduly.audity.modely.audit_section_summary import AuditSectionSummary


class AuditSectionSummaryRepository:
    def get_for_audit(self, audit_id: int) -> list[AuditSectionSummary]:
        with get_session() as session:
            stmt = select(AuditSectionSummary).where(
                AuditSectionSummary.audit_id == int(audit_id)
            )
            rows = list(session.scalars(stmt))
            for row in rows:
                session.expunge(row)
            return rows

    def get_for_section(
        self,
        audit_id: int,
        *,
        process_id: str,
        section_id: str,
    ) -> AuditSectionSummary | None:
        process_id, section_id = section_summary_key(process_id, section_id)
        with get_session() as session:
            stmt = select(AuditSectionSummary).where(
                AuditSectionSummary.audit_id == int(audit_id),
                AuditSectionSummary.process_id == process_id,
                AuditSectionSummary.section_id == section_id,
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def upsert(
        self,
        audit_id: int,
        *,
        process_id: str,
        section_id: str,
        summary_text: str,
    ) -> AuditSectionSummary | None:
        process_id, section_id = section_summary_key(process_id, section_id)
        text = normalize_section_summary_text(summary_text)
        if not process_id or not section_id:
            return None
        now = datetime.now()
        with get_session() as session:
            stmt = select(AuditSectionSummary).where(
                AuditSectionSummary.audit_id == int(audit_id),
                AuditSectionSummary.process_id == process_id,
                AuditSectionSummary.section_id == section_id,
            )
            row = session.scalars(stmt).first()
            if not text.strip():
                if row is not None:
                    session.delete(row)
                    session.commit()
                return None
            if row is None:
                row = AuditSectionSummary(
                    audit_id=int(audit_id),
                    process_id=process_id,
                    section_id=section_id,
                    summary_text=text,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.summary_text = text
                row.updated_at = now
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def delete_for_audit(self, audit_id: int) -> None:
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(AuditSectionSummary).where(
                        AuditSectionSummary.audit_id == int(audit_id)
                    )
                )
            )
            for row in rows:
                session.delete(row)
            session.commit()
