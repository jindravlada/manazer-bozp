import re
from dataclasses import dataclass, field
from datetime import date, datetime

from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_PROVERKY,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_annual_report_service import bozp_annual_report_service
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service

_NEGATIVE_MARKERS = (
    "neprobíh",
    "neproběh",
    "chybí",
    "chyba",
    "není",
    "nezajišt",
    "nedostateč",
    "neúpln",
    "nevhodn",
    "chybn",
    "zanedban",
    "porušen",
    "chyběj",
    "absence",
    "nedodrž",
    "neřešen",
)

_IMPERATIVE_PREFIXES = (
    "doplnit",
    "zajistit",
    "upřesnit",
    "provést",
    "zavést",
    "aktualizovat",
    "dokončit",
    "opravit",
    "odstranit",
    "zkontrolovat",
    "navrhnout",
    "zlepšit",
    "posílit",
)

_POSITIVE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"probíhají\s+pravideln", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"probíhá\s+pravideln", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"kontrol.*\s+probíhají", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"přístup\s+.*\s+je\s+voln", re.I), "Přístup k hydrantu není volný."),
)


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except Exception:
        return text


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _first_line(value: str) -> str:
    for line in _text(value).split("\n"):
        text = line.strip().lstrip("✔").strip()
        if text:
            return text
    return ""


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


def _per_inspection(value: int, inspections_count: int) -> float | None:
    if inspections_count <= 0:
        return None
    return value / inspections_count


def _format_ratio_change(
    label: str,
    previous_value: float | None,
    current_value: float | None,
) -> str:
    previous_text = f"{previous_value:.2f} / prověrku" if previous_value is not None else "—"
    current_text = f"{current_value:.2f} / prověrku" if current_value is not None else "—"
    return f"{label}: {previous_text} → {current_text}"


def _inspection_count_label(count: int) -> str:
    if count == 1:
        return "1 prověrka"
    if 2 <= count <= 4:
        return f"{count} prověrky"
    return f"{count} prověrek"


def _inspection_year(inspection: BozpInspection) -> int | None:
    if inspection.inspection_date is not None:
        return inspection.inspection_date.year
    return inspection.year


@dataclass(frozen=True)
class AnnualReportNormalizedMetrics:
    neshody_per_inspection: float | None
    doporuceni_per_inspection: float | None
    zjisteni_per_inspection: float | None
    opatreni_per_inspection: float | None

    @classmethod
    def from_metrics(cls, metrics: "AnnualReportMetrics") -> "AnnualReportNormalizedMetrics":
        count = metrics.inspections_count
        return cls(
            neshody_per_inspection=_per_inspection(metrics.ratings_nevyhovuje, count),
            doporuceni_per_inspection=_per_inspection(
                metrics.ratings_vyhovuje_s_doporucenim,
                count,
            ),
            zjisteni_per_inspection=_per_inspection(metrics.findings_count, count),
            opatreni_per_inspection=_per_inspection(metrics.measures_total, count),
        )

    def to_lines(self) -> list[str]:
        return [
            _format_ratio("Neshody", self.neshody_per_inspection),
            _format_ratio("Doporučení", self.doporuceni_per_inspection),
            _format_ratio("Zjištění", self.zjisteni_per_inspection),
            _format_ratio("Opatření", self.opatreni_per_inspection),
        ]


def _format_ratio(label: str, value: float | None) -> str:
    if value is None:
        return f"{label}: —"
    return f"{label}: {value:.2f} / prověrku"


