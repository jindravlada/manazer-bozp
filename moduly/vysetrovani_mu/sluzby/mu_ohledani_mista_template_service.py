"""Tisk prázdné pracovní šablony Ohledání místa mimořádné události."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from moduly.vysetrovani_mu.constants import OHLEDANI_MISTA_PRINT_DIALOG_TITLE
from moduly.vysetrovani_mu.modely.mu_investigation import MuInvestigation
from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
from moduly.vysetrovani_mu.sluzby.mu_source_context import resolve_mu_source_context

_HANDWRITE_LINE = "________________________________________________"
_HANDWRITE_SHORT = "____________________"


def _text(value) -> str:
    return str(value or "").strip()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return _text(value) or "—"


def _blank_lines(count: int) -> list[OdtParagraph]:
    return [OdtParagraph.text(_HANDWRITE_LINE) for _ in range(count)]


class MuOhledaniMistaTemplateService:
    TEMPLATE_NAME = "SablonaOhledaniMista.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "sablony_ohledani_mista"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def build_context(self, investigation: MuInvestigation) -> dict:
        context = resolve_mu_source_context(
            _text(getattr(investigation, "source_type", None)),
            getattr(investigation, "source_id", None),
            _text(getattr(investigation, "source_label", None)),
            _text(getattr(investigation, "number", None)),
        )
        event_date = context.event_datum or getattr(investigation, "started_at", None)
        place = _text(context.event_misto) or _text(
            getattr(investigation, "source_label", None)
        )
        return {
            "cislo_mu": _text(getattr(investigation, "number", None)) or "—",
            "nazev": _text(getattr(investigation, "title", None)) or "—",
            "charakter": _text(getattr(investigation, "event_character", None)) or "—",
            "datum_udalosti": _format_date(event_date),
            "cas_udalosti": _text(context.event_cas) or "—",
            "misto": place or "—",
            "formular_text": self._form_content(),
        }

    def generate_for_investigation(self, investigation: MuInvestigation) -> Path:
        if investigation is None or not getattr(investigation, "id", None):
            raise ValueError("Není vybrané uložené vyšetřování.")

        storage_service.ensure_structure()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        number = _text(getattr(investigation, "number", None)) or str(investigation.id)
        safe_number = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in number)
        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            f"SablonaOhledaniMista-{safe_number}_{stamp}.odt",
        )
        self.engine.render(self.template_path(), output_path, self.build_context(investigation))
        return output_path

    def open_for_investigation(self, investigation: MuInvestigation) -> Path:
        path = self.generate_for_investigation(investigation)
        open_export_file(path, title=OHLEDANI_MISTA_PRINT_DIALOG_TITLE)
        return path

    def generate_for_investigation_id(self, investigation_id: int) -> Path:
        investigation = mu_investigation_service.get_by_id(investigation_id)
        if investigation is None:
            raise ValueError("Vyšetřování nebylo nalezeno.")
        return self.generate_for_investigation(investigation)

    def open_for_investigation_id(self, investigation_id: int) -> Path:
        investigation = mu_investigation_service.get_by_id(investigation_id)
        if investigation is None:
            raise ValueError("Vyšetřování nebylo nalezeno.")
        return self.open_for_investigation(investigation)

    def _form_content(self) -> OdtRichContent:
        paragraphs: list[OdtParagraph] = [
            OdtParagraph.text(
                "Pracovní formulář k ručnímu vyplnění při ohledání místa. "
                "Po návratu přepište údaje do záložky Ohledání místa.",
            ),
            OdtParagraph.blank_line(),
            OdtParagraph.text("Protokol o ohledání místa události", bold=True),
            OdtParagraph.text(f"Záznam provedl: {_HANDWRITE_LINE}"),
            OdtParagraph.text(f"Provoz: {_HANDWRITE_LINE}"),
            OdtParagraph.text("Ohledání místa provedli:"),
            *_blank_lines(5),
            OdtParagraph.text(
                f"Čas ohledání - zahájení: {_HANDWRITE_SHORT}"
            ),
            OdtParagraph.text(
                f"Čas ohledání - ukončení: {_HANDWRITE_SHORT}"
            ),
            OdtParagraph.blank_line(),
            OdtParagraph.text("Výsledek ohledání", bold=True),
            OdtParagraph.text("Podrobný popis místa:"),
            *_blank_lines(10),
            OdtParagraph.blank_line(),
            OdtParagraph.text("Podepsaný protokol a fotodokumentace", bold=True),
            OdtParagraph.text(
                "Poznámka k pořízené fotodokumentaci / přiloženému protokolu:"
            ),
            *_blank_lines(4),
        ]
        return OdtRichContent(paragraphs=paragraphs)


mu_ohledani_mista_template_service = MuOhledaniMistaTemplateService()
