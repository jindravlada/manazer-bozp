from dataclasses import dataclass, field
from datetime import date, datetime

from core.shared.constants import ENTITY_AUDITY
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.performance_evaluation_methodology_service import (
    EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
    PerformanceMethodologyContent,
    performance_evaluation_methodology_service,
)
from moduly.audity.constants import (
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_program import AuditProgram
from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_annual_export_context_service import (
    AuditAnnualHistoricalSeries,
    AuditAnnualMetrics,
    _MATURITY_LEGEND,
    _overall_rating_heading,
    audit_annual_export_context_service,
)
from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service
from moduly.audity.sluzby.audit_intro_export_service import audit_intro_export_service
from moduly.audity.sluzby.audit_process_maturity_history_service import (
    TREND_DECLINING,
    TREND_IMPROVING,
    TREND_STABLE,
    audit_process_maturity_history_service,
)
from moduly.audity.sluzby.audit_program_final_report_service import (
    audit_program_final_report_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.nastaveni.sluzby.settings_service import settings_service

_MATURITY_SCORES = {
    "kriticky": 1,
    "rizikovy": 2,
    "stabilni": 3,
    "vyspely": 4,
}

_PROGRAM_TREND_LABELS = {
    TREND_IMPROVING: "zlepšuje se",
    TREND_DECLINING: "zhoršuje se",
    TREND_STABLE: "beze změny",
}


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _fmt_period(date_from: date | None, date_to: date | None) -> str:
    if date_from is None or date_to is None:
        return "—"
    return (
        f"{date_from.day}. {date_from.month}. {date_from.year} – "
        f"{date_to.day}. {date_to.month}. {date_to.year}"
    )


def _program_years(program: AuditProgram) -> list[int]:
    if program.date_from is None or program.date_to is None:
        return []
    return list(range(program.date_from.year, program.date_to.year + 1))


def _bullet_lines(text: str, *, prefix: str = "✔") -> str:
    lines: list[str] = []
    for line in _text(text).split("\n"):
        item = line.strip()
        if not item:
            continue
        lines.append(item if item.startswith(prefix) else f"{prefix} {item}")
    return "\n".join(lines) if lines else "—"


@dataclass(frozen=True)
class AuditProgramFinalManualContent:
    silne_stranky: str
    hlavni_slabiny: str
    doporuceni_novy_program: str
    zpracoval: str

    def to_placeholders(self) -> dict[str, str]:
        return {
            "silne_stranky_text": _bullet_lines(self.silne_stranky),
            "hlavni_slabiny_text": _bullet_lines(self.hlavni_slabiny, prefix="•"),
            "doporuceni_novy_program_text": _text(self.doporuceni_novy_program) or "—",
            "zpracoval": _text(self.zpracoval) or "—",
        }


@dataclass(frozen=True)
class AuditProgramFinalReportContext:
    program: AuditProgram
    years: tuple[int, ...]
    metrics: AuditAnnualMetrics
    manual: AuditProgramFinalManualContent
    overall_assessment_text: str
    overall_rating_emoji: str
    program_fulfillment_text: str
    workplace_coverage_text: str
    process_coverage_text: str
    system_maturity_evolution_text: str
    process_evolution_text: str
    systemic_problems_text: str
    corrective_measures_text: str
    previous_program_comparison_text: str
    continuity_text: str
    continuity_previous_audits_text: str = ""
    appendices: dict[str, str] = field(default_factory=dict)

    def placeholder_values(self) -> dict[str, str]:
        employer = settings_service.get_employer()
        organization = _text(employer.name if employer else "")
        values = {
            "program_nazev": _text(self.program.name) or "—",
            "auditni_program_nazev": _text(self.program.name) or "—",
            "organizace": organization or "—",
            "zamestnavatel_nazev": organization,
            "obdobi": _fmt_period(self.program.date_from, self.program.date_to),
            "obdobi_programu": _fmt_period(self.program.date_from, self.program.date_to),
            "datum_vytvoreni": datetime.now().strftime("%d.%m.%Y"),
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
            "navaznost_programu_text": self.continuity_text,
            "navaznost_predchozi_audity_text": self.continuity_previous_audits_text,
            "celkove_hodnoceni_nadpis": _overall_rating_heading(self.overall_rating_emoji),
            "celkove_hodnoceni_text": self.overall_assessment_text,
            "splneni_programu_text": self.program_fulfillment_text,
            "pokryti_pracovist_text": self.workplace_coverage_text,
            "pokryti_procesu_text": self.process_coverage_text,
            "vyvoj_vyspelosti_systemu_text": self.system_maturity_evolution_text,
            "vyvoj_procesu_text": self.process_evolution_text,
            "systemicke_problemy_text": self.systemic_problems_text,
            "ucinnost_opatreni_text": self.corrective_measures_text,
            "srovnani_predchozi_program_text": self.previous_program_comparison_text,
        }
        values.update(self.manual.to_placeholders())
        values.update(self.appendices)
        return values


class AuditProgramFinalExportContextService:
    def __init__(self) -> None:
        self._annual = audit_annual_export_context_service
        self._repository = AuditProgramRepository()

    def build(
        self,
        program_id: int,
        *,
        report: AuditProgramFinalReport | None = None,
    ) -> AuditProgramFinalReportContext:
        program = audit_program_service.get_program(program_id)
        if program is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")

        saved = report or audit_program_final_report_service.get_or_create_for_program(program_id)
        years = tuple(_program_years(program))
        audits = self._audits_for_program(program_id)
        reference_year = years[-1] if years else date.today().year
        metrics = self._annual._compute_metrics(reference_year, audits)
        attention_problems = self._annual._collect_attention_problems(audits)
        severity = self._annual._compute_severity_assessment(audits, metrics, attention_problems)
        history = self._load_program_history(program_id, years, reference_year)
        comparison = self._annual._build_comparison(reference_year, metrics, history)
        overall_rating = self._annual._determine_overall_rating(
            metrics,
            severity,
            comparison,
            history,
        )
        methodology = performance_evaluation_methodology_service.build(
            self._annual._performance_signals(
                metrics,
                severity,
                overall_rating,
                comparison,
                history,
            ),
            domain=EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
        )
        process_maturity = self._annual._build_process_maturity(
            audits,
            year=reference_year,
            audit_program_id=program_id,
            severity_index=self._annual._build_severity_index(),
        )
        manual = AuditProgramFinalManualContent(
            silne_stranky=saved.silne_stranky,
            hlavni_slabiny=saved.hlavni_slabiny,
            doporuceni_novy_program=saved.doporuceni_novy_program,
            zpracoval=_text(saved.zpracoval),
        )
        appendices = self._annual._build_appendices(
            audits,
            methodology_text=(
                f"{methodology.appendix_text}\n\n{_MATURITY_LEGEND}"
            ),
        )
        return AuditProgramFinalReportContext(
            program=program,
            years=years,
            metrics=metrics,
            manual=manual,
            overall_assessment_text=self._annual._overall_assessment_text(
                severity,
                overall_rating,
                PerformanceMethodologyContent(
                    appendix_text=methodology.appendix_text,
                    expert_justification=methodology.expert_justification,
                    reliability=methodology.reliability,
                ),
                process_maturity,
            ),
            overall_rating_emoji=overall_rating.emoji,
            program_fulfillment_text=self._build_program_fulfillment_text(program),
            workplace_coverage_text=self._build_workplace_coverage_text(program_id),
            process_coverage_text=self._build_process_coverage_text(program_id),
            system_maturity_evolution_text=self._build_system_maturity_evolution_text(
                program_id,
                years,
            ),
            process_evolution_text=self._build_process_evolution_text(program_id, years),
            systemic_problems_text=self._annual._build_systemic_problems_text(attention_problems),
            corrective_measures_text=self._annual._build_corrective_measures_text(
                metrics,
                severity,
            ),
            previous_program_comparison_text=self._build_previous_program_comparison(
                program,
                attention_problems,
                years,
            ),
            continuity_text=self._build_continuity_text(program),
            continuity_previous_audits_text=(
                audit_intro_export_service.build_continuity_text_for_audits(audits)
            ),
            appendices=appendices.to_placeholders(),
        )

    def _audits_for_program(self, program_id: int) -> list[Audit]:
        return audit_annual_program_service.filter_audits_for_program(
            audit_service.get_all(),
            program_id=program_id,
        )

    def _load_program_history(
        self,
        program_id: int,
        years: tuple[int, ...],
        reference_year: int,
    ) -> AuditAnnualHistoricalSeries:
        metrics_by_year: dict[int, AuditAnnualMetrics] = {}
        for year in years:
            audits = audit_annual_program_service.filter_audits_for_program(
                audit_service.get_for_year(year),
                program_id=program_id,
            )
            if audits:
                metrics_by_year[year] = self._annual._compute_metrics(year, audits)
        return AuditAnnualHistoricalSeries(
            target_year=reference_year,
            available_years=years,
            metrics_by_year=metrics_by_year,
        )

    def _build_continuity_text(self, program: AuditProgram) -> str:
        previous_id = program.previous_program_id
        if previous_id is None:
            return (
                "Předchozí auditní program není evidován. "
                "Tento program tvoří referenční bázi pro další období."
            )
        previous = audit_program_service.get_program(previous_id)
        if previous is None:
            return "Navazuje na program, který již není v evidenci."
        return (
            f"Navazuje na program: {previous.name or '—'}\n"
            f"Období předchozího programu: {_fmt_period(previous.date_from, previous.date_to)}"
        )

    def _build_program_fulfillment_text(self, program: AuditProgram) -> str:
        visits = [
            visit
            for visit in self._repository.list_visits(program.id)
            if visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
        ]
        if not visits:
            return "V programu nejsou evidovány plánované návštěvy auditů."
        completed = sum(
            1
            for visit in visits
            if visit.status == AUDIT_PROGRAM_VISIT_STATUS_COMPLETED or visit.audit_id is not None
        )
        coverage = audit_program_service.get_program_coverage(program.id)
        completion = coverage.completion_percent if coverage is not None else 0.0
        return (
            f"Program {program.name or '—'} pokrývá období "
            f"{_fmt_period(program.date_from, program.date_to)}.\n"
            f"Dokončené návštěvy: {completed} z {len(visits)} "
            f"({completed / len(visits) * 100:.0f} %).\n"
            f"Plnění řídicích procesů v návštěvách: {completion:.0f} %."
        )

    def _build_workplace_coverage_text(self, program_id: int) -> str:
        coverage = audit_program_service.get_program_coverage(program_id)
        if coverage is None:
            return "—"
        lines = [
            f"Počet aktivních pracovišť v programu: {coverage.workplace_count}.",
            f"Plánované návštěvy: {coverage.visit_count}, dokončené: {coverage.completed_visit_count}.",
        ]
        missing_workplaces = [
            item
            for item in coverage.missing_by_workplace
            if item.missing_process_ids
        ]
        if missing_workplaces:
            lines.append("Pracoviště s neúplným pokrytím řídicích procesů:")
            for item in missing_workplaces[:10]:
                lines.append(
                    f"• {item.workplace_name or '—'} – chybí {len(item.missing_process_ids)} procesů"
                )
        else:
            lines.append("Všechna pracoviště mají přiřazené plánované řídicí procesy.")
        return "\n".join(lines)

    def _build_process_coverage_text(self, program_id: int) -> str:
        coverage = audit_program_service.get_program_coverage(program_id)
        if coverage is None:
            return "—"
        return (
            f"Plánované řízení procesů v návštěvách: {coverage.planned_process_count}.\n"
            f"Dokončené: {coverage.completed_process_count} "
            f"({coverage.completion_percent:.0f} %)."
        )

    def _build_system_maturity_evolution_text(
        self,
        program_id: int,
        years: tuple[int, ...],
    ) -> str:
        if not years:
            return "Pro program není definováno období pro sledování vyspělosti."
        lines: list[str] = []
        levels: list[str] = []
        for year in years:
            snapshots = audit_process_maturity_history_service.get_year_snapshots(
                year,
                audit_program_id=program_id,
            )
            if not snapshots:
                continue
            level, emoji, label = audit_process_maturity_history_service.average_maturity_level(
                [item.maturity_level for item in snapshots]
            )
            levels.append(level)
            lines.append(f"{year}   {emoji} {label}")
        if not lines:
            return "Historie vyspělosti systému řízení zatím není evidována."
        trend = self._resolve_program_trend(levels)
        lines.append(f"Trend: {trend}")
        return "\n".join(lines)

    def _build_process_evolution_text(
        self,
        program_id: int,
        years: tuple[int, ...],
    ) -> str:
        if not years:
            return "—"
        process_ids: set[str] = set()
        for year in years:
            for snapshot in audit_process_maturity_history_service.get_year_snapshots(
                year,
                audit_program_id=program_id,
            ):
                process_ids.add(snapshot.process_id)

        blocks: list[str] = []
        for process_id in sorted(process_ids):
            history = audit_process_maturity_history_service.get_process_history(
                process_id,
                audit_program_id=program_id,
            )
            year_records = [item for item in history if item.year in years]
            if not year_records:
                continue
            year_records = sorted(year_records, key=lambda item: item.year)
            lines = [year_records[0].process_name]
            maturity_labels: list[str] = []
            for record in year_records:
                lines.append(f"{record.year}   {record.maturity_emoji} {record.maturity_label}")
                maturity_labels.append(record.maturity_level)
            lines.append(f"Trend: {self._resolve_program_trend(maturity_labels)}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) if blocks else "Historie vyspělosti procesů zatím není evidována."

    def _build_previous_program_comparison(
        self,
        program: AuditProgram,
        current_problems: list,
        years: tuple[int, ...],
    ) -> str:
        previous_id = program.previous_program_id
        if previous_id is None:
            return (
                "Předchozí auditní program není evidován. "
                "Tento program tvoří referenční bázi pro další období."
            )

        previous = audit_program_service.get_program(previous_id)
        if previous is None:
            return "Předchozí program není v evidenci – srovnání není možné."

        current_period = _fmt_period(program.date_from, program.date_to)
        previous_period = _fmt_period(previous.date_from, previous.date_to)
        current_levels = self._final_year_maturity_levels(program.id, years)
        previous_years = tuple(_program_years(previous))
        previous_levels = self._final_year_maturity_levels(previous.id, previous_years)

        _, current_emoji, current_label = (
            audit_process_maturity_history_service.average_maturity_level(current_levels)
            if current_levels
            else ("stabilni", "🟡", "Stabilní")
        )
        _, previous_emoji, previous_label = (
            audit_process_maturity_history_service.average_maturity_level(previous_levels)
            if previous_levels
            else ("stabilni", "🟡", "Stabilní")
        )

        current_nevyhovuje = self._count_nevyhovuje(program.id)
        previous_nevyhovuje = self._count_nevyhovuje(previous.id)
        current_repeated = sum(1 for problem in current_problems if problem.count > 1)
        previous_problems = self._annual._collect_attention_problems(
            self._audits_for_program(previous.id)
        )
        previous_repeated = sum(1 for problem in previous_problems if problem.count > 1)
        repeated_trend = self._repeated_problems_trend(previous_repeated, current_repeated)

        return (
            f"Předchozí program: {previous_period}\n"
            f"Aktuální program: {current_period}\n\n"
            f"Průměrná vyspělost:\n"
            f"{previous_emoji} {previous_label} → {current_emoji} {current_label}\n\n"
            f"Počet systémových neshod:\n"
            f"{previous_nevyhovuje} → {current_nevyhovuje}\n\n"
            f"Opakované problémy:\n"
            f"{repeated_trend}"
        )

    def _final_year_maturity_levels(
        self,
        program_id: int,
        years: tuple[int, ...],
    ) -> list[str]:
        for year in reversed(years):
            snapshots = audit_process_maturity_history_service.get_year_snapshots(
                year,
                audit_program_id=program_id,
            )
            if snapshots:
                return [item.maturity_level for item in snapshots]
        return []

    def _count_nevyhovuje(self, program_id: int) -> int:
        total = 0
        for audit in self._audits_for_program(program_id):
            stats = control_activity_statistics_service.compute(ENTITY_AUDITY, audit.id)
            total += stats.ratings_nevyhovuje
        return total

    @staticmethod
    def _resolve_program_trend(levels: list[str]) -> str:
        if len(levels) < 2:
            return "bez srovnání"
        first = _MATURITY_SCORES.get(levels[0], 2)
        last = _MATURITY_SCORES.get(levels[-1], 2)
        if last > first:
            return _PROGRAM_TREND_LABELS[TREND_IMPROVING]
        if last < first:
            return _PROGRAM_TREND_LABELS[TREND_DECLINING]
        return _PROGRAM_TREND_LABELS[TREND_STABLE]

    @staticmethod
    def _repeated_problems_trend(previous_count: int, current_count: int) -> str:
        if current_count < previous_count:
            return "snížení"
        if current_count > previous_count:
            return "zhoršení"
        return "beze změny"


audit_program_final_export_context_service = AuditProgramFinalExportContextService()
