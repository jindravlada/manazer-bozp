from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport
from moduly.proverky.repository.bozp_annual_report_repository import BozpAnnualReportRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


class BozpAnnualReportService:
    def __init__(self) -> None:
        self.repository = BozpAnnualReportRepository()

    def get_for_year(self, year: int) -> BozpAnnualReport | None:
        return self.repository.get_by_year(year)

    def get_or_create_for_year(self, year: int) -> BozpAnnualReport:
        report = self.repository.get_by_year(year)
        if report is not None:
            return report
        return BozpAnnualReport(
            year=year,
            zpracoval=self.default_specialist_name(),
        )

    def save_for_year(
        self,
        year: int,
        *,
        silne_stranky: str = "",
        top_priority: str = "",
        doporuceni_specialisty: str = "",
        zpracoval: str | None = None,
    ) -> BozpAnnualReport:
        report = self.get_or_create_for_year(year)
        report.silne_stranky = _text(silne_stranky)
        report.top_priority = _text(top_priority)
        report.doporuceni_specialisty = _text(doporuceni_specialisty)
        if zpracoval is not None:
            report.zpracoval = _text(zpracoval)
        elif not report.zpracoval:
            report.zpracoval = self.default_specialist_name()
        return self.repository.save(report)

    def default_specialist_name(self) -> str:
        workers = settings_service.get_workers_for_controls()
        if len(workers) == 1:
            worker = workers[0]
            return _text(f"{worker.first_name} {worker.last_name}".strip())
        if workers:
            worker = sorted(workers, key=lambda item: (item.last_name, item.first_name))[0]
            return _text(f"{worker.first_name} {worker.last_name}".strip())
        return ""


bozp_annual_report_service = BozpAnnualReportService()
