from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.services.storage_service import storage_service
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_export_context_service import audit_export_context_service

PROTOCOL_INCOMPLETE_WARNING = (
    "Audit ještě není dokončený. Protokol bude vygenerován v aktuálním stavu."
)


class ProtokolAuditService:
    """Vygenerování protokolu z auditu jako editovatelného ODT dokumentu."""

    TEMPLATE_NAME = "ProtokolAudit.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "protokoly_auditu"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        bundled = storage_service.bundled_template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)
        if bundled is not None:
            return bundled
        return storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_audit(self, audit: Audit) -> Path:
        if audit is None or not getattr(audit, "id", None):
            raise ValueError("Není vybraný uložený audit.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona protokolu nebyla nalezena: {template}")

        context = audit_export_context_service.build(audit)
        values = context.placeholder_values()

        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(audit),
        )
        return self.engine.render(template, output_path, values)

    def open_for_audit(self, audit: Audit) -> Path:
        path = self.generate_for_audit(audit)
        open_export_file(path, title="Protokol auditu")
        return path

    def incomplete_warning(self, audit: Audit) -> str | None:
        context = audit_export_context_service.build(audit)
        if context.is_completed():
            return None
        return PROTOCOL_INCOMPLETE_WARNING

    def _output_filename(self, audit: Audit) -> str:
        number = str(getattr(audit, "number", "") or "bez-cisla").replace("/", "-").replace("\\", "-")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ProtokolAudit-{number}_{stamp}.odt"


protokol_audit_service = ProtokolAuditService()
