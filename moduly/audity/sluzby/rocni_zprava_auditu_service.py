from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_annual_export_context_service import (
    audit_annual_export_context_service,
)
from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service


class RocniZpravaAudituService:
    """Vygenerování roční zprávy z interních auditů jako editovatelného ODT dokumentu."""

    TEMPLATE_NAME = "RocniZpravaAuditu.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "rocni_zpravy_auditu"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        bundled = storage_service.bundled_template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)
        if bundled is not None:
            return bundled
        return storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_year(self, year: int, *, audit_program_id: int | None = None) -> Path:
        if year < 1900 or year > 3000:
            raise ValueError("Neplatný rok roční zprávy.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona roční zprávy nebyla nalezena: {template}")

        report = audit_annual_report_service.get_or_create_for_year(
            year,
            audit_program_id=audit_program_id,
        )
        context = audit_annual_export_context_service.build(year, report=report)
        values = context.placeholder_values()

        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(year),
        )
        return self.engine.render(template, output_path, values)

    def open_for_year(self, year: int, *, audit_program_id: int | None = None) -> Path:
        path = self.generate_for_year(year, audit_program_id=audit_program_id)
        open_export_file(path, title="Roční zpráva auditu")
        return path

    @staticmethod
    def _output_filename(year: int) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"RocniZpravaAuditu-{year}_{stamp}.odt"


rocni_zprava_auditu_service = RocniZpravaAudituService()
