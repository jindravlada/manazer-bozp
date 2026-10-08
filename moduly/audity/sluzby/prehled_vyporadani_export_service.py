"""Export uloženého přehledu vypořádání zjištění z interních auditů.

Text dokumentu se skládá jen z historického snímku. Šablonu vykreslí
společný ODT engine Manažera BOZP.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtExportError, OdtParagraph, OdtRichContent
from core.services.storage_service import storage_service
from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    SETTLEMENT_SOURCE_AUDITY,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.modely.finding_settlement_overview import (
    FindingSettlementOverview,
    FindingSettlementOverviewItem,
)
from core.shared.sluzby.finding_settlement_overview_service import (
    finding_settlement_overview_service,
)

SECTION_SETTLED_BASELINE = "Vypořádaná zjištění"
SECTION_SETTLED_SINCE = "Vypořádaná od posledního přehledu"
SECTION_UNSETTLED = "Dosud nevypořádaná zjištění"
SECTION_NEW = "Nová zjištění"
SECTION_REOPENED = "Znovuotevřená zjištění"
EMPTY_SECTION = "Žádné zjištění."

_OPEN_STATUSES = frozenset({FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU})


class PrehledVyporadaniExportError(Exception):
    """Uložený přehled nelze zobrazit ani exportovat."""


@dataclass(frozen=True)
class PrehledVyporadaniItemView:
    audit_label: str
    workplace_name: str
    finding_type_label: str
    process_label: str
    verification_area_label: str
    description: str
    recommended_action: str
    status_label: str
    resolved_at_label: str
    task_label: str
    categories: str
    description_snapshot: str


@dataclass(frozen=True)
class PrehledVyporadaniView:
    overview_id: int
    sequence_number: int
    presented_label: str
    period_label: str
    note: str
    total_count: int
    settled_count: int
    in_process_count: int
    open_count: int
    type_counts: tuple[tuple[str, int], ...]
    settled_since_count: int
    unsettled_count: int
    new_count: int
    reopened_count: int
    settled_items: tuple[PrehledVyporadaniItemView, ...]
    unsettled_items: tuple[PrehledVyporadaniItemView, ...]
    new_items: tuple[PrehledVyporadaniItemView, ...]
    reopened_items: tuple[PrehledVyporadaniItemView, ...]
    items: tuple[PrehledVyporadaniItemView, ...]

    @property
    def shows_changes(self) -> bool:
        return self.sequence_number > 0


def format_overview_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def period_label_for(overview: FindingSettlementOverview) -> str:
    if int(overview.sequence_number) == 0 or overview.period_from is None:
        return f"výchozí stav k {format_overview_date(overview.period_to)}"
    return (
        f"{format_overview_date(overview.period_from)} – "
        f"{format_overview_date(overview.period_to)}"
    )


def presented_date_problem(value: date | None, previous: date | None) -> str | None:
    if value is None:
        return "Datum předložení není platné."
    if previous is not None and value < previous:
        return "Datum předložení nesmí být starší než datum předchozího přehledu."
    return None


def scope_warning(completed_record_count: int, finding_count: int) -> str:
    if completed_record_count <= 0:
        return "Neexistuje žádný dokončený interní audit. Přehled bude prázdný."
    if finding_count <= 0:
        return "Dokončené audity neobsahují žádná zjištění. Přehled bude prázdný."
    return ""


class PrehledVyporadaniExportService:
    TEMPLATE_NAME = "PrehledVyporadaniZjisteni.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "prehledy_vyporadani"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def load_view(self, overview_id: int) -> PrehledVyporadaniView:
        overview = finding_settlement_overview_service.get_overview(int(overview_id))
        if overview is None or overview.source_type != SETTLEMENT_SOURCE_AUDITY:
            raise PrehledVyporadaniExportError(
                "Historický přehled nebyl nalezen."
            )
        if overview.presented_at is None or overview.period_to is None:
            raise PrehledVyporadaniExportError(
                "Historický přehled je poškozený a nelze ho použít."
            )
        items = finding_settlement_overview_service.items_for(int(overview.id))
        return build_view(overview, items)

    def generate(
        self,
        overview_id: int,
        *,
        output_path: Path | None = None,
    ) -> Path:
        view = self.load_view(overview_id)
        template = self.template_path()
        if not template.exists():
            raise PrehledVyporadaniExportError(
                f"Šablona přehledu vypořádání nebyla nalezena: {template}"
            )
        target = output_path or storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(view.sequence_number),
        )
        values = placeholder_values(view)
        try:
            return self.engine.render(template, target, values)
        except (OdtExportError, OSError, FileNotFoundError) as exc:
            raise PrehledVyporadaniExportError(
                f"Přehled se nepodařilo exportovat.\n\n{exc}"
            ) from exc

    @staticmethod
    def _output_filename(sequence_number: int) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"PrehledVyporadani-{int(sequence_number)}_{stamp}.odt"


def build_view(
    overview: FindingSettlementOverview,
    items: list[FindingSettlementOverviewItem],
) -> PrehledVyporadaniView:
    type_counts = _type_counts(overview)
    if int(overview.total_count) != len(items):
        raise PrehledVyporadaniExportError(
            "Historický přehled je poškozený a nelze ho použít."
        )
    if sum(count for _label, count in type_counts) != int(overview.total_count):
        raise PrehledVyporadaniExportError(
            "Historický přehled je poškozený a nelze ho použít."
        )

    sequence = int(overview.sequence_number)
    views = tuple(_item_view(item, sequence) for item in items)
    by_identity = {id(item): view for item, view in zip(items, views, strict=True)}
    settled_source = _settled_source(items, sequence)
    unsettled_source = [item for item in items if item.status in _OPEN_STATUSES]
    new_source = [item for item in items if sequence > 0 and item.is_new]
    reopened_source = [item for item in items if sequence > 0 and item.reopened]
    return PrehledVyporadaniView(
        overview_id=int(overview.id),
        sequence_number=sequence,
        presented_label=format_overview_date(overview.presented_at),
        period_label=period_label_for(overview),
        note=str(overview.note or "").strip(),
        total_count=int(overview.total_count),
        settled_count=int(overview.settled_count),
        in_process_count=int(overview.in_process_count),
        open_count=int(overview.open_count),
        type_counts=type_counts,
        settled_since_count=sum(1 for item in items if item.settled_since_previous),
        unsettled_count=len(unsettled_source),
        new_count=len(new_source),
        reopened_count=len(reopened_source),
        settled_items=tuple(by_identity[id(item)] for item in settled_source),
        unsettled_items=tuple(by_identity[id(item)] for item in unsettled_source),
        new_items=tuple(by_identity[id(item)] for item in new_source),
        reopened_items=tuple(by_identity[id(item)] for item in reopened_source),
        items=views,
    )


def placeholder_values(view: PrehledVyporadaniView) -> dict[str, object]:
    number = f"Přehled č. {view.sequence_number}"
    if view.sequence_number == 0:
        number = "Přehled č. 0 – výchozí stav"
    note = OdtRichContent(paragraphs=[], omit_when_empty=True)
    if view.note:
        note = OdtRichContent(
            paragraphs=[OdtParagraph.text(f"Poznámka: {view.note}")]
        )
    settled_title = (
        SECTION_SETTLED_BASELINE if view.sequence_number == 0 else SECTION_SETTLED_SINCE
    )
    return {
        "cislo_prehledu": number,
        "datum_predlozeni": view.presented_label,
        "obdobi": view.period_label,
        "poznamka": note,
        "souhrn": _summary(view),
        "sekce_vyporadana": _section(settled_title, view.settled_items),
        "sekce_nevyporadana": _section(SECTION_UNSETTLED, view.unsettled_items),
        "sekce_nova": _optional_section(view.shows_changes, SECTION_NEW, view.new_items),
        "sekce_znovuotevrena": _optional_section(
            view.shows_changes,
            SECTION_REOPENED,
            view.reopened_items,
        ),
    }


def _summary(view: PrehledVyporadaniView) -> OdtRichContent:
    paragraphs = [
        OdtParagraph.text(f"Celkový počet zjištění: {view.total_count}"),
        OdtParagraph.text(f"Vypořádaná: {view.settled_count}"),
        OdtParagraph.text(f"V procesu: {view.in_process_count}"),
        OdtParagraph.text(f"Otevřená: {view.open_count}"),
        OdtParagraph.text("Počty podle typů zjištění:", bold=True),
    ]
    if view.type_counts:
        paragraphs.extend(
            OdtParagraph.text(f"{label}: {count}")
            for label, count in view.type_counts
        )
    else:
        paragraphs.append(OdtParagraph.text(EMPTY_SECTION))
    if view.shows_changes:
        paragraphs.extend(
            [
                OdtParagraph.blank_line(),
                OdtParagraph.text(
                    f"Vypořádaná od posledního přehledu: {view.settled_since_count}"
                ),
                OdtParagraph.text(f"Dosud nevypořádaná: {view.unsettled_count}"),
                OdtParagraph.text(f"Nová zjištění: {view.new_count}"),
                OdtParagraph.text(f"Znovuotevřená zjištění: {view.reopened_count}"),
            ]
        )
    return OdtRichContent(paragraphs=paragraphs)


def _optional_section(
    enabled: bool,
    title: str,
    items: tuple[PrehledVyporadaniItemView, ...],
) -> OdtRichContent:
    if not enabled:
        return OdtRichContent(paragraphs=[], omit_when_empty=True)
    return _section(title, items)


def _section(
    title: str,
    items: tuple[PrehledVyporadaniItemView, ...],
) -> OdtRichContent:
    paragraphs: list[OdtParagraph] = [OdtParagraph.text(title, style="H")]
    if not items:
        paragraphs.append(OdtParagraph.text(EMPTY_SECTION))
        return OdtRichContent(paragraphs=paragraphs)
    for index, item in enumerate(items):
        if index:
            paragraphs.append(OdtParagraph.blank_line())
        paragraphs.extend(_item_paragraphs(item))
    return OdtRichContent(paragraphs=paragraphs)


def _item_paragraphs(item: PrehledVyporadaniItemView) -> list[OdtParagraph]:
    return [
        OdtParagraph.text(f"Audit {item.audit_label}", bold=True),
        OdtParagraph.text(f"Auditovaný provoz: {_dash(item.workplace_name)}"),
        OdtParagraph.text(f"Typ zjištění: {_dash(item.finding_type_label)}"),
        OdtParagraph.text(f"Řídicí proces: {_dash(item.process_label)}"),
        OdtParagraph.text(f"Oblast ověřování: {_dash(item.verification_area_label)}"),
        OdtParagraph.text(f"Popis zjištění: {_dash(item.description)}"),
        OdtParagraph.text(f"Doporučené opatření: {_dash(item.recommended_action)}"),
        OdtParagraph.text(f"Stav zjištění: {_dash(item.status_label)}"),
        OdtParagraph.text(f"Datum vypořádání: {item.resolved_at_label}"),
        OdtParagraph.text(f"Navazující úkol: {item.task_label}"),
    ]


def _item_view(
    item: FindingSettlementOverviewItem,
    sequence: int,
) -> PrehledVyporadaniItemView:
    year = "" if item.audit_year is None else str(item.audit_year)
    number = str(item.audit_number or "").strip()
    if number and year:
        audit_label = f"{number}/{year}"
    else:
        audit_label = number or year or "—"
    task_label = "—"
    if item.task_id:
        title = str(item.task_title or "").strip() or "—"
        status = str(item.task_status or "").strip() or "—"
        task_label = f"{title} ({status})"
    return PrehledVyporadaniItemView(
        audit_label=audit_label,
        workplace_name=str(item.workplace_name or ""),
        finding_type_label=finding_type_label(str(item.finding_type or "")),
        process_label=str(item.process_label or ""),
        verification_area_label=str(item.verification_area_label or ""),
        description=str(item.description or ""),
        recommended_action=str(item.recommended_action or ""),
        status_label=finding_status_label(str(item.status or "")),
        resolved_at_label=format_overview_date(item.resolved_at),
        task_label=task_label,
        categories=_categories(item, sequence),
        description_snapshot=str(item.description or ""),
    )


def _categories(item: FindingSettlementOverviewItem, sequence: int) -> str:
    if sequence <= 0:
        return "výchozí stav"
    names: list[str] = []
    if item.settled_since_previous:
        names.append("vypořádané od posledního přehledu")
    if item.still_unsettled or item.status in _OPEN_STATUSES:
        names.append("dosud nevypořádané")
    if item.is_new:
        names.append("nové zjištění")
    if item.reopened:
        names.append("znovuotevřené")
    if item.resettled:
        names.append("opakovaně vypořádané")
    return ", ".join(names) if names else "—"


def _settled_source(
    items: list[FindingSettlementOverviewItem],
    sequence: int,
) -> list[FindingSettlementOverviewItem]:
    if sequence == 0:
        return [item for item in items if item.status == FINDING_STATUS_VYPORADANO]
    return [item for item in items if item.settled_since_previous]


def _type_counts(
    overview: FindingSettlementOverview,
) -> tuple[tuple[str, int], ...]:
    raw_text = overview.type_counts_json if overview.type_counts_json else "{}"
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PrehledVyporadaniExportError(
            "Historický přehled je poškozený a nelze ho použít."
        ) from exc
    if not isinstance(raw, dict):
        raise PrehledVyporadaniExportError(
            "Historický přehled je poškozený a nelze ho použít."
        )
    counts: list[tuple[str, int]] = []
    for key, value in raw.items():
        try:
            count = int(value)
        except (TypeError, ValueError) as exc:
            raise PrehledVyporadaniExportError(
                "Historický přehled je poškozený a nelze ho použít."
            ) from exc
        counts.append((finding_type_label(str(key)), count))
    counts.sort(key=lambda row: row[0])
    return tuple(counts)


def _dash(value: str) -> str:
    text = str(value or "").strip()
    return text or "—"


prehled_vyporadani_export_service = PrehledVyporadaniExportService()
