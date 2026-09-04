from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_program_plan_export_context_service import (
    audit_program_plan_export_context_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service


class AuditProgramPlanExportService:
    """Vygenerování plánu interních auditů jako ODT dokumentu."""

    TEMPLATE_NAME = "PlanInternichAuditu.odt"
    TEMPLATE_SUBDIR = "exporty"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def default_filename(self, program_id: int) -> str:
        overview = audit_program_service.get_program_overview(program_id)
        if overview is None:
            raise ValueError("Auditní program nebyl nalezen.")
        program = overview.program
        number = self._safe_filename_part(program.number, fallback="program")
        years = self._period_years(program.date_from, program.date_to)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts = ["Plan_internich_auditu", number]
        if years:
            parts.append(years)
        return "_".join(parts) + f"_{stamp}.odt"

    def generate_preview_for_program(self, program_id: int) -> Path:
        """Zapíše plán do dočasného ODT; soubor se nesmaže po otevření."""
        stem = Path(self.default_filename(program_id)).stem
        handle, raw = tempfile.mkstemp(
            prefix=f"{stem}_",
            suffix=".odt",
            dir=tempfile.gettempdir(),
        )
        os.close(handle)
        target = Path(raw)
        try:
            return self.generate_for_program(program_id, target)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def generate_for_program(self, program_id: int, output_path: str | Path) -> Path:
        if program_id <= 0:
            raise ValueError("Neplatný auditní program.")
        overview = audit_program_service.get_program_overview(program_id)
        if overview is None:
            raise ValueError("Auditní program nebyl nalezen.")
        if not overview.visits:
            raise ValueError("Program nemá žádné plánované návštěvy.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona plánu auditu nebyla nalezena: {template}")

        context = audit_program_plan_export_context_service.build(program_id)
        target = Path(output_path)
        if target.suffix.lower() != ".odt":
            target = target.with_suffix(".odt")
        target.parent.mkdir(parents=True, exist_ok=True)
        return self.engine.render(template, target, context.placeholder_values())

    @staticmethod
    def _period_years(date_from, date_to) -> str:
        if date_from is None and date_to is None:
            return ""
        if date_from is None:
            return str(date_to.year)
        if date_to is None:
            return str(date_from.year)
        if date_from.year == date_to.year:
            return str(date_from.year)
        return f"{date_from.year}-{date_to.year}"

    @staticmethod
    def _safe_filename_part(value: str, *, fallback: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
        cleaned = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in ascii_text.strip()
        )
        cleaned = re.sub(r"_+", "_", cleaned).strip("._")
        return cleaned[:60] or fallback


audit_program_plan_export_service = AuditProgramPlanExportService()
