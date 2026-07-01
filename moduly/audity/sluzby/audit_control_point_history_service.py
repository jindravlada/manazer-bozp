from dataclasses import dataclass
from datetime import datetime

from core.shared.modely.finding import Finding
from moduly.audity.repository.audit_control_point_history_repository import (
    AuditControlPointHistoryRepository,
)
from moduly.audity.sluzby.audit_service import audit_service


@dataclass(frozen=True)
class AuditQuestionHistoryEntry:
    recorded_at: datetime | None
    result: str
    note: str
    audit_id: int
    audit_number: str
    workplace_id: int | None
    workplace_name: str
    finding: Finding | None


class AuditControlPointHistoryService:
    def __init__(self):
        self.repository = AuditControlPointHistoryRepository()

    def get_workplace_history(
        self,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
        workplace_id: int | None,
        exclude_audit_id: int | None = None,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryEntry]:
        if not question_id or workplace_id is None:
            return []

        return self._to_entries(
            self.repository.get_for_control_point(
                area_label=process_label,
                section_label=criterion_label,
                control_point_id=question_id,
                workplace_id=workplace_id,
                exclude_audit_id=exclude_audit_id,
                limit=limit,
            ),
            process_label=process_label,
            criterion_label=criterion_label,
            question_id=question_id,
        )

    def get_shared_experiences(
        self,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
        exclude_audit_id: int | None = None,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryEntry]:
        if not question_id:
            return []

        return self._to_entries(
            self.repository.get_shared_experiences(
                area_label=process_label,
                section_label=criterion_label,
                control_point_id=question_id,
                exclude_audit_id=exclude_audit_id,
                limit=limit,
            ),
            process_label=process_label,
            criterion_label=criterion_label,
            question_id=question_id,
        )

    def get_similar_elsewhere_history(
        self,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
        workplace_id: int | None,
        exclude_audit_id: int | None = None,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryEntry]:
        if not question_id:
            return []

        return self._to_entries(
            self.repository.get_for_control_point(
                area_label=process_label,
                section_label=criterion_label,
                control_point_id=question_id,
                exclude_workplace_id=workplace_id,
                exclude_audit_id=exclude_audit_id,
                only_with_workplace=True,
                limit=limit,
            ),
            process_label=process_label,
            criterion_label=criterion_label,
            question_id=question_id,
        )

    def _to_entries(
        self,
        records,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
    ) -> list[AuditQuestionHistoryEntry]:
        entries: list[AuditQuestionHistoryEntry] = []
        for record in records:
            finding = audit_service.finding_for_control_point(
                record.audit.id,
                process_label=process_label,
                criterion_label=criterion_label,
                question_id=question_id,
            )
            entries.append(
                AuditQuestionHistoryEntry(
                    recorded_at=record.control_result.recorded_at,
                    result=record.control_result.result,
                    note=record.control_result.note or "",
                    audit_id=record.audit.id,
                    audit_number=str(record.audit.number or "").strip(),
                    workplace_id=record.audit.workplace_id,
                    workplace_name=str(record.audit.workplace_name or "").strip(),
                    finding=finding,
                )
            )
        return entries

    def get_history(
        self,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
        workplace_id: int | None = None,
        exclude_audit_id: int | None = None,
        limit: int = 5,
    ) -> list[AuditQuestionHistoryEntry]:
        """Zpětná kompatibilita — historie aktuálního auditovaného provozu."""
        return self.get_workplace_history(
            process_label=process_label,
            criterion_label=criterion_label,
            question_id=question_id,
            workplace_id=workplace_id,
            exclude_audit_id=exclude_audit_id,
            limit=limit,
        )


audit_control_point_history_service = AuditControlPointHistoryService()
