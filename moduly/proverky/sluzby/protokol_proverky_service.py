from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.services.storage_service import storage_service
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
    bozp_inspection_export_context_service,
)

PROTOCOL_INCOMPLETE_WARNING = (
    "Prověrka ještě není dokončená. Protokol bude vygenerován v aktuálním stavu."
)


class ProtokolProverkyService:
    """Vygenerování protokolu o prověrce BOZP jako editovatelného ODT dokumentu."""

    TEMPLATE_NAME = "ProtokolProverkyBOZP.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "protokoly_proverky"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME
        )

    def generate_for_inspection(self, inspection: BozpInspection) -> Path:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona protokolu nebyla nalezena: {template}")

        context = bozp_inspection_export_context_service.build(inspection)
        values = context.placeholder_values()

        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(inspection),
        )
        return self.engine.render(template, output_path, values)

    def open_for_inspection(self, inspection: BozpInspection) -> Path:
        path = self.generate_for_inspection(inspection)
        open_export_file(path, title="Protokol prověrky")
        return path

    def incomplete_warning(self, inspection: BozpInspection) -> str | None:
        context = bozp_inspection_export_context_service.build(inspection)
        if context.is_completed():
            return None
        return PROTOCOL_INCOMPLETE_WARNING

    def _output_filename(self, inspection: BozpInspection) -> str:
        number = str(getattr(inspection, "number", "") or "bez-cisla").replace("/", "-").replace("\\", "-")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ProtokolProverkyBOZP-{number}_{stamp}.odt"


protokol_proverky_service = ProtokolProverkyService()