@dataclass(frozen=True)
class AnnualReportMetrics:
    """Agregované ukazatele za rok – rozšiřitelné o trendy a grafy."""

    year: int
    inspections_count: int
    workplaces_count: int
    areas_count: int
    control_points_count: int
    ratings_vyhovuje: int
    ratings_vyhovuje_s_doporucenim: int
    ratings_nevyhovuje: int
    findings_count: int
    measures_total: int
    measures_open: int
    measures_closed: int

    def normalized(self) -> AnnualReportNormalizedMetrics:
        return AnnualReportNormalizedMetrics.from_metrics(self)

    def to_lines(self) -> list[str]:
        lines = [
            f"Počet prověrek: {self.inspections_count}",
            f"Počet kontrolovaných pracovišť: {self.workplaces_count}",
            f"Počet kontrolovaných oblastí: {self.areas_count}",
            f"Počet kontrolních bodů: {self.control_points_count}",
            f"Vyhovuje: {self.ratings_vyhovuje}",
            f"Vyhovuje s doporučením: {self.ratings_vyhovuje_s_doporucenim}",
            f"Nevyhovuje: {self.ratings_nevyhovuje}",
            f"Počet zjištění: {self.findings_count}",
            f"Počet uložených opatření: {self.measures_total}",
            f"Počet otevřených opatření: {self.measures_open}",
            f"Počet uzavřených opatření: {self.measures_closed}",
        ]
        lines.extend(self.normalized().to_lines())
        return lines

    def to_placeholders(self) -> dict[str, str]:
        overview = "\n".join(self.to_lines())
        normalized = self.normalized()
        return {
            "prehled_vysledku_text": overview,
            "statistika_text": overview,
            "pocet_proverek": str(self.inspections_count),
            "pocet_pracovist": str(self.workplaces_count),
            "pocet_oblasti": str(self.areas_count),
            "pocet_kontrolnich_bodu": str(self.control_points_count),
            "neshody_na_proverku": (
                f"{normalized.neshody_per_inspection:.2f}"
                if normalized.neshody_per_inspection is not None
                else "—"
            ),
            "doporuceni_na_proverku": (
                f"{normalized.doporuceni_per_inspection:.2f}"
                if normalized.doporuceni_per_inspection is not None
                else "—"
            ),
            "zjisteni_na_proverku": (
                f"{normalized.zjisteni_per_inspection:.2f}"
                if normalized.zjisteni_per_inspection is not None
                else "—"
            ),
            "opatreni_na_proverku": (
                f"{normalized.opatreni_per_inspection:.2f}"
                if normalized.opatreni_per_inspection is not None
                else "—"
            ),
        }


@dataclass(frozen=True)
class AnnualReportHistoricalSeries:
    """Víceletá historie – připraveno pro budoucí grafy a tříleté přehledy."""

    target_year: int
    available_years: tuple[int, ...]
    metrics_by_year: dict[int, AnnualReportMetrics]

    def previous_years(self) -> tuple[int, ...]:
        return tuple(year for year in self.available_years if year < self.target_year)

    def metrics_for_year(self, year: int) -> AnnualReportMetrics | None:
        return self.metrics_by_year.get(year)


@dataclass(frozen=True)
class AnnualReportAttentionProblem:
    label: str
    severity: str
    count: int

    def to_text(self) -> str:
        emoji = "🔴" if self.severity == CONTROL_RESULT_NEVYHOVUJE else "🟡"
        lines = [f"{emoji} {self.label}"]
        if self.count > 1:
            lines.extend(["", "Výskyt:", _inspection_count_label(self.count)])
        return "\n".join(lines)


@dataclass(frozen=True)
class AnnualReportYearComparison:
    """Meziroční srovnání – připraveno pro víceleté trendy."""

    has_previous_year: bool
    text: str

    def to_placeholders(self) -> dict[str, str]:
        return {"vyvoj_text": self.text}


@dataclass(frozen=True)
class AnnualReportKeyInsights:
    text: str

    def to_placeholders(self) -> dict[str, str]:
        return {"klicove_poznatky_text": self.text or "—"}


@dataclass(frozen=True)
class AnnualReportAppendices:
    """Přílohy dokumentu – samostatné bloky pro budoucí rozšíření."""

    inspections_text: str
    findings_text: str
    measures_text: str
    open_measures_text: str

    def to_placeholders(self) -> dict[str, str]:
        return {
            "priloha_proverky_text": self.inspections_text,
            "priloha_zjisteni_text": self.findings_text,
            "priloha_opatreni_text": self.measures_text,
            "priloha_otevrena_opatreni_text": self.open_measures_text,
        }


@dataclass(frozen=True)
class AnnualReportManualContent:
    silne_stranky: str
    top_priority: str
    doporuceni_specialisty: str
    zpracoval: str

    def strengths_text(self) -> str:
        raw = _text(self.silne_stranky)
        if not raw:
            return "—"
        lines: list[str] = []
        for line in raw.split("\n"):
            text = line.strip()
            if not text:
                continue
            lines.append(text if text.startswith("✔") else f"✔ {text}")
        return "\n".join(lines) if lines else "—"

    def to_placeholders(self) -> dict[str, str]:
        return {
            "silne_stranky_text": self.strengths_text(),
            "top_priority_text": _text(self.top_priority) or "—",
            "doporuceni_specialisty": _text(self.doporuceni_specialisty) or "—",
            "zpracoval": _text(self.zpracoval) or "—",
        }


