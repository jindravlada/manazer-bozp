"""Export terénního checklistu – pracovní pomůcka pro pochůzku provozem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from moduly.proverky.constants import (
    TERRAIN_CHECKLIST_DIALOG_TITLE,
    TERRAIN_CHECKLIST_EMPTY,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.inspection_verification_service import (
    inspection_verification_service,
)


def _text(value) -> str:
    return str(value or "").strip()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return _text(value) or "—"


class TerrainChecklistService:
    TEMPLATE_NAME = "TerenniChecklist.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "terenni_checklisty"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def generate_for_inspection(self, inspection: BozpInspection) -> Path:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")

        storage_service.ensure_structure()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        number = _text(getattr(inspection, "number", None)) or str(inspection.id)
        safe_number = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in number)
        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            f"TerenniChecklist-{safe_number}_{stamp}.odt",
        )

        values = {
            "cislo_proverky": number or "—",
            "kontrolovany_provoz": _text(getattr(inspection, "workplace_name", None)) or "—",
            "datum_proverky": _format_date(
                getattr(inspection, "started_at", None)
                or getattr(inspection, "finished_at", None)
            ),
            "checklist_text": self._checklist_content(inspection.id),
        }
        self.engine.render(self.template_path(), output_path, values)
        return output_path

    def open_for_inspection(self, inspection: BozpInspection) -> Path:
        path = self.generate_for_inspection(inspection)
        open_export_file(path, title=TERRAIN_CHECKLIST_DIALOG_TITLE)
        return path

    def _checklist_content(self, inspection_id: int) -> OdtRichContent:
        points = inspection_verification_service.list_control_points(
            inspection_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        if not points:
            return OdtRichContent(paragraphs=[OdtParagraph.text(TERRAIN_CHECKLIST_EMPTY)])

        paragraphs: list[OdtParagraph] = []
        for index, ref in enumerate(points):
            if index > 0:
                paragraphs.append(OdtParagraph.blank_line())
            paragraphs.append(
                OdtParagraph.text(f"{ref.area_label} · {ref.section_label}")
            )
            paragraphs.append(
                OdtParagraph.text(ref.control_point_label, bold=True)
            )
            paragraphs.append(OdtParagraph.text("Poznámka: ________________________________"))
            paragraphs.append(OdtParagraph.text("_________________________________________"))
        return OdtRichContent(paragraphs=paragraphs)


terrain_checklist_service = TerrainChecklistService()
