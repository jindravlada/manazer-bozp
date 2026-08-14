import re
from dataclasses import dataclass, field
from datetime import date, datetime

from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_AUDITY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.shared.sluzby.performance_evaluation_methodology_service import (
    DATA_REPRESENTATIVENESS_LABEL,
    EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
    PerformanceEvaluationExplanation,
    PerformanceEvaluationInput,
    PerformanceMethodologyContent,
    PerformanceRatingResult,
    RATING_GREEN,
    RATING_RED,
    RATING_YELLOW,
    SEVERITY_LEVEL_CRITICAL,
    SEVERITY_LEVEL_HIGH,
    SEVERITY_LEVEL_LOW,
    SEVERITY_LEVEL_MEDIUM,
    SEVERITY_WEIGHTS,
    performance_evaluation_methodology_service,
)
from moduly.audity.sluzby.audit_attention_problem_normalizer import normalize_attention_problem
from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service
from moduly.audity.sluzby.audit_process_maturity_history_service import (
    audit_process_maturity_history_service,
)
from moduly.audity.constants import (
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
    CONTROL_POINT_SEVERITY_DEFAULT,
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_NIZKA,
    CONTROL_POINT_SEVERITY_STREDNI,
    CONTROL_POINT_SEVERITY_VYSOKA,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_annual_report import AuditAnnualReport
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_question_source_service import (
    AuditQuestionSourceError,
    audit_question_source_service,
)
from moduly.audity.sluzby.audit_question_snapshot_service import snapshot_key
from moduly.audity.sluzby.audit_service import audit_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.sluzby.task_service import task_service

_OPEN_FINDING_STATUSES = frozenset({FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU})

_SEVERITY_ORDER = (
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_VYSOKA,
    CONTROL_POINT_SEVERITY_STREDNI,
    CONTROL_POINT_SEVERITY_NIZKA,
)

_SEVERITY_LABELS = {
    CONTROL_POINT_SEVERITY_NIZKA: "Nízká",
    CONTROL_POINT_SEVERITY_STREDNI: "Střední",
    CONTROL_POINT_SEVERITY_VYSOKA: "Vysoká",
    CONTROL_POINT_SEVERITY_KRITICKA: "Kritická",
}

_MATURITY_LEVELS = (
    ("kriticky", "🔴", "Kritický"),
    ("rizikovy", "🟠", "Rizikový"),
    ("stabilni", "🟡", "Stabilní"),
    ("vyspely", "🟢", "Vyspělý"),
)

_MATURITY_LEGEND = """Legenda vyspělosti řídicích procesů:

🟢 Vyspělý
Proces je dlouhodobě stabilní a nevykazuje významné systémové nedostatky.

🟡 Stabilní
Proces je funkční, ale existuje prostor ke zlepšení.

🟠 Rizikový
Proces vykazuje opakované nedostatky a vyžaduje zvýšenou pozornost.

🔴 Kritický
Proces není dostatečně řízen a představuje významné riziko pro účinnost systému řízení."""

_MATURITY_LEGEND_REFERENCE = (
    "Legenda úrovní vyspělosti řídicích procesů je uvedena v příloze."
)


def _overall_rating_heading(emoji: str) -> str:
    return f"CELKOVÉ HODNOCENÍ {emoji}"


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return _text(value)


def _per_activity(value: int, count: int) -> float | None:
    if count <= 0:
        return None
    return value / count


def _audit_count_label(count: int) -> str:
    if count == 1:
        return "1 audit"
    if 2 <= count <= 4:
        return f"{count} audity"
    return f"{count} auditů"


def _occurrence_group_heading(count: int) -> str:
    return f"Výskyt ({_audit_count_label(count)})"


def _format_labeled_block(
    index: int,
    title: str,
    fields: list[tuple[str, str]],
) -> str:
    lines = [f"{index}. {title}"]
    for label, value in fields:
        text = _text(value)
        if text:
            lines.append(f"   {label}: {text}")
    return "\n".join(lines)


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks)


def _first_line(text: str) -> str:
    for line in _text(text).split("\n"):
        if line.strip():
            return line.strip()
    return ""


def _format_ratio(label: str, value: float | None) -> str:
    if value is None:
        return f"{label}: —"
    return f"{label}: {value:.2f} / audit"


@dataclass(frozen=True)
class AuditAnnualNormalizedMetrics:
    neshody_per_audit: float | None
    doporuceni_per_audit: float | None
    zjisteni_per_audit: float | None
    opatreni_per_audit: float | None

    @classmethod
    def from_metrics(cls, metrics: "AuditAnnualMetrics") -> "AuditAnnualNormalizedMetrics":
        count = metrics.audits_count
        return cls(
            neshody_per_audit=_per_activity(metrics.ratings_nevyhovuje, count),
            doporuceni_per_audit=_per_activity(metrics.ratings_vyhovuje_s_doporucenim, count),
            zjisteni_per_audit=_per_activity(metrics.findings_count, count),
            opatreni_per_audit=_per_activity(metrics.measures_total, count),
        )


@dataclass(frozen=True)
class AuditAnnualMetrics:
    year: int
    audits_count: int
    workplaces_count: int
    processes_count: int
    control_points_count: int
    ratings_vyhovuje: int
    ratings_vyhovuje_s_doporucenim: int
    ratings_nevyhovuje: int
    findings_count: int
    measures_total: int
    measures_open: int
    measures_closed: int

    def normalized(self) -> AuditAnnualNormalizedMetrics:
        return AuditAnnualNormalizedMetrics.from_metrics(self)

    def to_lines(self, *, severity: "AuditAnnualSeverityMetrics | None" = None) -> list[str]:
        lines = [
            f"Počet auditů: {self.audits_count}",
            f"Počet pracovišť: {self.workplaces_count}",
            f"Počet řídicích procesů: {self.processes_count}",
            f"Počet auditních tvrzení: {self.control_points_count}",
            f"Vyhovuje: {self.ratings_vyhovuje}",
            f"Vyhovuje s doporučením: {self.ratings_vyhovuje_s_doporucenim}",
            f"Nevyhovuje: {self.ratings_nevyhovuje}",
            f"Zjištění: {self.findings_count}",
            f"Uložená opatření: {self.measures_total}",
            f"Otevřená opatření: {self.measures_open}",
        ]
        if severity is not None:
            lines.append("")
            lines.extend(severity.performance_lines(self))
        return lines

    def to_placeholders(
        self,
        *,
        severity: "AuditAnnualSeverityMetrics | None" = None,
        reliability_label: str | None = None,
    ) -> dict[str, str]:
        overview = "\n".join(self.to_lines(severity=severity))
        normalized = self.normalized()
        values = {
            "prehled_vysledku_text": overview,
            "statistika_text": overview,
            "pocet_auditu": str(self.audits_count),
            "pocet_pracovist": str(self.workplaces_count),
            "pocet_procesu": str(self.processes_count),
            "pocet_kontrolnich_bodu": str(self.control_points_count),
            "neshody_na_audit": (
                f"{normalized.neshody_per_audit:.2f}"
                if normalized.neshody_per_audit is not None
                else "—"
            ),
            "doporuceni_na_audit": (
                f"{normalized.doporuceni_per_audit:.2f}"
                if normalized.doporuceni_per_audit is not None
                else "—"
            ),
            "zjisteni_na_audit": (
                f"{normalized.zjisteni_per_audit:.2f}"
                if normalized.zjisteni_per_audit is not None
                else "—"
            ),
            "opatreni_na_audit": (
                f"{normalized.opatreni_per_audit:.2f}"
                if normalized.opatreni_per_audit is not None
                else "—"
            ),
        }
        if severity is not None:
            values.update(severity.to_placeholders())
            perf_lines = severity.performance_lines(self)
            if reliability_label:
                perf_lines.append(f"{DATA_REPRESENTATIVENESS_LABEL}: {reliability_label}")
            values["ukazatele_vykonnosti_text"] = "\n".join(perf_lines)
        return values


