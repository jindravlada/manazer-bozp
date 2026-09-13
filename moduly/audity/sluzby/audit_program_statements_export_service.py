from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine
from core.export.open_export import (
    create_managed_temp_file,
    unlink_managed_temp_file,
)
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_statements_export_context_service import (
    audit_program_statements_export_context_service,
)


class AuditProgramStatementsExportService:
    """Vygenerování auditních tvrzení návštěvy jako ODT dokumentu."""

    TEMPLATE_NAME = "AuditniTvrzeni.odt"
    TEMPLATE_SUBDIR = "exporty"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def default_filename(self, visit_id: int) -> str:
        visit = audit_program_service.repository.get_visit(visit_id)
        if visit is None:
            raise ValueError("Návštěva nebyla nalezena.")
        program = audit_program_service.repository.get_program(visit.program_id)
        workplace = audit_program_service._resolve_workplace_name(visit)
        program_part = self._safe_filename_part(
            getattr(program, "number", "") or getattr(program, "name", ""),
            fallback="program",
        )
        workplace_part = self._safe_filename_part(workplace, fallback="provoz")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        year = visit.planned_year or 0
        month = visit.planned_month or 0
        parts = ["Auditni_tvrzeni", program_part, workplace_part]
        if year:
            parts.append(str(year))
        if month:
            parts.append(f"{int(month):02d}")
        return "_".join(parts) + f"_{stamp}.odt"

    def generate_preview_for_visit(self, visit_id: int) -> Path:
        """Zapíše tvrzení do dočasného ODT; úklid až při ukončení Manažera."""
        context = audit_program_statements_export_context_service.build_for_visit(
            visit_id
        )
        target = create_managed_temp_file(
            name_hint=self.default_filename(visit_id)
        )
        try:
            return self._render(context, target)
        except Exception:
            unlink_managed_temp_file(target)
            raise

    def generate_for_visit(self, visit_id: int, output_path: str | Path) -> Path:
        context = audit_program_statements_export_context_service.build_for_visit(
            visit_id
        )
        return self._render(context, Path(output_path))

    def _render(self, context, output_path: Path) -> Path:
        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(
                f"Šablona auditních tvrzení nebyla nalezena: {template}"
            )
        target = Path(output_path)
        if target.suffix.lower() != ".odt":
            target = target.with_suffix(".odt")
        target.parent.mkdir(parents=True, exist_ok=True)
        return self.engine.render(template, target, context.placeholder_values())

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


audit_program_statements_export_service = AuditProgramStatementsExportService()
