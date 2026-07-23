from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.services.storage_service import storage_service
from moduly.proverky.constants import (
    INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
    INSPECTION_PROTOCOL_DIALOG_TITLE,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
    DETAILED_REPORT_DOCUMENT_CONFIG,
    PROTOCOL_DOCUMENT_CONFIG,
    InspectionExportDocumentConfig,
    bozp_inspection_export_context_service,
)

PROTOCOL_INCOMPLETE_WARNING = (
    "Prověrka ještě není dokončená. Protokol bude vygenerován v aktuálním stavu."
)
DETAILED_REPORT_INCOMPLETE_WARNING = (
    "Prověrka ještě není dokončená. Podrobná zpráva bude vygenerována v aktuálním stavu."
)


class ProtokolProverkyService:
    """Vygenerování protokolu / podrobné zprávy z prověrky BOZP jako ODT dokumentu."""

    TEMPLATE_NAME = "ProtokolProverkyBOZP.odt"
    DETAILED_REPORT_TEMPLATE_NAME = "PodrobnaZpravaProverky.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "protokoly_proverky"
    DETAILED_REPORT_EXPORT_SUBDIR = "podrobne_zpravy_proverky"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self, *, detailed: bool = False) -> Path:
        storage_service.ensure_structure()
        name = (
            self.DETAILED_REPORT_TEMPLATE_NAME if detailed else self.TEMPLATE_NAME
        )
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            name,
        )

    def generate_for_inspection(self, inspection: BozpInspection) -> Path:
        return self._generate(
            inspection,
            config=PROTOCOL_DOCUMENT_CONFIG,
            detailed=False,
        )

    def generate_detailed_report_for_inspection(
        self, inspection: BozpInspection
    ) -> Path:
        return self._generate(
            inspection,
            config=DETAILED_REPORT_DOCUMENT_CONFIG,
            detailed=True,
        )

    def open_for_inspection(self, inspection: BozpInspection) -> Path:
        path = self.generate_for_inspection(inspection)
        open_export_file(path, title=INSPECTION_PROTOCOL_DIALOG_TITLE)
        return path

    def open_detailed_report_for_inspection(
        self, inspection: BozpInspection
    ) -> Path:
        path = self.generate_detailed_report_for_inspection(inspection)
        open_export_file(path, title=INSPECTION_DETAILED_REPORT_DIALOG_TITLE)
        return path

    def incomplete_warning(
        self,
        inspection: BozpInspection,
        *,
        detailed: bool = False,
    ) -> str | None:
        context = bozp_inspection_export_context_service.build(inspection)
        if context.is_completed():
            return None
        if detailed:
            return DETAILED_REPORT_INCOMPLETE_WARNING
        return PROTOCOL_INCOMPLETE_WARNING

    def _generate(
        self,
        inspection: BozpInspection,
        *,
        config: InspectionExportDocumentConfig,
        detailed: bool,
    ) -> Path:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")

        template = self.template_path(detailed=detailed)
        if not template.exists():
            label = "podrobné zprávy" if detailed else "protokolu"
            raise FileNotFoundError(f"Šablona {label} nebyla nalezena: {template}")

        context = bozp_inspection_export_context_service.build(
            inspection, config=config
        )
        values = context.placeholder_values()

        export_subdir = (
            self.DETAILED_REPORT_EXPORT_SUBDIR if detailed else self.EXPORT_SUBDIR
        )
        output_path = storage_service.export_file(
            export_subdir,
            self._output_filename(inspection, detailed=detailed),
        )
        return self.engine.render(template, output_path, values)

    def _output_filename(
        self, inspection: BozpInspection, *, detailed: bool = False
    ) -> str:
        number = (
            str(getattr(inspection, "number", "") or "bez-cisla")
            .replace("/", "-")
            .replace("\\", "-")
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "PodrobnaZpravaProverky" if detailed else "ProtokolProverkyBOZP"
        return f"{prefix}-{number}_{stamp}.odt"


protokol_proverky_service = ProtokolProverkyService()
