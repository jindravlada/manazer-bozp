from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.export.commission_display import AUDIT_OPTIONAL_COMMISSION_PLACEHOLDERS
from core.services.storage_service import storage_service
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_export_context_service import (
    DETAILED_REPORT_DOCUMENT_CONFIG,
    PROTOCOL_DOCUMENT_CONFIG,
    AuditExportDocumentConfig,
    audit_export_context_service,
)

PROTOCOL_INCOMPLETE_WARNING = (
    "Audit ještě není dokončený. Protokol bude vygenerován v aktuálním stavu."
)

# AUDIT-BUG-2: dočasná diagnostika exportu protokolu. Výchozí vypnuto.
# Zapnutí: MANAZER_BOZP_PROTOKOL_AUDIT_DIAG=1
_DIAG_ENABLED = False
_DIAG_ENV = "MANAZER_BOZP_PROTOKOL_AUDIT_DIAG"
_DIAG_LOG_NAME = "protokol_audit_debug.log"


def _diag_is_enabled() -> bool:
    if _DIAG_ENABLED:
        return True
    raw = os.environ.get(_DIAG_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _diag(message: str) -> None:
    """Dočasné diagnostické logování exportu protokolu (stderr + soubor)."""
    if not _diag_is_enabled():
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[protokol-audit {stamp}] {message}"
    print(line, flush=True)
    try:
        storage_service.ensure_structure()
        log_path = storage_service.logs_dir / _DIAG_LOG_NAME
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        print(f"[protokol-audit] nelze zapsat log: {exc}", flush=True)


class ProtokolAuditService:
    """Vygenerování protokolu / podrobné zprávy z auditu jako ODT dokumentu."""

    TEMPLATE_NAME = "ProtokolAudit.odt"
    DETAILED_REPORT_TEMPLATE_NAME = "PodrobnaZpravaAudit.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "protokoly_auditu"
    DETAILED_REPORT_EXPORT_SUBDIR = "podrobne_zpravy_auditu"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self, *, detailed: bool = False) -> Path:
        storage_service.ensure_structure()
        name = self.DETAILED_REPORT_TEMPLATE_NAME if detailed else self.TEMPLATE_NAME
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            name,
        )

    def generate_for_audit(self, audit: Audit) -> Path:
        return self._generate(
            audit,
            config=PROTOCOL_DOCUMENT_CONFIG,
            detailed=False,
            open_title="Protokol auditu",
        )

    def generate_detailed_report_for_audit(self, audit: Audit) -> Path:
        return self._generate(
            audit,
            config=DETAILED_REPORT_DOCUMENT_CONFIG,
            detailed=True,
            open_title="Podrobná zpráva z auditu",
        )

    def open_for_audit(self, audit: Audit) -> Path:
        audit_id = getattr(audit, "id", None) if audit is not None else None
        _diag(f"open_for_audit() ENTER audit_id={audit_id}")
        try:
            path = self.generate_for_audit(audit)
            _diag(f"open_export_file({path})")
            open_export_file(path, title="Protokol auditu")
            _diag("open_for_audit() EXIT ok")
            return path
        except Exception:
            _diag("open_for_audit() EXCEPTION:\n" + traceback.format_exc())
            raise

    def open_detailed_report_for_audit(self, audit: Audit) -> Path:
        audit_id = getattr(audit, "id", None) if audit is not None else None
        _diag(f"open_detailed_report_for_audit() ENTER audit_id={audit_id}")
        try:
            path = self.generate_detailed_report_for_audit(audit)
            _diag(f"open_export_file({path})")
            open_export_file(path, title="Podrobná zpráva z auditu")
            _diag("open_detailed_report_for_audit() EXIT ok")
            return path
        except Exception:
            _diag(
                "open_detailed_report_for_audit() EXCEPTION:\n"
                + traceback.format_exc()
            )
            raise

    def incomplete_warning(self, audit: Audit) -> str | None:
        context = audit_export_context_service.build(audit)
        if context.is_completed():
            return None
        return PROTOCOL_INCOMPLETE_WARNING

    def _generate(
        self,
        audit: Audit,
        *,
        config: AuditExportDocumentConfig,
        detailed: bool,
        open_title: str,
    ) -> Path:
        del open_title  # used only by open_* wrappers
        audit_id = getattr(audit, "id", None) if audit is not None else None
        kind = "detailed_report" if detailed else "protocol"
        _diag(f"generate({kind}) start audit_id={audit_id}")

        if audit is None or not audit_id:
            raise ValueError("Není vybraný uložený audit.")

        _diag("načítám šablonu")
        template = self.template_path(detailed=detailed)
        _diag(f"šablona={template} exists={template.exists()}")
        if not template.exists():
            label = "podrobné zprávy" if detailed else "protokolu"
            raise FileNotFoundError(f"Šablona {label} nebyla nalezena: {template}")

        _diag("vytvářím context")
        context = audit_export_context_service.build(audit, config=config)
        _diag(
            "context hotov "
            f"finished_at={getattr(audit, 'finished_at', None)!r} "
            f"number={getattr(audit, 'number', None)!r} "
            f"detailed={detailed}"
        )

        _diag("placeholder_values()")
        values = context.placeholder_values()
        total_chars = sum(len(str(v)) for v in values.values())
        _diag(f"placeholder_values() hotovo keys={len(values)} chars={total_chars}")

        export_subdir = (
            self.DETAILED_REPORT_EXPORT_SUBDIR if detailed else self.EXPORT_SUBDIR
        )
        output_path = storage_service.export_file(
            export_subdir,
            self._output_filename(audit, detailed=detailed),
        )
        _diag(f"render() → {output_path}")
        rendered = self.engine.render(
            template,
            output_path,
            values,
            omit_empty_placeholder_rows=AUDIT_OPTIONAL_COMMISSION_PLACEHOLDERS,
        )
        _diag(
            f"soubor vytvořen path={rendered} "
            f"exists={rendered.exists()} "
            f"size={rendered.stat().st_size if rendered.exists() else 0}"
        )
        return rendered

    def _output_filename(self, audit: Audit, *, detailed: bool = False) -> str:
        number = str(getattr(audit, "number", "") or "bez-cisla").replace("/", "-").replace("\\", "-")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "PodrobnaZpravaAudit" if detailed else "ProtokolAudit"
        return f"{prefix}-{number}_{stamp}.odt"


protokol_audit_service = ProtokolAuditService()
