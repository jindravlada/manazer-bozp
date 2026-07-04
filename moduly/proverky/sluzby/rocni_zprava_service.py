import subprocess
from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine
from core.services.storage_service import storage_service
from moduly.proverky.sluzby.bozp_annual_export_context_service import (
    bozp_annual_export_context_service,
)
from moduly.proverky.sluzby.bozp_annual_report_service import bozp_annual_report_service


class RocniZpravaService:
    """Vygenerování roční zprávy o stavu BOZP jako editovatelného ODT dokumentu."""

    TEMPLATE_NAME = "RocniZpravaBOZP.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "rocni_zpravy_bozp"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_year(self, year: int) -> Path:
        if year < 1900 or year > 3000:
            raise ValueError("Neplatný rok roční zprávy.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona roční zprávy nebyla nalezena: {template}")

        report = bozp_annual_report_service.get_or_create_for_year(year)
        context = bozp_annual_export_context_service.build(year, report=report)
        values = context.placeholder_values()

        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(year),
        )
        return self.engine.render(template, output_path, values)

    def open_for_year(self, year: int) -> Path:
        path = self.generate_for_year(year)
        subprocess.Popen(["xdg-open", str(path)])
        return path

    @staticmethod
    def _output_filename(year: int) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"RocniZpravaBOZP-{year}_{stamp}.odt"


rocni_zprava_service = RocniZpravaService()
