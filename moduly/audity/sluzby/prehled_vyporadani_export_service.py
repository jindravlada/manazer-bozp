"""Export uloženého přehledu vypořádání zjištění z interních auditů.

Text dokumentu se skládá jen z historického snímku. Šablonu vykreslí
společný ODT engine Manažera BOZP.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from core.export import (
    OdtExportEngine,
    OdtExportError,
    OdtParagraph,
    OdtRichContent,
    OdtXmlFragment,
)
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
EMPTY_SECTION = "Žádná zjištění."
SUMMARY_HEADING = "Souhrnné vyhodnocení"

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
    source_number: str
    source_year: int | None


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


def format_audit_reference(number: str, year: int | None) -> str:
    """Číslo auditu pro dokument. Rok přidá jen tehdy, když v čísle ještě není."""
    text = str(number or "").strip()
    if year is None:
        return text or "—"
    year_text = str(int(year))
    if not text:
        return year_text
    if re.search(rf"(^|[^\d]){re.escape(year_text)}([^\d]|$)", text):
        return text
    return f"{text}/{year_text}"


def count_with_percent(count: int, total: int) -> str:
    """Podíl z uloženého počtu. Při nule nepočítá procenta."""
    value = int(count)
    whole = int(total)
    if whole <= 0:
        return str(value)
    share = (100 * value + whole // 2) // whole
    return f"{value} ({share} %)"


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
    if view.sequence_number == 0:
        header = [
            OdtParagraph.text("Přehled č. 0 – výchozí stav", style="MgmtMeta"),
            OdtParagraph.text(f"Stav k: {view.presented_label}", style="MgmtMeta"),
        ]
    else:
        header = [
            OdtParagraph.text(
                f"Přehled č. {view.sequence_number}",
                style="MgmtMeta",
            ),
            OdtParagraph.text(f"Období: {view.period_label}", style="MgmtMeta"),
        ]
    settled_title = (
        SECTION_SETTLED_BASELINE if view.sequence_number == 0 else SECTION_SETTLED_SINCE
    )
    return {
        "hlavicka": OdtRichContent(paragraphs=header),
        "souhrn": _summary(view),
        "sekce_vyporadana": _settled_section(settled_title, view.settled_items),
        "sekce_nevyporadana": _status_section(SECTION_UNSETTLED, view.unsettled_items),
        "sekce_nova": _optional_status_section(
            view.shows_changes,
            SECTION_NEW,
            view.new_items,
        ),
        "sekce_znovuotevrena": _optional_status_section(
            view.shows_changes,
            SECTION_REOPENED,
            view.reopened_items,
        ),
    }


def _summary(view: PrehledVyporadaniView) -> OdtRichContent:
    paragraphs = [
        OdtParagraph.text(SUMMARY_HEADING, style="H"),
        OdtParagraph.text(f"Celkem zjištění: {view.total_count}", style="MgmtMeta"),
        OdtParagraph.text(
            f"Vypořádáno: {count_with_percent(view.settled_count, view.total_count)}",
            style="MgmtMeta",
        ),
        OdtParagraph.text(
            f"V procesu: {count_with_percent(view.in_process_count, view.total_count)}",
            style="MgmtMeta",
        ),
        OdtParagraph.text(
            f"Otevřeno: {count_with_percent(view.open_count, view.total_count)}",
            style="MgmtMeta",
        ),
    ]
    if view.type_counts:
        types = ", ".join(f"{label}: {count}" for label, count in view.type_counts)
        paragraphs.append(OdtParagraph.text(f"Typy zjištění: {types}", style="MgmtMeta"))
    return OdtRichContent(paragraphs=paragraphs)


def _optional_status_section(
    enabled: bool,
    title: str,
    items: tuple[PrehledVyporadaniItemView, ...],
) -> OdtXmlFragment | OdtRichContent:
    if not enabled:
        return OdtRichContent(paragraphs=[], omit_when_empty=True)
    return _status_section(title, items)


def _settled_section(
    title: str,
    items: tuple[PrehledVyporadaniItemView, ...],
) -> OdtXmlFragment:
    if not items:
        return _empty_section(title)
    rows = tuple(
        (
            _audit_workplace(item),
            _finding_text(item),
            item.resolved_at_label,
        )
        for item in items
    )
    return _section_with_table(
        title,
        table_name="TabulkaVyporadana",
        column_styles=("MgmtColAudit", "MgmtColFindingWide", "MgmtColDate"),
        headers=("Audit / provoz", "Zjištění", "Datum vypořádání"),
        rows=rows,
    )


def _status_section(
    title: str,
    items: tuple[PrehledVyporadaniItemView, ...],
) -> OdtXmlFragment:
    if not items:
        return _empty_section(title)
    rows = tuple(
        (
            _audit_workplace(item),
            _finding_text(item),
            item.status_label or "—",
            item.task_label or "—",
        )
        for item in items
    )
    return _section_with_table(
        title,
        table_name=_table_name(title),
        column_styles=(
            "MgmtColAudit",
            "MgmtColFinding",
            "MgmtColStatus",
            "MgmtColTask",
        ),
        headers=("Audit / provoz", "Zjištění", "Stav", "Úkol"),
        rows=rows,
    )


def _empty_section(title: str) -> OdtXmlFragment:
    return OdtXmlFragment(
        xml=(
            _heading(title)
            + f'<text:p text:style-name="MgmtMeta">{escape(EMPTY_SECTION)}</text:p>'
        )
    )


def _section_with_table(
    title: str,
    *,
    table_name: str,
    column_styles: tuple[str, ...],
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> OdtXmlFragment:
    columns = "".join(
        f'<table:table-column table:style-name="{style}"/>'
        for style in column_styles
    )
    header = (
        "<table:table-header-rows>"
        '<table:table-row table:style-name="MgmtRow">'
        + "".join(_cell(value, header=True) for value in headers)
        + "</table:table-row></table:table-header-rows>"
    )
    body = "".join(
        '<table:table-row table:style-name="MgmtRow">'
        + "".join(_cell(value) for value in row)
        + "</table:table-row>"
        for row in rows
    )
    table = (
        f'<table:table table:name="{escape(table_name)}" table:style-name="MgmtTable">'
        f"{columns}{header}{body}</table:table>"
    )
    return OdtXmlFragment(xml=_heading(title) + table)


def _heading(title: str) -> str:
    return f'<text:p text:style-name="H">{escape(title)}</text:p>'


def _cell(value: str, *, header: bool = False) -> str:
    style = "MgmtHeaderCell" if header else "MgmtCell"
    paragraph = "MgmtHeader" if header else "MgmtText"
    return (
        f'<table:table-cell table:style-name="{style}" office:value-type="string">'
        f'<text:p text:style-name="{paragraph}">{_odt_text(value)}</text:p>'
        "</table:table-cell>"
    )


def _audit_workplace(item: PrehledVyporadaniItemView) -> str:
    reference = format_audit_reference(item.source_number, item.source_year)
    workplace = str(item.workplace_name or "").strip() or "—"
    return f"{reference}\n{workplace}"


def _finding_text(item: PrehledVyporadaniItemView) -> str:
    text = str(item.description_snapshot or "")
    if text.strip():
        return text
    return "—"


def _table_name(title: str) -> str:
    if title == SECTION_NEW:
        return "TabulkaNova"
    if title == SECTION_REOPENED:
        return "TabulkaZnovu"
    return "TabulkaNevyporadana"


def _odt_text(value: str) -> str:
    text = "" if value is None else str(value)
    escaped = escape(text)
    return (
        escaped.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<text:line-break/>")
    )


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
        source_number=str(item.audit_number or ""),
        source_year=None if item.audit_year is None else int(item.audit_year),
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


prehled_vyporadani_export_service = PrehledVyporadaniExportService()