@dataclass(frozen=True)
class AnnualReportContext:
    """Sjednocený kontext roční zprávy BOZP."""

    year: int
    metrics: AnnualReportMetrics
    history: AnnualReportHistoricalSeries
    comparison: AnnualReportYearComparison
    key_insights: AnnualReportKeyInsights
    appendices: AnnualReportAppendices
    manual: AnnualReportManualContent
    attention_areas_text: str
    attention_problems: tuple[AnnualReportAttentionProblem, ...]
    overall_assessment_text: str
    extension_placeholders: dict[str, str] = field(default_factory=dict)

    def placeholder_values(self) -> dict[str, str]:
        employer = settings_service.get_employer()
        organization = _text(employer.name if employer else "")

        values = {
            "rok": str(self.year),
            "organizace": organization or "—",
            "obdobi": f"1. 1. {self.year} – 31. 12. {self.year}",
            "datum_vytvoreni": datetime.now().strftime("%d.%m.%Y"),
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
            "celkove_hodnoceni_text": self.overall_assessment_text,
            "oblasti_pozornosti_text": self.attention_areas_text,
            "zamestnavatel_nazev": organization,
            "souhrn_text": self.overall_assessment_text,
        }
        values.update(self.metrics.to_placeholders())
        values.update(self.comparison.to_placeholders())
        values.update(self.key_insights.to_placeholders())
        values.update(self.appendices.to_placeholders())
        values.update(self.manual.to_placeholders())
        values.update(self.extension_placeholders)
        return values


