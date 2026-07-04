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
from moduly.proverky.constants import COMMISSION_RECORD_LEADER
from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_annual_report_service import bozp_annual_report_service
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


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

    def to_lines(self) -> list[str]:
        return [
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

    def to_placeholders(self) -> dict[str, str]:
        overview = "\n".join(self.to_lines())
        return {
            "prehled_vysledku_text": overview,
            "statistika_text": overview,
            "pocet_proverek": str(self.inspections_count),
            "pocet_pracovist": str(self.workplaces_count),
            "pocet_oblasti": str(self.areas_count),
            "pocet_kontrolnich_bodu": str(self.control_points_count),
        }


@dataclass(frozen=True)
class AnnualReportYearComparison:
    """Meziroční srovnání – připraveno pro víceleté trendy."""

    has_previous_year: bool
    text: str

    def to_placeholders(self) -> dict[str, str]:
        return {"vyvoj_text": self.text}


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
    comparison: AnnualReportYearComparison
    appendices: AnnualReportAppendices
    manual: AnnualReportManualContent
    attention_areas_text: str
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
        metrics = self._compute_metrics(year, inspections)
        comparison = self._build_comparison(year, metrics)
        appendices = self._build_appendices(inspections)
        manual = AnnualReportManualContent(
            silne_stranky=saved.silne_stranky,
            top_priority=saved.top_priority,
            doporuceni_specialisty=saved.doporuceni_specialisty,
            zpracoval=saved.zpracoval or self._resolve_specialist_name(inspections),
        )
        return AnnualReportContext(
            year=year,
            metrics=metrics,
            comparison=comparison,
            appendices=appendices,
            manual=manual,
            attention_areas_text=self._attention_areas_text(inspections),
            overall_assessment_text=self._overall_assessment_text(metrics),
            extension_placeholders=self._reserved_extension_placeholders(),
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
        detail = (
            f"Bylo provedeno {metrics.inspections_count} prověrek.\n"
            f"Bylo zjištěno {metrics.ratings_nevyhovuje} neshod "
            f"a {metrics.ratings_vyhovuje_s_doporucenim} doporučení.\n"
            f"{resolved}"
        )
        return f"{headline}\n{detail}"

    def _attention_areas_text(self, inspections: list[BozpInspection]) -> str:
        grouped: dict[tuple[str, str], dict[str, object]] = {}
        for inspection in inspections:
            for row in control_result_service.get_for_entity(ENTITY_PROVERKY, inspection.id):
                if row.result not in (
                    CONTROL_RESULT_NEVYHOVUJE,
                    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                ):
                    continue
                label = self._attention_area_label(row)
                key = (row.result, _text(label).casefold())
                bucket = grouped.setdefault(
                    key,
                    {"label": label, "result": row.result, "count": 0},
                )
                bucket["count"] = int(bucket["count"]) + 1

        if not grouped:
            return "—"

        lines: list[str] = []
        for (_, _), bucket in sorted(
            grouped.items(),
            key=lambda item: (
                0 if item[1]["result"] == CONTROL_RESULT_NEVYHOVUJE else 1,
                str(item[1]["label"]).casefold(),
            ),
        ):
            emoji = (
                "🔴"
                if bucket["result"] == CONTROL_RESULT_NEVYHOVUJE
                else "🟡"
            )
            label = str(bucket["label"])
            count = int(bucket["count"])
            suffix = f" ({count}×)" if count > 1 else ""
            lines.append(f"{emoji} {label}{suffix}")
        return "\n".join(lines)

    @staticmethod
    def _attention_area_label(row) -> str:
        for attr in ("source_control_point_label", "note", "source_section_label"):
            value = _text(getattr(row, attr, ""))
            if value:
                return value
        return "—"

    def _build_comparison(self, year: int, metrics: AnnualReportMetrics) -> AnnualReportYearComparison:
        previous = bozp_inspection_service.get_for_year(year - 1)
        if not previous:
            return AnnualReportYearComparison(
                has_previous_year=False,
                text=(
                    "Jedná se o první hodnocené období.\n"
                    "Meziroční srovnání zatím není k dispozici."
                ),
            )

        previous_metrics = self._compute_metrics(year - 1, previous)
        lines = [
            f"Prověrky: {previous_metrics.inspections_count} → {metrics.inspections_count}",
            f"Neshody: {previous_metrics.ratings_nevyhovuje} → {metrics.ratings_nevyhovuje}",
            f"Doporučení: {previous_metrics.ratings_vyhovuje_s_doporucenim} → {metrics.ratings_vyhovuje_s_doporucenim}",
            f"Zjištění: {previous_metrics.findings_count} → {metrics.findings_count}",
            f"Otevřená opatření: {previous_metrics.measures_open} → {metrics.measures_open}",
        ]
        return AnnualReportYearComparison(has_previous_year=True, text="\n".join(lines))

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

    def _resolve_specialist_name(self, inspections: list[BozpInspection]) -> str:
        default = bozp_annual_report_service.default_specialist_name()
        if default:
            return default

        counts: dict[str, int] = {}
        for inspection in inspections:
            for member in bozp_inspection_commission_service.get_for_inspection(inspection.id):
                if member.record_type != COMMISSION_RECORD_LEADER:
                    continue
                name = _text(member.display_name)
                if not name:
                    continue
                counts[name] = counts.get(name, 0) + 1
        if not counts:
            return "—"
        return max(counts.items(), key=lambda item: (item[1], item[0]))[0]

    @staticmethod
    def _reserved_extension_placeholders() -> dict[str, str]:
        return {
            "trendy_text": "",
            "grafy_text": "",
            "top10_zavad_text": "",
            "problemova_pracoviste_text": "",
            "priciny_zavad_text": "",
        }


bozp_annual_export_context_service = BozpAnnualExportContextService()
