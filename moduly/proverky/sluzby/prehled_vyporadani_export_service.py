"""Export uloženého přehledu vypořádání zjištění z prověrek BOZP.

Dokument se skládá jen z historického snímku řady Prověrek. Výpočet
i šablona navazují na přehled interních auditů.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtExportError
from core.services.storage_service import storage_service
from core.shared.constants import SETTLEMENT_SOURCE_PROVERKY
from core.shared.sluzby.finding_settlement_overview_service import (
    finding_settlement_overview_service,
)
from moduly.audity.sluzby.prehled_vyporadani_export_service import (
    PrehledVyporadaniExportError,
    PrehledVyporadaniView,
    build_view,
    placeholder_values,
)

RECORD_HEADING = "Prověrka / pracoviště"


def inspection_scope_warning(completed_record_count: int, finding_count: int) -> str:
    if completed_record_count <= 0:
        return "Neexistuje žádná dokončená prověrka BOZP. Přehled bude prázdný."
    if finding_count <= 0:
        return "Dokončené prověrky neobsahují žádná zjištění. Přehled bude prázdný."
    return ""


class PrehledVyporadaniProverkyExportService:
    TEMPLATE_NAME = "PrehledVyporadaniZjisteniProverky.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "prehledy_vyporadani_proverky"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def load_view(self, overview_id: int) -> PrehledVyporadaniView:
        overview = finding_settlement_overview_service.get_overview(int(overview_id))
        if overview is None or overview.source_type != SETTLEMENT_SOURCE_PROVERKY:
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
        values = placeholder_values(
            view,
            record_heading=RECORD_HEADING,
            include_presented_date=True,
        )
        try:
            return self.engine.render(template, target, values)
        except (OdtExportError, OSError, FileNotFoundError) as exc:
            raise PrehledVyporadaniExportError(
                f"Přehled se nepodařilo exportovat.\n\n{exc}"
            ) from exc

    @staticmethod
    def _output_filename(sequence_number: int) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"PrehledVyporadaniProverky-{int(sequence_number)}_{stamp}.odt"


prehled_vyporadani_proverky_export_service = PrehledVyporadaniProverkyExportService()