@dataclass(frozen=True)
class AuditAnnualSeverityMetrics:
    counts_by_severity: dict[str, int]
    weighted_score: int
    score_per_audit: float | None
    nevyhovuje_percent: float
    overdue_open_measures: int
    open_critical_count: int
    open_critical_overdue: int
    open_high_overdue: int
    repeated_problems_count: int

    def count_for(self, severity: str) -> int:
        return int(self.counts_by_severity.get(severity, 0))

    def performance_lines(self, metrics: AuditAnnualMetrics) -> list[str]:
        normalized = metrics.normalized()
        return [
            "Ukazatele výkonnosti systému řízení:",
            _format_ratio("Neshody", normalized.neshody_per_audit),
            _format_ratio("Doporučení", normalized.doporuceni_per_audit),
            _format_ratio("Zjištění", normalized.zjisteni_per_audit),
            _format_ratio("Opatření", normalized.opatreni_per_audit),
            f"Váhové skóre zjištění: {self.weighted_score}",
            _format_ratio("Váhové skóre", self.score_per_audit),
            f"Otevřená opatření po termínu: {self.overdue_open_measures}",
        ]

    def to_placeholders(self) -> dict[str, str]:
        return {
            "vahove_skore_zjisteni": str(self.weighted_score),
            "vahove_skore_na_audit": (
                f"{self.score_per_audit:.2f}" if self.score_per_audit is not None else "—"
            ),
            "otevrena_opatreni_po_terminu": str(self.overdue_open_measures),
            "podil_nevyhovuje_procent": f"{self.nevyhovuje_percent:.2f}",
        }


@dataclass(frozen=True)
class AuditAnnualAttentionProblem:
    label: str
    severity: str
    count: int

    def to_text(self) -> str:
        emoji = "🔴" if self.severity == CONTROL_RESULT_NEVYHOVUJE else "🟡"
        return f"{emoji} {self.label}"


@dataclass(frozen=True)
class AuditProcessMaturityItem:
    process_id: str
    process_name: str
    audits_count: int
    control_points_count: int
    weighted_score: int
    nevyhovuje_count: int
    doporuceni_count: int
    open_findings_count: int
    overdue_measures_count: int
    open_measures_count: int
    maturity_level: str
    maturity_label: str
    maturity_emoji: str
    summary: str
    trend_label: str = ""

    def to_text(self) -> str:
        trend_suffix = f"\n   Trend: {self.trend_label}" if self.trend_label else ""
        return (
            f"{self.maturity_emoji} {self.process_name}\n"
            f"   {self.nevyhovuje_count} neshod · "
            f"{self.doporuceni_count} doporučení · "
            f"{self.open_findings_count} otevřených zjištění{trend_suffix}\n"
            f"   {self.summary}"
        )


@dataclass(frozen=True)
class AuditProcessMaturityAssessment:
    items: tuple[AuditProcessMaturityItem, ...]
    text: str
    legend_text: str
    average_level: str
    average_emoji: str
    average_label: str
    trends_text: str

    def average_maturity_text(self) -> str:
        return f"{self.average_emoji} {self.average_label}"

    def strong_processes_text(self) -> str:
        lines = [item.process_name for item in self.items if item.maturity_level == "vyspely"]
        return "\n".join(f"✔ {line}" for line in lines) if lines else ""

    def weak_processes_text(self) -> str:
        lines = [
            item.process_name
            for item in self.items
            if item.maturity_level in {"kriticky", "rizikovy"}
        ]
        return "\n".join(f"• {line}" for line in lines) if lines else ""


@dataclass(frozen=True)
class AuditAnnualHistoricalSeries:
    target_year: int
    available_years: tuple[int, ...]
    metrics_by_year: dict[int, AuditAnnualMetrics]

    def previous_years(self) -> tuple[int, ...]:
        return tuple(year for year in self.available_years if year < self.target_year)

    def metrics_for_year(self, year: int) -> AuditAnnualMetrics | None:
        return self.metrics_by_year.get(year)


@dataclass(frozen=True)
class AuditAnnualYearComparison:
    has_previous_year: bool
    text: str

    def to_placeholders(self) -> dict[str, str]:
        return {"vyvoj_text": self.text}


@dataclass(frozen=True)
class AuditAnnualKeyInsights:
    text: str

    def to_placeholders(self) -> dict[str, str]:
        return {"klicove_poznatky_text": self.text or "—"}


@dataclass(frozen=True)
class AuditAnnualManualContent:
    silne_stranky: str
    top_priority: str
    doporuceni_specialisty: str
    zpracoval: str

    def to_placeholders(self) -> dict[str, str]:
        silne = _text(self.silne_stranky)
        silne_lines = []
        for line in silne.split("\n"):
            text = line.strip()
            if not text:
                continue
            silne_lines.append(text if text.startswith("✔") else f"✔ {text}")
        return {
            "silne_stranky_text": "\n".join(silne_lines) if silne_lines else "—",
            "top_priority_text": _text(self.top_priority) or "—",
            "doporuceni_specialisty": _text(self.doporuceni_specialisty) or "—",
            "doporuceni_auditora": _text(self.doporuceni_specialisty) or "—",
            "zpracoval": _text(self.zpracoval) or "—",
        }


@dataclass(frozen=True)
class AuditAnnualAppendices:
    audits_text: str
    findings_text: str
    measures_text: str
    open_measures_text: str
    methodology_text: str

    def to_placeholders(self) -> dict[str, str]:
        return {
            "priloha_auditu_text": self.audits_text,
            "priloha_zjisteni_text": self.findings_text,
            "priloha_opatreni_text": self.measures_text,
            "priloha_otevrena_opatreni_text": self.open_measures_text,
            "priloha_metodika_text": self.methodology_text,
        }


