"""Služba souhrnných sdělení za okruh auditu."""

from __future__ import annotations

from moduly.audity.modely.audit_section_summary import AuditSectionSummary
from moduly.audity.repository.audit_section_summary_repository import (
    AuditSectionSummaryRepository,
)


class AuditSectionSummaryService:
    def __init__(self) -> None:
        self.repository = AuditSectionSummaryRepository()

    def get_text(
        self,
        audit_id: int | None,
        *,
        process_id: str,
        section_id: str,
    ) -> str:
        if audit_id is None:
            return ""
        row = self.repository.get_for_section(
            int(audit_id),
            process_id=process_id,
            section_id=section_id,
        )
        return str(row.summary_text or "") if row is not None else ""

    def map_for_audit(self, audit_id: int | None) -> dict[tuple[str, str], str]:
        if audit_id is None:
            return {}
        mapping: dict[tuple[str, str], str] = {}
        for row in self.repository.get_for_audit(int(audit_id)):
            key = (str(row.process_id or "").strip(), str(row.section_id or "").strip())
            if key[0] and key[1]:
                mapping[key] = str(row.summary_text or "")
        return mapping

    def set_text(
        self,
        audit_id: int,
        *,
        process_id: str,
        section_id: str,
        summary_text: str,
        session=None,
    ) -> AuditSectionSummary | None:
        return self.repository.upsert(
            int(audit_id),
            process_id=process_id,
            section_id=section_id,
            summary_text=summary_text,
            session=session,
        )

    def delete_for_audit(self, audit_id: int) -> None:
        self.repository.delete_for_audit(int(audit_id))


audit_section_summary_service = AuditSectionSummaryService()