class BozpAnnualExportContextService:
    def build(self, year: int, *, report: BozpAnnualReport | None = None) -> AnnualReportContext:
        if year < 1900 or year > 3000:
            raise ValueError("Neplatný rok roční zprávy.")

        inspections = bozp_inspection_service.get_for_year(year)
        saved = report or bozp_annual_report_service.get_or_create_for_year(year)
        history = self._load_historical_series(year)
        metrics = history.metrics_for_year(year) or self._compute_metrics(year, inspections)
        attention_problems = self._collect_attention_problems(inspections)
        comparison = self._build_comparison(year, metrics, history)
        appendices = self._build_appendices(inspections)
        manual = AnnualReportManualContent(
            silne_stranky=saved.silne_stranky,
            top_priority=saved.top_priority,
            doporuceni_specialisty=saved.doporuceni_specialisty,
            zpracoval=_text(saved.zpracoval),
        )
        key_insights = self._build_key_insights(
            metrics=metrics,
            manual=manual,
            attention_problems=attention_problems,
            history=history,
        )
        return AnnualReportContext(
            year=year,
            metrics=metrics,
            history=history,
            comparison=comparison,
            key_insights=key_insights,
            appendices=appendices,
            manual=manual,
            attention_areas_text=self._attention_areas_text(attention_problems),
            attention_problems=tuple(attention_problems),
            overall_assessment_text=self._overall_assessment_text(metrics),
            extension_placeholders=self._reserved_extension_placeholders(history),
        )

    def _load_historical_series(self, target_year: int) -> AnnualReportHistoricalSeries:
        years: set[int] = set()
        for inspection in bozp_inspection_service.get_all():
            inspection_year = _inspection_year(inspection)
            if inspection_year is not None and inspection_year <= target_year:
                years.add(inspection_year)

        metrics_by_year: dict[int, AnnualReportMetrics] = {}
        for year in sorted(years):
            inspections = bozp_inspection_service.get_for_year(year)
            metrics_by_year[year] = self._compute_metrics(year, inspections)

        return AnnualReportHistoricalSeries(
            target_year=target_year,
            available_years=tuple(sorted(years)),
            metrics_by_year=metrics_by_year,
        )

    def _compute_metrics(self, year: int, inspections: list[BozpInspection]) -> AnnualReportMetrics:
        workplaces: set[str] = set()
        areas: set[str] = set()
        ratings_vyhovuje = 0
        ratings_vyhovuje_s_doporucenim = 0
        ratings_nevyhovuje = 0
        control_points_count = 0
        findings_count = 0
        measures_total = 0
        measures_open = 0
        measures_closed = 0
        seen_task_ids: set[int] = set()

        for inspection in inspections:
            if _text(inspection.workplace_name):
                workplaces.add(_text(inspection.workplace_name))

            stats = control_activity_statistics_service.compute(ENTITY_PROVERKY, inspection.id)
            ratings_vyhovuje += stats.ratings_vyhovuje
            ratings_vyhovuje_s_doporucenim += stats.ratings_vyhovuje_s_doporucenim
            ratings_nevyhovuje += stats.ratings_nevyhovuje
            control_points_count += stats.control_points_checked
            findings_count += stats.findings_total

            for result in control_result_service.get_for_entity(ENTITY_PROVERKY, inspection.id):
                label = _text(result.source_area_label)
                if label:
                    areas.add(label)

            for task in bozp_inspection_service.get_tasks_for_inspection(inspection.id):
                if task.id in seen_task_ids:
                    continue
                seen_task_ids.add(task.id)
                measures_total += 1
                if task.computed_status == "Ukončeno":
                    measures_closed += 1
                elif task.computed_status not in {"Zrušeno"}:
                    measures_open += 1

        return AnnualReportMetrics(
            year=year,
            inspections_count=len(inspections),
            workplaces_count=len(workplaces),
            areas_count=len(areas),
            control_points_count=control_points_count,
            ratings_vyhovuje=ratings_vyhovuje,
            ratings_vyhovuje_s_doporucenim=ratings_vyhovuje_s_doporucenim,
            ratings_nevyhovuje=ratings_nevyhovuje,
            findings_count=findings_count,
            measures_total=measures_total,
            measures_open=measures_open,
            measures_closed=measures_closed,
        )

    def _overall_assessment_text(self, metrics: AnnualReportMetrics) -> str:
        if metrics.ratings_nevyhovuje:
            headline = "🔴\nByly zjištěny závažné nedostatky ovlivňující úroveň BOZP."
        elif metrics.ratings_vyhovuje_s_doporucenim:
            headline = "🟡\nByly zjištěny oblasti vyžadující zvýšenou pozornost."
        else:
            headline = "🟢\nSystém BOZP je funkční a stabilní."

        resolved = (
            "Všechna závažná zjištění byla řešena."
            if metrics.measures_open == 0 and metrics.ratings_nevyhovuje == 0
            else "Některá závažná zjištění vyžadují další sledování plnění opatření."
        )
        normalized = metrics.normalized()
        detail = (
            f"Bylo provedeno {metrics.inspections_count} prověrek.\n"
            f"Bylo zjištěno {metrics.ratings_nevyhovuje} neshod "
            f"a {metrics.ratings_vyhovuje_s_doporucenim} doporučení.\n"
            f"{_format_ratio('Neshody', normalized.neshody_per_inspection).replace('Neshody: ', 'Průměrně neshod: ')}\n"
            f"{resolved}"
        )
        return f"{headline}\n{detail}"

    def _collect_attention_problems(
        self,
        inspections: list[BozpInspection],
    ) -> list[AnnualReportAttentionProblem]:
        grouped: dict[tuple[str, str], dict[str, object]] = {}
        for inspection in inspections:
            for row in control_result_service.get_for_entity(ENTITY_PROVERKY, inspection.id):
                if row.result not in (
                    CONTROL_RESULT_NEVYHOVUJE,
                    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                ):
                    continue
                raw_label = self._attention_area_label(row)
                problem_label = self._normalize_attention_problem(raw_label)
                if not problem_label:
                    continue
                key = (row.result, problem_label.casefold())
                bucket = grouped.setdefault(
                    key,
                    {
                        "label": problem_label,
                        "severity": row.result,
                        "count": 0,
                    },
                )
                bucket["count"] = int(bucket["count"]) + 1

        problems = [
            AnnualReportAttentionProblem(
                label=str(bucket["label"]),
                severity=str(bucket["severity"]),
                count=int(bucket["count"]),
            )
            for bucket in grouped.values()
        ]
        problems.sort(
            key=lambda item: (
                0 if item.severity == CONTROL_RESULT_NEVYHOVUJE else 1,
                -item.count,
                item.label.casefold(),
            ),
        )
        return problems

    def _attention_areas_text(self, problems: list[AnnualReportAttentionProblem]) -> str:
        if not problems:
            return "—"
        return "\n\n".join(problem.to_text() for problem in problems)

    @staticmethod
    def _is_problem_statement(label: str) -> bool:
        lower = label.lower().strip()
        if any(lower.startswith(prefix) for prefix in _IMPERATIVE_PREFIXES):
            return True
        return any(marker in lower for marker in _NEGATIVE_MARKERS)

    def _normalize_attention_problem(self, label: str) -> str | None:
        label = _text(label)
        if not label or label == "—":
            return None
        if self._is_problem_statement(label):
            return label

        lower = label.lower()
        for pattern, replacement in _POSITIVE_REPLACEMENTS:
            if pattern.search(lower):
                return replacement

        if re.search(r"\bje\s+", lower) and "není" not in lower:
            inverted = re.sub(r"\bje\b", "není", label, count=1, flags=re.I)
            if inverted.lower() != lower:
                return inverted
        if re.search(r"\bjsou\s+", lower) and "nejsou" not in lower:
            inverted = re.sub(r"\bjsou\b", "nejsou", label, count=1, flags=re.I)
            if inverted.lower() != lower:
                return inverted
        if re.search(r"\bprobíhají\b", lower):
            return "Neprobíhají pravidelné kontroly pracovišť."

        return None

    @staticmethod
    def _attention_area_label(row) -> str:
        for attr in ("source_control_point_label", "note", "source_section_label"):
            value = _text(getattr(row, attr, ""))
            if value:
                return value
        return "—"

    def _build_comparison(
        self,
        year: int,
        metrics: AnnualReportMetrics,
        history: AnnualReportHistoricalSeries,
    ) -> AnnualReportYearComparison:
        previous_year = year - 1
        previous_metrics = history.metrics_for_year(previous_year)
        if previous_metrics is None or previous_metrics.inspections_count == 0:
            if not history.previous_years():
                return AnnualReportYearComparison(
                    has_previous_year=False,
                    text=(
                        "Jedná se o první hodnocené období.\n"
                        "Meziroční srovnání zatím není k dispozici."
                    ),
                )
            return AnnualReportYearComparison(
                has_previous_year=False,
                text=(
                    f"Za rok {previous_year} nejsou evidovány prověrky.\n"
                    "Meziroční srovnání s bezprostředně předchozím rokem proto není k dispozici."
                ),
            )

        previous_normalized = previous_metrics.normalized()
        current_normalized = metrics.normalized()
        lines = [
            f"Prověrky: {previous_metrics.inspections_count} → {metrics.inspections_count}",
            f"Neshody: {previous_metrics.ratings_nevyhovuje} → {metrics.ratings_nevyhovuje}",
            f"Doporučení: {previous_metrics.ratings_vyhovuje_s_doporucenim} → {metrics.ratings_vyhovuje_s_doporucenim}",
            f"Zjištění: {previous_metrics.findings_count} → {metrics.findings_count}",
            f"Otevřená opatření: {previous_metrics.measures_open} → {metrics.measures_open}",
            "",
            _format_ratio_change(
                "Neshody",
                previous_normalized.neshody_per_inspection,
                current_normalized.neshody_per_inspection,
            ),
            _format_ratio_change(
                "Doporučení",
                previous_normalized.doporuceni_per_inspection,
                current_normalized.doporuceni_per_inspection,
            ),
            _format_ratio_change(
                "Zjištění",
                previous_normalized.zjisteni_per_inspection,
                current_normalized.zjisteni_per_inspection,
            ),
            _format_ratio_change(
                "Opatření",
                previous_normalized.opatreni_per_inspection,
                current_normalized.opatreni_per_inspection,
            ),
            "",
        ]
        lines.extend(self._comparison_interpretation(previous_metrics, metrics))
        return AnnualReportYearComparison(has_previous_year=True, text="\n".join(lines).strip())

    def _comparison_interpretation(
        self,
        previous: AnnualReportMetrics,
        current: AnnualReportMetrics,
    ) -> list[str]:
        paragraphs: list[str] = []
        prev_norm = previous.normalized()
        curr_norm = current.normalized()

        if current.ratings_nevyhovuje > previous.ratings_nevyhovuje:
            paragraph = [
                f"Počet neshod vzrostl z {previous.ratings_nevyhovuje} na {current.ratings_nevyhovuje}."
            ]
            if current.inspections_count > previous.inspections_count:
                paragraph.append(
                    f"Současně však vzrostl počet provedených prověrek "
                    f"z {previous.inspections_count} na {current.inspections_count}."
                )
                if (
                    prev_norm.neshody_per_inspection is not None
                    and curr_norm.neshody_per_inspection is not None
                ):
                    if curr_norm.neshody_per_inspection < prev_norm.neshody_per_inspection:
                        paragraph.append(
                            "Po normalizaci na počet prověrek se ukazatel neshod zlepšil – "
                            "samotný nárůst absolutního počtu tedy neznamená zhoršení úrovně BOZP."
                        )
                    elif curr_norm.neshody_per_inspection > prev_norm.neshody_per_inspection:
                        paragraph.append(
                            "Po normalizaci na počet prověrek se ukazatel neshod zhoršil – "
                            "nárůst neshod odráží reálné zhoršení stavu BOZP."
                        )
                    else:
                        paragraph.append(
                            "Samotný nárůst počtu neshod proto automaticky neznamená zhoršení úrovně BOZP."
                        )
            else:
                paragraph.append(
                    "Nárůst neshod při srovnatelném rozsahu prověrek signalizuje zhoršení stavu BOZP."
                )
            paragraphs.append(" ".join(paragraph))
        elif current.ratings_nevyhovuje < previous.ratings_nevyhovuje:
            paragraphs.append(
                f"Počet neshod klesl z {previous.ratings_nevyhovuje} na {current.ratings_nevyhovuje} – "
                "pozitivní trend ve prospěch bezpečnosti práce."
            )

        if current.ratings_vyhovuje_s_doporucenim > previous.ratings_vyhovuje_s_doporucenim:
            if (
                prev_norm.doporuceni_per_inspection is not None
                and curr_norm.doporuceni_per_inspection is not None
                and curr_norm.doporuceni_per_inspection <= prev_norm.doporuceni_per_inspection
                and current.inspections_count > previous.inspections_count
            ):
                paragraphs.append(
                    "Počet doporučení vzrostl, avšak po přepočtu na prověrku se trend nezhoršil – "
                    "vyšší aktivita kontrol přináší více detailních podnětů ke zlepšení."
                )

        if current.measures_open < previous.measures_open:
            paragraphs.append(
                f"Počet otevřených opatření klesl z {previous.measures_open} na {current.measures_open} – "
                "organizace efektivněji uzavírá zjištěné nedostatky."
            )
        elif current.measures_open > previous.measures_open:
            paragraphs.append(
                f"Počet otevřených opatření vzrostl z {previous.measures_open} na {current.measures_open} – "
                "je nutné zajistit jejich včasné dokončení."
            )

        if not paragraphs:
            paragraphs.append(
                "Vývoj oproti minulému roku je stabilní. "
                "Normalizované ukazatele doporučujeme sledovat jako hlavní manažerský signál."
            )
        return paragraphs

    def _build_key_insights(
        self,
        *,
        metrics: AnnualReportMetrics,
        manual: AnnualReportManualContent,
        attention_problems: list[AnnualReportAttentionProblem],
        history: AnnualReportHistoricalSeries,
    ) -> AnnualReportKeyInsights:
        bullets: list[str] = []
        top_problem = attention_problems[0] if attention_problems else None
        top_red = next(
            (problem for problem in attention_problems if problem.severity == CONTROL_RESULT_NEVYHOVUJE),
            None,
        )

        if top_problem:
            suffix = ""
            if top_problem.count > 1:
                suffix = f" (výskyt ve {_inspection_count_label(top_problem.count)})"
            bullets.append(f"• Nejčastější problém: {top_problem.label}{suffix}")
        else:
            bullets.append(
                "• Nejčastější problém: Zásadní opakující se nedostatky nebyly identifikovány."
            )

        previous_year = history.target_year - 1
        previous_metrics = history.metrics_for_year(previous_year)
        improvement_text = ""
        if previous_metrics and previous_metrics.inspections_count > 0:
            prev_norm = previous_metrics.normalized()
            curr_norm = metrics.normalized()
            improvements: list[str] = []
            if (
                prev_norm.neshody_per_inspection is not None
                and curr_norm.neshody_per_inspection is not None
                and curr_norm.neshody_per_inspection < prev_norm.neshody_per_inspection
            ):
                improvements.append("snížení neshod na prověrku")
            if metrics.measures_open < previous_metrics.measures_open:
                improvements.append("méně otevřených opatření")
            if (
                prev_norm.doporuceni_per_inspection is not None
                and curr_norm.doporuceni_per_inspection is not None
                and curr_norm.doporuceni_per_inspection < prev_norm.doporuceni_per_inspection
            ):
                improvements.append("méně doporučení na prověrku")
            if improvements:
                improvement_text = improvements[0]
        if not improvement_text:
            improvement_text = _first_line(manual.silne_stranky)
        if improvement_text:
            bullets.append(f"• Největší zlepšení: {improvement_text}")
        elif previous_metrics and previous_metrics.inspections_count > 0:
            bullets.append("• Největší zlepšení: Stabilní nebo mírně pozitivní vývoj oproti minulému roku.")
        else:
            bullets.append(
                "• Největší zlepšení: První hodnocené období – referenční báze pro budoucí srovnání."
            )

        if top_red:
            bullets.append(f"• Největší riziko: {top_red.label}")
        elif metrics.measures_open > 0:
            bullets.append(
                f"• Největší riziko: {metrics.measures_open} neuzavřených opatření vyžaduje sledování."
            )
        elif metrics.ratings_nevyhovuje > 0:
            bullets.append("• Největší riziko: Zjištěné neshody vyžadují systematické řešení.")
        else:
            bullets.append("• Největší riziko: Žádné závažné nevyřešené riziko nebylo identifikováno.")

        priority = _first_line(manual.top_priority)
        if priority:
            bullets.append(f"• Doporučená priorita příštího roku: {priority}")
        elif top_problem:
            bullets.append(
                f"• Doporučená priorita příštího roku: Řešit {top_problem.label.lower()}"
            )
        else:
            bullets.append(
                "• Doporučená priorita příštího roku: Udržet dosavadní úroveň BOZP a sledovat trend."
            )

        return AnnualReportKeyInsights(text="\n".join(bullets))

    def _build_appendices(self, inspections: list[BozpInspection]) -> AnnualReportAppendices:
        inspection_lines: list[str] = []
        finding_blocks: list[str] = []
        measure_blocks: list[str] = []
        open_measure_blocks: list[str] = []
        finding_index = 1
        measure_index = 1
        open_measure_index = 1

        for inspection in sorted(
            inspections,
            key=lambda item: (item.inspection_date or date.min, item.id),
        ):
            inspection_lines.append(
                " • ".join(
                    part
                    for part in [
                        _text(inspection.number) or f"ID {inspection.id}",
                        _text(inspection.workplace_name),
                        _fmt_date(inspection.inspection_date),
                        _text(inspection.status),
                    ]
                    if part
                )
            )

            for finding in sorted(
                finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id),
                key=lambda item: (item.display_order, item.id),
            ):
                finding_blocks.append(
                    _format_labeled_block(
                        finding_index,
                        finding_type_label(finding.finding_type),
                        [
                            ("Prověrka", inspection.number),
                            ("Pracoviště", inspection.workplace_name),
                            ("Oblast", finding.source_area_label),
                            ("Popis", finding.description),
                            ("Stav", finding_status_label(finding.status)),
                        ],
                    )
                )
                finding_index += 1

            for task in bozp_inspection_service.get_tasks_for_inspection(inspection.id):
                block = _format_labeled_block(
                    measure_index,
                    task.title or "Úkol",
                    [
                        ("Prověrka", inspection.number),
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
                            task.title or "Úkol",
                            [
                                ("Prověrka", inspection.number),
                                ("Odpovídá", task.responsible_person),
                                ("Termín", _fmt_date(task.due_date)),
                                ("Stav", task.computed_status),
                            ],
                        )
                    )
                    open_measure_index += 1

        return AnnualReportAppendices(
            inspections_text="\n".join(inspection_lines) if inspection_lines else "Nejsou evidovány.",
            findings_text=_join_blocks(finding_blocks) if finding_blocks else "Nejsou evidována.",
            measures_text=_join_blocks(measure_blocks) if measure_blocks else "Nejsou evidována.",
            open_measures_text=_join_blocks(open_measure_blocks) if open_measure_blocks else "Nejsou evidována.",
        )

    @staticmethod
    def _reserved_extension_placeholders(history: AnnualReportHistoricalSeries) -> dict[str, str]:
        return {
            "trendy_text": "",
            "grafy_text": "",
            "top10_zavad_text": "",
            "problemova_pracoviste_text": "",
            "priciny_zavad_text": "",
            "historie_roky_text": ", ".join(str(year) for year in history.available_years),
        }


bozp_annual_export_context_service = BozpAnnualExportContextService()
