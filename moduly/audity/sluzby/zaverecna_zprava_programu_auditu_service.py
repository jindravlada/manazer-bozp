from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_program_final_export_context_service import (
    audit_program_final_export_context_service,
)
from moduly.audity.sluzby.audit_program_final_report_service import (
    audit_program_final_report_service,
)


class ZaverecnaZpravaProgramuAudituService:
    """Vygenerování závěrečné zprávy programu interních auditů jako editovatelného ODT."""

    TEMPLATE_NAME = "ZaverecnaZpravaProgramuAuditu.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "zaverecne_zpravy_programu_auditu"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        bundled = storage_service.bundled_template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)
        if bundled is not None:
            return bundled
        return storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_program(self, audit_program_id: int) -> Path:
        if audit_program_id <= 0:
            raise ValueError("Neplatný auditní program.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona závěrečné zprávy nebyla nalezena: {template}")

        report = audit_program_final_report_service.get_or_create_for_program(audit_program_id)
        context = audit_program_final_export_context_service.build(
            audit_program_id,
            report=report,
        )
        values = context.placeholder_values()

        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(context.program.name),
        )
        return self.engine.render(template, output_path, values)

    def open_for_program(self, audit_program_id: int) -> Path:
        path = self.generate_for_program(audit_program_id)
        open_export_file(path, title="Závěrečná zpráva programu")
        return path

    @staticmethod
    def _output_filename(program_name: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in (program_name or "program").strip()
        )[:40]
        return f"ZaverecnaZpravaProgramuAuditu-{safe_name}_{stamp}.odt"


zaverecna_zprava_programu_auditu_service = ZaverecnaZpravaProgramuAudituService()
