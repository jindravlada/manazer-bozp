from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport
from moduly.audity.repository.audit_program_final_report_repository import (
    AuditProgramFinalReportRepository,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.nastaveni.sluzby.settings_service import settings_service


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


class AuditProgramFinalReportService:
    def __init__(self) -> None:
        self.repository = AuditProgramFinalReportRepository()

    def get_for_program(self, audit_program_id: int) -> AuditProgramFinalReport | None:
        return self.repository.get_by_program_id(audit_program_id)

    def get_or_create_for_program(self, audit_program_id: int) -> AuditProgramFinalReport:
        if audit_program_service.get_program(audit_program_id) is None:
            raise ValueError(f"Program auditů {audit_program_id} neexistuje.")
        report = self.repository.get_by_program_id(audit_program_id)
        if report is not None:
            return report
        return AuditProgramFinalReport(
            audit_program_id=audit_program_id,
            silne_stranky="",
            hlavni_slabiny="",
            doporuceni_novy_program="",
            zpracoval="",
        )

    def get_last_preparer_worker_id(self) -> int | None:
        report = self.repository.get_last_with_preparer()
        if report is None:
            return None
        return report.zpracoval_worker_id

    def resolve_preparer_worker_id(self, report: AuditProgramFinalReport) -> int | None:
        if report.zpracoval_worker_id is not None:
            return report.zpracoval_worker_id

        name = _text(report.zpracoval)
        if not name:
            return None

        for worker in settings_service.get_workers(include_inactive=True):
            if _text(worker.display_name) == name:
                return worker.id
        return None

    def resolve_preparer_name(
        self,
        *,
        worker_id: int | None = None,
        fallback_name: str = "",
    ) -> str:
        if worker_id is not None:
            worker = settings_service.get_worker_by_id(worker_id)
            if worker is not None:
                return _text(worker.display_name)
        return _text(fallback_name)

    def save_for_program(
        self,
        audit_program_id: int,
        *,
        silne_stranky: str = "",
        hlavni_slabiny: str = "",
        doporuceni_novy_program: str = "",
        zpracoval_worker_id: int | None = None,
        zpracoval: str | None = None,
    ) -> AuditProgramFinalReport:
        report = self.get_or_create_for_program(audit_program_id)
        report.silne_stranky = _text(silne_stranky)
        report.hlavni_slabiny = _text(hlavni_slabiny)
        report.doporuceni_novy_program = _text(doporuceni_novy_program)
        report.zpracoval_worker_id = zpracoval_worker_id
        report.zpracoval = self.resolve_preparer_name(
            worker_id=zpracoval_worker_id,
            fallback_name=zpracoval if zpracoval is not None else "",
        )
        return self.repository.save(report)


audit_program_final_report_service = AuditProgramFinalReportService()