@dataclass(frozen=True)
class AuditAnnualReportContext:
    year: int
    audit_program_id: int | None
    audit_program_name: str
    metrics: AuditAnnualMetrics
    severity: AuditAnnualSeverityMetrics
    overall_rating: PerformanceRatingResult
    process_maturity: AuditProcessMaturityAssessment
    management_performance_text: str
    process_effectiveness_text: str
    systemic_problems_text: str
    corrective_measures_text: str
    program_fulfillment_text: str
    history: AuditAnnualHistoricalSeries
    comparison: AuditAnnualYearComparison
    key_insights: AuditAnnualKeyInsights
    methodology: PerformanceMethodologyContent
    appendices: AuditAnnualAppendices
    manual: AuditAnnualManualContent
    attention_areas_text: str
    overall_assessment_text: str
    extension_placeholders: dict[str, str] = field(default_factory=dict)

    def placeholder_values(self) -> dict[str, str]:
        employer = settings_service.get_employer()
        organization = _text(employer.name if employer else "")
        values = {
            "rok": str(self.year),
            "organizace": organization or "—",
            "zamestnavatel_nazev": organization,
            "obdobi": f"1. 1. {self.year} – 31. 12. {self.year}",
            "datum_vytvoreni": datetime.now().strftime("%d.%m.%Y"),
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
            "celkove_hodnoceni_nadpis": _overall_rating_heading(self.overall_rating.emoji),
            "celkove_hodnoceni_emoji": self.overall_rating.emoji,
            "celkove_hodnoceni_text": self.overall_assessment_text,
            "souhrn_text": self.overall_assessment_text,
            "oblasti_pozornosti_text": self.attention_areas_text,
            "vyspelost_systemu_text": self.process_maturity.text,
            "vyspelost_legenda_text": self.process_maturity.legend_text,
            "prumerna_vyspelost_systemu_text": self.process_maturity.average_maturity_text(),
            "vykonnost_systemu_text": self.management_performance_text,
            "ucinnost_procesu_text": self.process_effectiveness_text,
            "systemicke_problemy_text": self.systemic_problems_text,
            "ucinnost_opatreni_text": self.corrective_measures_text,
            "plneni_programu_text": self.program_fulfillment_text,
            "silne_procesy_text": self.process_maturity.strong_processes_text() or "—",
            "slabe_procesy_text": self.process_maturity.weak_processes_text() or "—",
            "auditni_program_nazev": self.audit_program_name or "—",
            "trendy_procesu_text": self.process_maturity.trends_text,
        }
        values.update(
            self.metrics.to_placeholders(
                severity=self.severity,
                reliability_label=self.methodology.reliability.label,
            )
        )
        values.update(self.comparison.to_placeholders())
        values.update(self.key_insights.to_placeholders())
        values.update(self.appendices.to_placeholders())
        values.update(self.manual.to_placeholders())
        values.update(self.methodology.to_placeholders())
        values.update(self.extension_placeholders)
        return values


