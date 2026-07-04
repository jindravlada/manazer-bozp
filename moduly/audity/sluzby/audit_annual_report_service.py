from moduly.audity.modely.audit_annual_report import AuditAnnualReport
from moduly.audity.repository.audit_annual_report_repository import AuditAnnualReportRepository
from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service
from moduly.nastaveni.sluzby.settings_service import settings_service


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


class AuditAnnualReportService:
    def __init__(self) -> None:
        self.repository = AuditAnnualReportRepository()

    def get_for_year(self, year: int, *, audit_program_id: int | None = None) -> AuditAnnualReport | None:
        program_id = audit_annual_program_service.resolve_program_id(year, audit_program_id)
        return self.repository.get_by_year_and_program(year, program_id)

    def get_or_create_for_year(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> AuditAnnualReport:
        program_id = audit_annual_program_service.resolve_program_id(year, audit_program_id)
        report = self.repository.get_by_year_and_program(year, program_id)
        if report is not None:
            return report
        return AuditAnnualReport(
            year=year,
            audit_program_id=program_id,
            silne_stranky="",
            top_priority="",
            doporuceni_specialisty="",
            zpracoval="",
        )

    def get_last_preparer_worker_id(self) -> int | None:
        report = self.repository.get_last_with_preparer()
        if report is None:
            return None
        return report.zpracoval_worker_id

    def resolve_preparer_worker_id(self, report: AuditAnnualReport) -> int | None:
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

    def save_for_year(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
        silne_stranky: str = "",
        top_priority: str = "",
        doporuceni_specialisty: str = "",
        zpracoval_worker_id: int | None = None,
        zpracoval: str | None = None,
    ) -> AuditAnnualReport:
        program_id = audit_annual_program_service.resolve_program_id(year, audit_program_id)
        report = self.get_or_create_for_year(year, audit_program_id=program_id)
        report.audit_program_id = program_id
        report.silne_stranky = _text(silne_stranky)
        report.top_priority = _text(top_priority)
        report.doporuceni_specialisty = _text(doporuceni_specialisty)
        report.zpracoval_worker_id = zpracoval_worker_id
        report.zpracoval = self.resolve_preparer_name(
            worker_id=zpracoval_worker_id,
            fallback_name=zpracoval if zpracoval is not None else "",
        )
        return self.repository.save(report)


audit_annual_report_service = AuditAnnualReportService()
