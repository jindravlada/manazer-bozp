"""Export terénního checklistu auditu – pracovní pomůcka pro pochůzku provozem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from core.shared.verification_type import VERIFICATION_TYPE_TERRAIN
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    CONTROL_POINT_SEVERITY_OPTIONS,
    EXTRAORDINARY_CHECKLIST_SECTION_TITLE,
    TERRAIN_CHECKLIST_DIALOG_TITLE,
    TERRAIN_CHECKLIST_EMPTY,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
from moduly.audity.sluzby.audit_question_source_service import (
    AuditQuestionSourceError,
    audit_question_source_service,
)
from moduly.audity.sluzby.audit_verification_service import audit_verification_service

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


def _text(value) -> str:
    return str(value or "").strip()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return _text(value) or "—"


def _severity_label(value) -> str:
    raw = _text(value).lower()
    return _SEVERITY_LABELS.get(raw, _text(value) or "—")


class AuditTerrainChecklistService:
    TEMPLATE_NAME = "TerenniChecklistAuditu.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "terenni_checklisty_auditu"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def generate_for_audit(
        self,
        audit: Audit,
        *,
        process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
    ) -> Path:
        if audit is None or not getattr(audit, "id", None):
            raise ValueError("Není vybraný uložený audit.")

        storage_service.ensure_structure()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        number = _text(getattr(audit, "number", None)) or str(audit.id)
        safe_number = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in number)
        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            f"TerenniChecklistAuditu-{safe_number}_{stamp}.odt",
        )

        values = {
            "cislo_auditu": number or "—",
            "kontrolovany_provoz": _text(getattr(audit, "workplace_name", None)) or "—",
            "datum_auditu": _format_date(
                getattr(audit, "started_at", None)
                or getattr(audit, "finished_at", None)
            ),
            "checklist_text": self._checklist_content(
                audit.id,
                process_ids=process_ids,
            ),
        }
        self.engine.render(self.template_path(), output_path, values)
        return output_path

    def open_for_audit(
        self,
        audit: Audit,
        *,
        process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
    ) -> Path:
        path = self.generate_for_audit(audit, process_ids=process_ids)
        open_export_file(path, title=TERRAIN_CHECKLIST_DIALOG_TITLE)
        return path

    def _checklist_content(
        self,
        audit_id: int,
        *,
        process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
    ) -> OdtRichContent:
        points = audit_verification_service.list_assertions(
            audit_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            process_ids=process_ids,
        )
        # Standardní terén: bez mimořádných (ty mají vlastní sekci dle zmrazeného typu).
        standard = [
            ref
            for ref in points
            if interpret_question_kind((ref.control_point or {}).get("question_kind"))
            != AUDIT_QUESTION_KIND_EXTRAORDINARY
        ]
        extraordinary_terrain = self._extraordinary_terrain_from_snapshot(audit_id)

        if not standard and not extraordinary_terrain:
            return OdtRichContent(paragraphs=[OdtParagraph.text(TERRAIN_CHECKLIST_EMPTY)])

        paragraphs: list[OdtParagraph] = []
        for index, ref in enumerate(standard):
            if index > 0:
                paragraphs.append(OdtParagraph.blank_line())
            paragraphs.append(
                OdtParagraph.text(
                    f"{ref.area_label} · {ref.section_label}",
                    keep_with_next=True,
                )
            )
            paragraphs.append(
                OdtParagraph.text(
                    ref.control_point_label,
                    bold=True,
                    keep_with_next=True,
                )
            )
            paragraphs.append(
                OdtParagraph.text(
                    "Poznámka: ________________________________",
                    keep_with_next=True,
                )
            )
            paragraphs.append(OdtParagraph.text("_________________________________________"))

        if extraordinary_terrain:
            if paragraphs:
                paragraphs.append(OdtParagraph.blank_line())
            paragraphs.append(
                OdtParagraph.text(
                    EXTRAORDINARY_CHECKLIST_SECTION_TITLE,
                    bold=True,
                    keep_with_next=True,
                )
            )
            for index, item in enumerate(extraordinary_terrain):
                paragraphs.append(OdtParagraph.blank_line())
                process_label = _text(item.get("process_name")) or "—"
                severity = _severity_label(item.get("severity"))
                paragraphs.append(
                    OdtParagraph.text(
                        f"{process_label} · závažnost: {severity}",
                        keep_with_next=True,
                    )
                )
                paragraphs.append(
                    OdtParagraph.text(
                        _text(item.get("assertion_text")) or "—",
                        bold=True,
                        keep_with_next=True,
                    )
                )
                paragraphs.append(
                    OdtParagraph.text(
                        "Poznámka: ________________________________",
                        keep_with_next=True,
                    )
                )
                paragraphs.append(
                    OdtParagraph.text("_________________________________________")
                )

        return OdtRichContent(paragraphs=paragraphs)

    def _extraordinary_terrain_from_snapshot(self, audit_id: int) -> list[dict]:
        """Jen mimořádné se zmrazeným verification_type=teren; legacy bez typu vynechat."""
        try:
            source = audit_question_source_service.resolve_for_audit(audit_id)
        except AuditQuestionSourceError:
            return []
        if not source.is_snapshot:
            return []
        items: list[dict] = []
        for view in source.assertions:
            if interpret_question_kind(view.question_kind) != AUDIT_QUESTION_KIND_EXTRAORDINARY:
                continue
            frozen = _text(view.verification_type)
            if frozen != VERIFICATION_TYPE_TERRAIN:
                continue
            items.append(
                {
                    "assertion_text": view.assertion_text,
                    "process_name": view.process_name,
                    "severity": view.severity,
                    "display_order": view.display_order,
                }
            )
        items.sort(
            key=lambda row: (
                int(row.get("display_order") or 0),
                _text(row.get("assertion_text")).lower(),
            )
        )
        return items


audit_terrain_checklist_service = AuditTerrainChecklistService()