class AuditAnnualExportContextService:
    def build(self, year: int, *, report: AuditAnnualReport | None = None) -> AuditAnnualReportContext:
        if year < 1900 or year > 3000:
            raise ValueError("Neplatný rok roční zprávy z auditů.")

        saved = report or audit_annual_report_service.get_or_create_for_year(year)
        program_id = saved.audit_program_id
        program = audit_annual_program_service.get_program_by_id(program_id)
        audits = audit_annual_program_service.filter_audits_for_program(
            audit_service.get_for_year(year),
            program_id=program_id,
        )
        history = self._load_historical_series(year, program_id=program_id)
        metrics = history.metrics_for_year(year) or self._compute_metrics(year, audits)
        attention_problems = self._collect_attention_problems(audits)
        comparison = self._build_comparison(year, metrics, history)
        manual = AuditAnnualManualContent(
            silne_stranky=saved.silne_stranky,
            top_priority=saved.top_priority,
            doporuceni_specialisty=saved.doporuceni_specialisty,
            zpracoval=_text(saved.zpracoval),
        )
        severity = self._compute_severity_assessment(audits, metrics, attention_problems)
        overall_rating = self._determine_overall_rating(metrics, severity, comparison, history)
        methodology = performance_evaluation_methodology_service.build(
            self._performance_signals(metrics, severity, overall_rating, comparison, history),
            domain=EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
        )
        methodology = PerformanceMethodologyContent(
            appendix_text=f"{methodology.appendix_text}\n\n{_MATURITY_LEGEND}",
            expert_justification=methodology.expert_justification,
            reliability=methodology.reliability,
        )
        process_maturity = self._build_process_maturity(
            audits,
            year=year,
            audit_program_id=program_id,
            severity_index=self._build_severity_index(),
        )
        program_fulfillment_text = self._build_program_fulfillment_text(year, program_id=program_id)
        management_performance_text = self._build_management_performance_text(
            metrics, severity, overall_rating, process_maturity
        )
        process_effectiveness_text = self._build_process_effectiveness_text(process_maturity)
        systemic_problems_text = self._build_systemic_problems_text(attention_problems)
        corrective_measures_text = self._build_corrective_measures_text(metrics, severity)
        appendices = self._build_appendices(
            audits,
            methodology_text=methodology.appendix_text,
        )
        key_insights = self._build_key_insights(
            metrics=metrics,
            manual=manual,
            attention_problems=attention_problems,
            process_maturity=process_maturity,
            history=history,
        )
        return AuditAnnualReportContext(
            year=year,
            audit_program_id=program_id,
            audit_program_name=_text(program.name if program else ""),
            metrics=metrics,
            severity=severity,
            overall_rating=overall_rating,
            process_maturity=process_maturity,
            management_performance_text=management_performance_text,
            process_effectiveness_text=process_effectiveness_text,
            systemic_problems_text=systemic_problems_text,
            corrective_measures_text=corrective_measures_text,
            program_fulfillment_text=program_fulfillment_text,
            history=history,
            comparison=comparison,
            key_insights=key_insights,
            methodology=methodology,
            appendices=appendices,
            manual=manual,
            attention_areas_text=self._attention_areas_text(attention_problems),
            overall_assessment_text=self._overall_assessment_text(
                severity, overall_rating, methodology, process_maturity
            ),
            extension_placeholders=self._reserved_extension_placeholders(history),
        )

    def build_evaluation_explanation(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> PerformanceEvaluationExplanation:
        report = audit_annual_report_service.get_or_create_for_year(
            year,
            audit_program_id=audit_program_id,
        )
        context = self.build(year, report=report)
        return performance_evaluation_methodology_service.build_explanation(
            self._performance_input_from(
                metrics=context.metrics,
                severity=context.severity,
                comparison=context.comparison,
                history=context.history,
            ),
            domain=EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
        )

    def _compute_metrics(self, year: int, audits: list[Audit]) -> AuditAnnualMetrics:
        workplaces: set[int | str] = set()
        processes: set[str] = set()
        control_points_count = 0
        ratings_vyhovuje = 0
        ratings_vyhovuje_s_doporucenim = 0
        ratings_nevyhovuje = 0
        findings_count = 0
        measures_total = 0
        measures_open = 0
        measures_closed = 0

        for audit in audits:
            if audit.workplace_id is not None:
                workplaces.add(audit.workplace_id)
            elif audit.workplace_name:
                workplaces.add(audit.workplace_name)

            stats = control_activity_statistics_service.compute(ENTITY_AUDITY, audit.id)
            control_points_count += stats.control_points_checked
            ratings_vyhovuje += stats.ratings_vyhovuje
            ratings_vyhovuje_s_doporucenim += stats.ratings_vyhovuje_s_doporucenim
            ratings_nevyhovuje += stats.ratings_nevyhovuje
            findings_count += stats.findings_total

            for row in control_result_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if row.source_area_id:
                    processes.add(str(row.source_area_id))

            for task in audit_service.get_tasks_for_audit(audit.id):
                measures_total += 1
                if task.computed_status in {"Ukončeno", "Zrušeno"}:
                    measures_closed += 1
                else:
                    measures_open += 1

        return AuditAnnualMetrics(
            year=year,
            audits_count=len(audits),
            workplaces_count=len(workplaces),
            processes_count=len(processes),
            control_points_count=control_points_count,
            ratings_vyhovuje=ratings_vyhovuje,
            ratings_vyhovuje_s_doporucenim=ratings_vyhovuje_s_doporucenim,
            ratings_nevyhovuje=ratings_nevyhovuje,
            findings_count=findings_count,
            measures_total=measures_total,
            measures_open=measures_open,
            measures_closed=measures_closed,
        )

    def _load_historical_series(
        self,
        target_year: int,
        *,
        program_id: int | None = None,
    ) -> AuditAnnualHistoricalSeries:
        years = {target_year}
        for audit in audit_service.get_all():
            if audit.audit_date is not None:
                years.add(audit.audit_date.year)
            elif audit.year is not None:
                years.add(audit.year)

        metrics_by_year: dict[int, AuditAnnualMetrics] = {}
        for year in years:
            audits = audit_annual_program_service.filter_audits_for_program(
                audit_service.get_for_year(year),
                program_id=program_id,
            )
            if audits:
                metrics_by_year[year] = self._compute_metrics(year, audits)

        return AuditAnnualHistoricalSeries(
            target_year=target_year,
            available_years=tuple(sorted(years)),
            metrics_by_year=metrics_by_year,
        )

    def _build_severity_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for process in audit_knowledge_service.get_processes(include_inactive=True):
            if not process.has_knowledge_file:
                continue
            knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
            if not knowledge:
                continue
            for section in self._iter_knowledge_sections(knowledge.get("sekce") or []):
                for item in audit_knowledge_service.get_audit_questions(section):
                    item_id = _text(item.get("id"))
                    if item_id:
                        index[item_id] = audit_knowledge_service.get_control_point_severity(item)
        return index

    @staticmethod
    def _iter_knowledge_sections(sections: list) -> list[dict]:
        collected: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            collected.append(section)
            nested = section.get("sekce") or []
            if isinstance(nested, list):
                collected.extend(AuditAnnualExportContextService._iter_knowledge_sections(nested))
        return collected

    def _resolve_severity(
        self,
        *,
        process_id: str = "",
        criterion_id: str = "",
        control_point_id: str = "",
        severity_index: dict[str, str] | None = None,
    ) -> str:
        index = severity_index or {}
        control_point_id = _text(control_point_id)
        if control_point_id and control_point_id in index:
            return index[control_point_id]

        process_id = _text(process_id)
        criterion_id = _text(criterion_id)
        if process_id and criterion_id and control_point_id:
            process = audit_knowledge_service.get_process_by_id(process_id, ensure=False)
            if process is not None:
                knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
                if knowledge:
                    for section in self._iter_knowledge_sections(knowledge.get("sekce") or []):
                        if _text(section.get("id")) != criterion_id:
                            continue
                        for item in audit_knowledge_service.get_audit_questions(section):
                            if _text(item.get("id")) == control_point_id:
                                return audit_knowledge_service.get_control_point_severity(item)
        return CONTROL_POINT_SEVERITY_DEFAULT

    @staticmethod
    def _is_overdue_task(task, *, today: date | None = None) -> bool:
        if task.computed_status in {"Ukončeno", "Zrušeno"}:
            return False
        due_date = getattr(task, "due_date", None)
        if due_date is None:
            return False
        reference = today or date.today()
        return due_date < reference

    def _compute_severity_assessment(
        self,
        audits: list[Audit],
        metrics: AuditAnnualMetrics,
        attention_problems: list[AuditAnnualAttentionProblem],
    ) -> AuditAnnualSeverityMetrics:
        severity_index = self._build_severity_index()
        counts = {severity: 0 for severity in _SEVERITY_ORDER}
        weighted_score = 0
        open_critical_count = 0
        open_critical_overdue = 0
        open_high_overdue = 0
        overdue_open_measures = 0
        seen_overdue_task_ids: set[int] = set()

        for audit in audits:
            snap_severity: dict[tuple[str, str, str], str] = {}
            try:
                source = audit_question_source_service.resolve_for_audit(
                    audit.id, audit=audit
                )
                if source.is_snapshot:
                    snap_severity = dict(source.severity_by_key)
            except AuditQuestionSourceError:
                snap_severity = {}

            for row in control_result_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if row.result not in (
                    CONTROL_RESULT_NEVYHOVUJE,
                    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                ):
                    continue
                key = snapshot_key(
                    row.source_area_id,
                    row.source_section_id,
                    row.source_control_point_id,
                )
                severity = snap_severity.get(key) or self._resolve_severity(
                    process_id=str(row.source_area_id or ""),
                    criterion_id=str(row.source_section_id or ""),
                    control_point_id=str(row.source_control_point_id or ""),
                    severity_index=severity_index,
                )
                counts[severity] = counts.get(severity, 0) + 1
                weighted_score += SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS[CONTROL_POINT_SEVERITY_STREDNI])

            for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if finding.status not in _OPEN_FINDING_STATUSES:
                    continue
                severity = self._resolve_severity(
                    control_point_id=str(finding.source_control_point_id or ""),
                    severity_index=severity_index,
                )
                if severity == CONTROL_POINT_SEVERITY_KRITICKA:
                    open_critical_count += 1
                if finding.task_id:
                    task = task_service.get_task_by_id(finding.task_id)
                    if task is None or task.id in seen_overdue_task_ids:
                        continue
                    if self._is_overdue_task(task):
                        seen_overdue_task_ids.add(task.id)
                        overdue_open_measures += 1
                        if severity == CONTROL_POINT_SEVERITY_KRITICKA:
                            open_critical_overdue += 1
                        elif severity == CONTROL_POINT_SEVERITY_VYSOKA:
                            open_high_overdue += 1

            for task in audit_service.get_tasks_for_audit(audit.id):
                if task.id in seen_overdue_task_ids:
                    continue
                if self._is_overdue_task(task):
                    seen_overdue_task_ids.add(task.id)
                    overdue_open_measures += 1

        nevyhovuje_percent = (
            metrics.ratings_nevyhovuje / metrics.control_points_count * 100
            if metrics.control_points_count > 0
            else 0.0
        )
        repeated_problems_count = sum(1 for problem in attention_problems if problem.count > 1)
        return AuditAnnualSeverityMetrics(
            counts_by_severity=counts,
            weighted_score=weighted_score,
            score_per_audit=_per_activity(weighted_score, metrics.audits_count),
            nevyhovuje_percent=nevyhovuje_percent,
            overdue_open_measures=overdue_open_measures,
            open_critical_count=open_critical_count,
            open_critical_overdue=open_critical_overdue,
            open_high_overdue=open_high_overdue,
            repeated_problems_count=repeated_problems_count,
        )

    def _performance_input_from(
        self,
        *,
        metrics: AuditAnnualMetrics,
        severity: AuditAnnualSeverityMetrics,
        comparison: AuditAnnualYearComparison,
        history: AuditAnnualHistoricalSeries,
    ) -> PerformanceEvaluationInput:
        workplaces = settings_service.get_workplaces(include_inactive=False)
        return PerformanceEvaluationInput(
            activities_count=metrics.audits_count,
            control_points_count=metrics.control_points_count,
            workplaces_covered_count=metrics.workplaces_count,
            workplaces_total_count=len(workplaces),
            noncompliance_count=metrics.ratings_nevyhovuje,
            noncompliance_percent=severity.nevyhovuje_percent,
            weighted_severity_score=severity.weighted_score,
            score_per_activity=severity.score_per_audit,
            measures_total=metrics.measures_total,
            measures_open=metrics.measures_open,
            measures_closed=metrics.measures_closed,
            open_critical_overdue=severity.open_critical_overdue,
            open_high_overdue=severity.open_high_overdue,
            open_critical_count=severity.open_critical_count,
            critical_findings_count=severity.count_for(CONTROL_POINT_SEVERITY_KRITICKA),
            high_findings_count=severity.count_for(CONTROL_POINT_SEVERITY_VYSOKA),
            repeated_problems_count=severity.repeated_problems_count,
            overdue_measures_count=severity.overdue_open_measures,
            comparison_summary=self._comparison_summary_for_methodology(metrics, comparison, history),
        )

    def _determine_overall_rating(
        self,
        metrics: AuditAnnualMetrics,
        severity: AuditAnnualSeverityMetrics,
        comparison: AuditAnnualYearComparison,
        history: AuditAnnualHistoricalSeries,
    ) -> PerformanceRatingResult:
        return performance_evaluation_methodology_service.determine_rating(
            self._performance_input_from(
                metrics=metrics,
                severity=severity,
                comparison=comparison,
                history=history,
            ),
            domain=EVALUATION_DOMAIN_AUDIT_MANAGEMENT,
        )

    def _performance_signals(
        self,
        metrics: AuditAnnualMetrics,
        severity: AuditAnnualSeverityMetrics,
        overall_rating: PerformanceRatingResult,
        comparison: AuditAnnualYearComparison,
        history: AuditAnnualHistoricalSeries,
    ):
        from core.shared.sluzby.performance_evaluation_methodology_service import (
            PerformanceEvaluationSignals,
        )

        inp = self._performance_input_from(
            metrics=metrics,
            severity=severity,
            comparison=comparison,
            history=history,
        )
        return PerformanceEvaluationSignals(
            activities_count=inp.activities_count,
            control_points_count=inp.control_points_count,
            workplaces_covered_count=inp.workplaces_covered_count,
            workplaces_total_count=inp.workplaces_total_count,
            noncompliance_percent=inp.noncompliance_percent,
            weighted_severity_score=inp.weighted_severity_score,
            score_per_activity=inp.score_per_activity,
            measures_open=inp.measures_open,
            measures_closed=inp.measures_closed,
            open_critical_overdue=inp.open_critical_overdue,
            open_high_overdue=inp.open_high_overdue,
            open_critical_count=inp.open_critical_count,
            high_severity_count=inp.high_findings_count,
            repeated_problems_count=inp.repeated_problems_count,
            overdue_measures_count=inp.overdue_measures_count,
            rating_level=overall_rating.level,
            rating_headline=overall_rating.headline,
            comparison_summary=inp.comparison_summary,
        )

    def _comparison_summary_for_methodology(
        self,
        metrics: AuditAnnualMetrics,
        comparison: AuditAnnualYearComparison,
        history: AuditAnnualHistoricalSeries,
    ) -> str:
        if not comparison.has_previous_year:
            return ""
        previous_metrics = history.metrics_for_year(metrics.year - 1)
        if previous_metrics is None or previous_metrics.audits_count == 0:
            return ""
        previous_normalized = previous_metrics.normalized()
        current_normalized = metrics.normalized()
        if (
            previous_normalized.neshody_per_audit is not None
            and current_normalized.neshody_per_audit is not None
            and current_normalized.neshody_per_audit < previous_normalized.neshody_per_audit
        ):
            return (
                "Přestože meziročně došlo ke snížení počtu neshod na jeden audit "
                f"z {previous_normalized.neshody_per_audit:.2f} "
                f"na {current_normalized.neshody_per_audit:.2f}"
            )
        return ""

    def _collect_attention_problems(self, audits: list[Audit]) -> list[AuditAnnualAttentionProblem]:
        grouped: dict[tuple[str, str], dict[str, object]] = {}
        for audit in audits:
            seen_in_audit: set[tuple[str, str]] = set()
            for row in control_result_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if row.result not in (
                    CONTROL_RESULT_NEVYHOVUJE,
                    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                ):
                    continue
                raw_label = self._attention_area_label(row)
                problem_label = normalize_attention_problem(raw_label)
                if not problem_label:
                    continue
                key = (row.result, problem_label.casefold())
                if key in seen_in_audit:
                    continue
                seen_in_audit.add(key)
                bucket = grouped.setdefault(
                    key,
                    {"label": problem_label, "severity": row.result, "count": 0},
                )
                bucket["count"] = int(bucket["count"]) + 1

        problems = [
            AuditAnnualAttentionProblem(
                label=str(bucket["label"]),
                severity=str(bucket["severity"]),
                count=int(bucket["count"]),
            )
            for bucket in grouped.values()
        ]
        problems.sort(key=lambda item: (-item.count, item.label.casefold()))
        return problems

    @staticmethod
    def _attention_area_label(row) -> str:
        for attr in ("source_control_point_label", "note", "source_section_label"):
            value = _text(getattr(row, attr, ""))
            if value:
                return value
        return "—"

    def _attention_areas_text(self, problems: list[AuditAnnualAttentionProblem]) -> str:
        if not problems:
            return "—"
        blocks: list[str] = []
        current_count: int | None = None
        current_items: list[str] = []
        for problem in problems:
            if current_count is None or problem.count != current_count:
                if current_items:
                    blocks.append("\n".join([_occurrence_group_heading(current_count), "", *current_items]))
                current_count = problem.count
                current_items = [problem.to_text()]
            else:
                current_items.append(problem.to_text())
        if current_items and current_count is not None:
            blocks.append("\n".join([_occurrence_group_heading(current_count), "", *current_items]))
        return "\n\n".join(blocks)

    def _build_process_maturity(
        self,
        audits: list[Audit],
        *,
        year: int,
        audit_program_id: int | None,
        severity_index: dict[str, str],
    ) -> AuditProcessMaturityAssessment:
        process_stats: dict[str, dict[str, object]] = {}
        process_names: dict[str, str] = {}
        process_labels: dict[str, str] = {}
        for process in audit_knowledge_service.get_processes():
            process_names[process.id] = process.nazev

        for audit in audits:
            audit_processes: set[str] = set()
            control_point_process: dict[str, str] = {}
            for row in control_result_service.get_for_entity(ENTITY_AUDITY, audit.id):
                process_id = str(row.source_area_id or "").strip()
                if not process_id:
                    continue
                control_point_id = _text(row.source_control_point_id)
                if control_point_id:
                    control_point_process[control_point_id] = process_id
                if row.source_area_label:
                    process_labels[process_id] = _text(row.source_area_label)
                audit_processes.add(process_id)
                bucket = process_stats.setdefault(
                    process_id,
                    {
                        "nevyhovuje": 0,
                        "doporuceni": 0,
                        "open_findings": 0,
                        "overdue_measures": 0,
                        "open_measures": 0,
                        "control_points": 0,
                        "weighted_score": 0,
                        "audits": set(),
                    },
                )
                bucket["control_points"] = int(bucket["control_points"]) + 1
                if row.result in (
                    CONTROL_RESULT_NEVYHOVUJE,
                    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                ):
                    severity = self._resolve_severity(
                        process_id=process_id,
                        criterion_id=str(row.source_section_id or ""),
                        control_point_id=control_point_id,
                        severity_index=severity_index,
                    )
                    bucket["weighted_score"] = int(bucket["weighted_score"]) + SEVERITY_WEIGHTS.get(
                        severity,
                        SEVERITY_WEIGHTS[CONTROL_POINT_SEVERITY_STREDNI],
                    )
                if row.result == CONTROL_RESULT_NEVYHOVUJE:
                    bucket["nevyhovuje"] = int(bucket["nevyhovuje"]) + 1
                elif row.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM:
                    bucket["doporuceni"] = int(bucket["doporuceni"]) + 1

            for process_id in audit_processes:
                process_stats[process_id]["audits"].add(audit.id)

            for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if finding.status not in _OPEN_FINDING_STATUSES:
                    continue
                process_id = control_point_process.get(_text(finding.source_control_point_id), "")
                if process_id in process_stats:
                    process_stats[process_id]["open_findings"] = (
                        int(process_stats[process_id]["open_findings"]) + 1
                    )
                if finding.task_id:
                    task = task_service.get_task_by_id(finding.task_id)
                    if task and self._is_overdue_task(task) and process_id in process_stats:
                        process_stats[process_id]["overdue_measures"] = (
                            int(process_stats[process_id]["overdue_measures"]) + 1
                        )

            for task in audit_service.get_tasks_for_audit(audit.id):
                if task.computed_status in {"Ukončeno", "Zrušeno"}:
                    continue
                process_id = ""
                for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit.id):
                    if finding.task_id == task.id:
                        process_id = control_point_process.get(
                            _text(finding.source_control_point_id),
                            "",
                        )
                        break
                if process_id in process_stats:
                    process_stats[process_id]["open_measures"] = (
                        int(process_stats[process_id]["open_measures"]) + 1
                    )

        items: list[AuditProcessMaturityItem] = []
        maturity_order = {level: index for index, (level, _, _) in enumerate(_MATURITY_LEVELS)}
        for process_id, bucket in process_stats.items():
            nevyhovuje = int(bucket["nevyhovuje"])
            doporuceni = int(bucket["doporuceni"])
            open_findings = int(bucket["open_findings"])
            overdue = int(bucket["overdue_measures"])
            open_measures = int(bucket["open_measures"])
            audits_count = len(bucket["audits"])
            control_points_count = int(bucket["control_points"])
            weighted_score = int(bucket["weighted_score"])
            process_name = process_names.get(process_id, process_labels.get(process_id, process_id))
            level, emoji, label = self._resolve_maturity_level(
                nevyhovuje=nevyhovuje,
                doporuceni=doporuceni,
                open_findings=open_findings,
                overdue_measures=overdue,
            )
            summary = self._maturity_summary(level, nevyhovuje, doporuceni, open_findings, overdue)
            snapshot = audit_process_maturity_history_service.record_snapshot(
                year=year,
                audit_program_id=audit_program_id,
                process_id=process_id,
                process_name=process_name,
                maturity_level=level,
                maturity_emoji=emoji,
                maturity_label=label,
                weighted_score=weighted_score,
                audits_count=audits_count,
                control_points_count=control_points_count,
                nevyhovuje_count=nevyhovuje,
                doporuceni_count=doporuceni,
                open_measures_count=open_measures,
                overdue_measures_count=overdue,
            )
            items.append(
                AuditProcessMaturityItem(
                    process_id=process_id,
                    process_name=process_name,
                    audits_count=audits_count,
                    control_points_count=control_points_count,
                    weighted_score=weighted_score,
                    nevyhovuje_count=nevyhovuje,
                    doporuceni_count=doporuceni,
                    open_findings_count=open_findings,
                    overdue_measures_count=overdue,
                    open_measures_count=open_measures,
                    maturity_level=level,
                    maturity_label=label,
                    maturity_emoji=emoji,
                    summary=summary,
                    trend_label=snapshot.trend_label,
                )
            )

        items.sort(
            key=lambda item: (
                maturity_order.get(item.maturity_level, 99),
                -item.nevyhovuje_count,
                item.process_name.casefold(),
            )
        )
        average_level, average_emoji, average_label = audit_process_maturity_history_service.average_maturity_level(
            [item.maturity_level for item in items]
        )
        trends_text = audit_process_maturity_history_service.trends_text_for_year(
            year,
            audit_program_id=audit_program_id,
        )
        process_lines = "\n\n".join(item.to_text() for item in items) if items else "—"
        return AuditProcessMaturityAssessment(
            items=tuple(items),
            text=process_lines,
            legend_text=_MATURITY_LEGEND_REFERENCE,
            average_level=average_level,
            average_emoji=average_emoji,
            average_label=average_label,
            trends_text=trends_text,
        )

    @staticmethod
    def _resolve_maturity_level(
        *,
        nevyhovuje: int,
        doporuceni: int,
        open_findings: int,
        overdue_measures: int,
    ) -> tuple[str, str, str]:
        if nevyhovuje >= 2 or (nevyhovuje >= 1 and overdue_measures >= 1):
            return _MATURITY_LEVELS[0]
        if nevyhovuje >= 1 or overdue_measures >= 1 or open_findings >= 2:
            return _MATURITY_LEVELS[1]
        if doporuceni >= 1 or open_findings >= 1:
            return _MATURITY_LEVELS[2]
        return _MATURITY_LEVELS[3]

    @staticmethod
    def _maturity_summary(
        level: str,
        nevyhovuje: int,
        doporuceni: int,
        open_findings: int,
        overdue: int,
    ) -> str:
        if level == "kriticky":
            return "Řídicí proces vykazuje závažné nedostatky ovlivňující účinnost systému řízení."
        if level == "rizikovy":
            return "Řídicí proces vyžaduje nápravu nebo posílení kontrolních mechanismů."
        if level == "stabilni":
            return "Řídicí proces je funkční, avšak s prostorem pro zlepšení sledování opatření."
        if doporuceni:
            return "Řídicí proces je vyspělý, drobná doporučení nenarušují celkovou účinnost."
        return "Řídicí proces je vyspělý a stabilně plní svou roli v systému řízení."

    def _build_program_fulfillment_text(self, year: int, *, program_id: int | None = None) -> str:
        repository = AuditProgramRepository()
        lines: list[str] = []
        programs = audit_program_service.list_programs()
        if program_id is not None:
            programs = [program for program in programs if program.id == program_id]
        for program in programs:
            visits = [
                visit
                for visit in repository.list_visits(program.id)
                if visit.planned_year == year and visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
            ]
            if not visits:
                continue
            completed = sum(
                1
                for visit in visits
                if visit.status == AUDIT_PROGRAM_VISIT_STATUS_COMPLETED or visit.audit_id is not None
            )
            lines.append(
                f"• {program.name}: {completed} z {len(visits)} plánovaných auditů v roce {year} dokončeno"
            )
        return "\n".join(lines) if lines else "V roce nejsou evidovány plánované návštěvy auditního programu."

    def _build_management_performance_text(
        self,
        metrics: AuditAnnualMetrics,
        severity: AuditAnnualSeverityMetrics,
        rating: PerformanceRatingResult,
        process_maturity: AuditProcessMaturityAssessment,
    ) -> str:
        return (
            f"Výkonnost systému řízení v roce {metrics.year} je hodnocena jako "
            f"{rating.headline.split('–', 1)[-1].strip().rstrip('.') if '–' in rating.headline else rating.headline}.\n"
            f"Průměrná vyspělost řídicích procesů: {process_maturity.average_maturity_text()}.\n"
            f"Podíl nevyhovujících auditních tvrzení: {severity.nevyhovuje_percent:.2f} %.\n"
            f"Váhové skóre zjištění: {severity.weighted_score} "
            f"({_format_ratio('Váhové skóre', severity.score_per_audit).replace('Váhové skóre: ', '')})."
        )

    def _build_process_effectiveness_text(self, maturity: AuditProcessMaturityAssessment) -> str:
        weak = [item.process_name for item in maturity.items if item.maturity_level in {"kriticky", "rizikovy"}]
        strong = [item.process_name for item in maturity.items if item.maturity_level == "vyspely"]
        parts: list[str] = []
        if weak:
            parts.append(
                "Nejvíce ohroženou účinností jsou řídicí procesy: " + ", ".join(weak[:5]) + "."
            )
        if strong:
            parts.append(
                "Nejvyspělejší řídicí procesy: " + ", ".join(strong[:5]) + "."
            )
        if not parts:
            return "Účinnost řídicích procesů je v průměru stabilní bez výrazných odchylek."
        return " ".join(parts)

    def _build_systemic_problems_text(self, problems: list[AuditAnnualAttentionProblem]) -> str:
        repeated = [problem for problem in problems if problem.count > 1]
        if not repeated:
            return "Opakované systémové problémy napříč audity nebyly v roce identifikovány."
        lines = [
            f"• {problem.label} (výskyt v {_audit_count_label(problem.count)})"
            for problem in repeated[:10]
        ]
        return (
            "Následující problémy se opakovaly ve více auditech a signalizují systémový charakter nedostatků:\n"
            + "\n".join(lines)
        )

    def _build_corrective_measures_text(
        self,
        metrics: AuditAnnualMetrics,
        severity: AuditAnnualSeverityMetrics,
    ) -> str:
        if metrics.measures_total == 0:
            return "V roce nebyla uložena žádná nápravná opatření."
        closed_ratio = metrics.measures_closed / metrics.measures_total * 100
        return (
            f"Bylo uloženo {metrics.measures_total} nápravných opatření, z toho "
            f"{metrics.measures_closed} uzavřeno ({closed_ratio:.0f} %). "
            f"Otevřená opatření po termínu: {severity.overdue_open_measures}."
        )

    def _build_comparison(
        self,
        year: int,
        metrics: AuditAnnualMetrics,
        history: AuditAnnualHistoricalSeries,
    ) -> AuditAnnualYearComparison:
        previous_year = year - 1
        previous_metrics = history.metrics_for_year(previous_year)
        if previous_metrics is None or previous_metrics.audits_count == 0:
            if not history.previous_years():
                return AuditAnnualYearComparison(
                    has_previous_year=False,
                    text=(
                        "Jedná se o první hodnocené období interních auditů.\n"
                        "Meziroční srovnání zatím není k dispozici."
                    ),
                )
            return AuditAnnualYearComparison(
                has_previous_year=False,
                text=(
                    f"Za rok {previous_year} nejsou evidovány audity.\n"
                    "Meziroční srovnání s bezprostředně předchozím rokem proto není k dispozici."
                ),
            )

        previous_normalized = previous_metrics.normalized()
        current_normalized = metrics.normalized()
        lines = [
            f"Audity: {previous_metrics.audits_count} → {metrics.audits_count}",
            _format_ratio("Neshody", previous_normalized.neshody_per_audit).replace(
                "Neshody:", f"Neshody {previous_year}:"
            ),
            _format_ratio("Neshody", current_normalized.neshody_per_audit).replace(
                "Neshody:", f"Neshody {year}:"
            ),
            f"Otevřená opatření: {previous_metrics.measures_open} → {metrics.measures_open}",
        ]
        return AuditAnnualYearComparison(has_previous_year=True, text="\n".join(lines))

    def _build_key_insights(
        self,
        *,
        metrics: AuditAnnualMetrics,
        manual: AuditAnnualManualContent,
        attention_problems: list[AuditAnnualAttentionProblem],
        process_maturity: AuditProcessMaturityAssessment,
        history: AuditAnnualHistoricalSeries,
    ) -> AuditAnnualKeyInsights:
        bullets: list[str] = []
        top_problem = attention_problems[0] if attention_problems else None
        weakest = next(
            (item for item in process_maturity.items if item.maturity_level in {"kriticky", "rizikovy"}),
            None,
        )
        if top_problem:
            suffix = f" (výskyt v {_audit_count_label(top_problem.count)})" if top_problem.count > 1 else ""
            bullets.append(f"• Nejčastější systémový problém: {top_problem.label}{suffix}")
        elif weakest:
            bullets.append(f"• Nejslabší řídicí proces: {weakest.process_name}")
        else:
            bullets.append("• Systémové problémy napříč audity nebyly identifikovány.")

        previous_metrics = history.metrics_for_year(metrics.year - 1)
        if previous_metrics and previous_metrics.audits_count > 0:
            prev_norm = previous_metrics.normalized()
            curr_norm = metrics.normalized()
            if (
                prev_norm.neshody_per_audit is not None
                and curr_norm.neshody_per_audit is not None
                and curr_norm.neshody_per_audit < prev_norm.neshody_per_audit
            ):
                bullets.append("• Největší zlepšení: snížení neshod na audit.")
            else:
                bullets.append("• Vývoj: sledovat trend neshod a plnění opatření.")
        else:
            bullets.append("• Největší zlepšení: první hodnocené období – referenční báze.")

        if weakest:
            bullets.append(f"• Největší riziko: řídicí proces {weakest.process_name}")
        elif metrics.measures_open > 0:
            bullets.append(f"• Největší riziko: {metrics.measures_open} otevřených nápravných opatření.")
        else:
            bullets.append("• Největší riziko: žádné závažné nevyřešené riziko nebylo identifikováno.")

        priority = _first_line(manual.top_priority)
        if priority:
            bullets.append(f"• Doporučená priorita příštího roku: {priority}")
        elif weakest:
            bullets.append(f"• Doporučená priorita příštího roku: posílit proces {weakest.process_name}")
        else:
            bullets.append("• Doporučená priorita příštího roku: udržet účinnost systému řízení.")

        return AuditAnnualKeyInsights(text="\n".join(bullets))

    def _overall_assessment_text(
        self,
        severity: AuditAnnualSeverityMetrics,
        rating: PerformanceRatingResult,
        methodology: PerformanceMethodologyContent,
        process_maturity: AuditProcessMaturityAssessment,
    ) -> str:
        detail = (
            f"Průměrná vyspělost systému řízení: {process_maturity.average_maturity_text()}.\n"
            f"Podíl nevyhovujících auditních tvrzení: {severity.nevyhovuje_percent:.2f} %.\n"
            f"Váhové skóre zjištění: {severity.weighted_score} "
            f"({_format_ratio('Váhové skóre', severity.score_per_audit).replace('Váhové skóre: ', '')}).\n"
            f"{DATA_REPRESENTATIVENESS_LABEL}: {methodology.reliability.label}.\n"
            f"{methodology.expert_justification}"
        )
        return f"{rating.headline}\n{detail}"

    def _build_appendices(
        self,
        audits: list[Audit],
        *,
        methodology_text: str,
    ) -> AuditAnnualAppendices:
        audit_lines: list[str] = []
        finding_blocks: list[str] = []
        measure_blocks: list[str] = []
        open_measure_blocks: list[str] = []
        finding_index = 1
        measure_index = 1
        open_measure_index = 1

        for audit in sorted(
            audits,
            key=lambda item: (item.audit_date or date.min, item.id),
        ):
            audit_lines.append(
                " • ".join(
                    part
                    for part in [
                        _text(audit.number) or f"ID {audit.id}",
                        _text(audit.workplace_name),
                        _fmt_date(audit.audit_date),
                        _text(audit.audit_type),
                    ]
                    if part
                )
            )

            for finding in sorted(
                finding_service.get_for_entity(ENTITY_AUDITY, audit.id),
                key=lambda item: (item.display_order, item.id),
            ):
                finding_blocks.append(
                    _format_labeled_block(
                        finding_index,
                        finding_type_label(finding.finding_type),
                        [
                            ("Audit", audit.number),
                            ("Pracoviště", audit.workplace_name),
                            ("Řídicí proces", finding.source_area_label),
                            ("Popis", finding.description),
                            ("Stav", finding_status_label(finding.status)),
                        ],
                    )
                )
                finding_index += 1

            for task in audit_service.get_tasks_for_audit(audit.id):
                block = _format_labeled_block(
                    measure_index,
                    task.title or "Opatření",
                    [
                        ("Audit", audit.number),
                        ("Odpovídá", task.responsible_person),
                        ("Termín", _fmt_date(task.due_date)),
                        ("Stav", task.computed_status),
                    ],
                )
                measure_blocks.append(block)
                measure_index += 1
                if task.computed_status not in {"Ukončeno", "Zrušeno"}:
                    open_measure_blocks.append(
                        _format_labeled_block(
                            open_measure_index,
                            task.title or "Opatření",
                            [
                                ("Audit", audit.number),
                                ("Odpovídá", task.responsible_person),
                                ("Termín", _fmt_date(task.due_date)),
                                ("Stav", task.computed_status),
                            ],
                        )
                    )
                    open_measure_index += 1

        return AuditAnnualAppendices(
            audits_text="\n".join(audit_lines) if audit_lines else "Nejsou evidovány.",
            findings_text=_join_blocks(finding_blocks) if finding_blocks else "Nejsou evidována.",
            measures_text=_join_blocks(measure_blocks) if measure_blocks else "Nejsou evidována.",
            open_measures_text=_join_blocks(open_measure_blocks) if open_measure_blocks else "Nejsou evidována.",
            methodology_text=methodology_text,
        )

    @staticmethod
    def _reserved_extension_placeholders(history: AuditAnnualHistoricalSeries) -> dict[str, str]:
        return {
            "trendy_text": "",
            "grafy_text": "",
            "historie_roky_text": ", ".join(str(year) for year in history.available_years),
            "historie_vyspelosti_text": "",
            "program_zprava_rezerva_text": "",
        }


audit_annual_export_context_service = AuditAnnualExportContextService()
